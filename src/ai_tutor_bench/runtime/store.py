from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from .contracts import JSON, JsonValue, canonical, digest, now
from .core.settlement import SETTLEMENT_VIEW, Settlement

SCHEMA = """
CREATE TABLE IF NOT EXISTS asset (hash TEXT PRIMARY KEY, body BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS run (
    id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, manifest TEXT NOT NULL REFERENCES asset(hash)
);
CREATE TABLE IF NOT EXISTS run_check (
    id INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES run(id), checked TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('verified','blocked')), detail TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS episode (
    id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES run(id),
    plan TEXT NOT NULL REFERENCES asset(hash)
);
CREATE TABLE IF NOT EXISTS call (
    id TEXT PRIMARY KEY, episode_id TEXT NOT NULL REFERENCES episode(id),
    turn INTEGER NOT NULL, role TEXT NOT NULL, attempt INTEGER NOT NULL CHECK (attempt = 1),
    started TEXT NOT NULL, request TEXT NOT NULL REFERENCES asset(hash),
    UNIQUE(episode_id, turn, role, attempt)
);
CREATE TABLE IF NOT EXISTS result (
    call_id TEXT PRIMARY KEY REFERENCES call(id), completed TEXT NOT NULL,
    raw TEXT NOT NULL REFERENCES asset(hash), visible TEXT, status TEXT NOT NULL,
    elapsed_ms INTEGER NOT NULL, input_tokens INTEGER, output_tokens INTEGER,
    cost_microusd INTEGER NOT NULL CHECK (cost_microusd = 0),
    checks TEXT NOT NULL REFERENCES asset(hash)
);
CREATE TABLE IF NOT EXISTS event (
    call_id TEXT PRIMARY KEY REFERENCES result(call_id), data TEXT NOT NULL REFERENCES asset(hash)
);
CREATE TABLE IF NOT EXISTS blind_key (
    blind_id TEXT PRIMARY KEY, call_id TEXT NOT NULL REFERENCES result(call_id),
    export_id TEXT NOT NULL, view TEXT NOT NULL, position INTEGER NOT NULL,
    UNIQUE(export_id, view, call_id)
);
"""
APPEND_ONLY = ("asset", "run", "run_check", "episode", "call", "result", "event", "blind_key")


class Store:
    def __init__(self, database: Path) -> None:
        self.database = database.resolve()
        self.db = sqlite3.connect(database)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(SCHEMA)
        self.db.execute(SETTLEMENT_VIEW)
        for table in APPEND_ONLY:
            for operation in ("UPDATE", "DELETE"):
                self.db.execute(
                    f"CREATE TRIGGER IF NOT EXISTS {table}_no_{operation.lower()} "
                    f"BEFORE {operation} ON {table} "
                    "BEGIN SELECT RAISE(ABORT, 'append-only'); END"
                )

    def close(self) -> None:
        self.db.close()

    def asset(self, data: bytes) -> str:
        key = digest(data)
        self.db.execute("INSERT OR IGNORE INTO asset VALUES (?, ?)", (key, data))
        return key

    def open_run(self, manifest: dict[str, object]) -> str:
        with self.db:
            key = self.asset(canonical(manifest))
            name = manifest["name"]
            saved = self.db.execute("SELECT id FROM run WHERE name=?", (name,)).fetchone()
            if saved is not None and saved[0] != key:
                raise ValueError("the named run already exists with another manifest")
            self.db.execute("INSERT OR IGNORE INTO run VALUES (?, ?, ?)", (key, name, key))
        return key

    def run_manifest(self, run: str) -> JsonValue:
        row = self.db.execute(
            "SELECT a.body FROM run r JOIN asset a ON a.hash=r.manifest WHERE r.id=?", (run,)
        ).fetchone()
        if row is None:
            raise ValueError("unknown run")
        return JSON.validate_json(row[0])

    def checks(self, run: str) -> set[str]:
        return {
            row[0] for row in self.db.execute("SELECT state FROM run_check WHERE run_id=?", (run,))
        }

    def verify_run(self, run: str, *, ok: bool, detail: str) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO run_check (run_id, checked, state, detail) VALUES (?,?,?,?)",
                (run, now(), "verified" if ok else "blocked", detail),
            )

    def episode(self, run: str, plan: object) -> str:
        key = digest(canonical([run, plan]))
        with self.db:
            spec = self.asset(canonical(plan))
            self.db.execute("INSERT OR IGNORE INTO episode VALUES (?, ?, ?)", (key, run, spec))
        return key

    def start(self, episode: str, turn: int, role: str, request: object) -> str | None:
        key = digest(canonical([episode, turn, role, 1]))
        with self.db:
            request_key = self.asset(canonical(request))
            saved = self.db.execute("SELECT request FROM call WHERE id=?", (key,)).fetchone()
            if saved is not None and saved[0] != request_key:
                raise ValueError("attempt already recorded with a different request")
            cursor = self.db.execute(
                "INSERT OR IGNORE INTO call VALUES (?, ?, ?, ?, 1, ?, ?)",
                (key, episode, turn, role, now(), request_key),
            )
        return key if cursor.rowcount else None

    def prior_text(self, episode: str, turn: int) -> str | None:
        saved = self.db.execute(
            "SELECT r.visible FROM call c JOIN result r ON r.call_id=c.id "
            "WHERE c.episode_id=? AND c.turn=? AND c.role='tutor' AND r.status='ok'",
            (episode, turn),
        ).fetchone()
        return saved[0] if saved is not None else None

    def finish(
        self,
        key: str,
        raw: JsonValue,
        text: str | None,
        status: str,
        elapsed_ms: int,
        usage: tuple[int | None, int | None] = (None, None),
        event: object = None,
        checks: tuple[str, ...] = (),
    ) -> None:
        with self.db:
            raw_key = self.asset(canonical(raw))
            checks_key = self.asset(canonical(checks))
            self.db.execute(
                "INSERT INTO result VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)",
                (key, now(), raw_key, text, status, elapsed_ms, *usage, checks_key),
            )
            if event is not None:
                event_key = self.asset(canonical(event))
                self.db.execute("INSERT INTO event VALUES (?, ?)", (key, event_key))

    def settlements(self, run: str) -> list[Settlement]:
        with closing(
            self.db.execute("SELECT * FROM settlement_view WHERE run_id=?", (run,))
        ) as cursor:
            return [Settlement.model_validate(dict(row)) for row in cursor]

    def allocated_microusd(self, run: str) -> int:
        row = self.db.execute(
            "SELECT COALESCE(SUM(COALESCE(reported_microusd, 0) + reserved_microusd), 0) "
            "FROM settlement_view WHERE run_id=?",
            (run,),
        ).fetchone()
        return row[0]

    def rows(self, run: str) -> list[dict[str, JsonValue]]:
        query = """
        SELECT e.id AS episode, p.body AS plan, c.id AS call_id, c.turn, c.role, c.attempt,
               c.started, q.body AS request, r.completed, a.body AS raw, r.visible,
               COALESCE(r.status, IIF(c.id IS NULL, 'nicht_gestartet', 'abgebrochen_unklar'))
                   AS status,
               r.elapsed_ms, r.input_tokens, r.output_tokens,
               CASE WHEN s.call_id IS NULL THEN r.cost_microusd ELSE s.reported_microusd END
                   AS cost_microusd,
               s.reserved_microusd AS reserved_cost_microusd, v.body AS event,
               z.body AS checks,
               EXISTS(SELECT 1 FROM run_check w WHERE w.run_id=e.run_id AND w.state='blocked')
                   AS run_blocked
        FROM episode e JOIN asset p ON p.hash=e.plan
        LEFT JOIN call c ON c.episode_id=e.id
        LEFT JOIN result r ON r.call_id=c.id
        LEFT JOIN event x ON x.call_id=c.id
        LEFT JOIN settlement_view s ON s.call_id=c.id AND s.run_id=e.run_id
        LEFT JOIN asset q ON q.hash=c.request
        LEFT JOIN asset a ON a.hash=r.raw
        LEFT JOIN asset v ON v.hash=x.data
        LEFT JOIN asset z ON z.hash=r.checks
        WHERE e.run_id=? ORDER BY e.rowid, c.turn, c.role
        """
        with closing(self.db.execute(query, (run,))) as cursor:
            return [decode_row(dict(row)) for row in cursor]

    def add_blind_key(self, blind: str, call: str, export: str, view: str, position: int) -> None:
        self.db.execute(
            "INSERT INTO blind_key VALUES (?, ?, ?, ?, ?)", (blind, call, export, view, position)
        )


def decode_row(row: dict[str, JsonValue | bytes]) -> dict[str, JsonValue]:
    if row["reserved_cost_microusd"] is None:
        del row["reserved_cost_microusd"]
    return {
        key: JSON.validate_json(value) if isinstance(value, bytes) else value
        for key, value in row.items()
    }
