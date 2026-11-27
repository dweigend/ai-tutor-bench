"""Read OpenRouter accounting from the append-only SQLite journal.

Install SETTLEMENT_VIEW on a connection (including a read-only connection), then query
settlement_view by run_id. Each row represents one reserved tutor call. The episode plan
owns the reservation and the event owns the reported cost. SQL NULL means no reported
charge, distinct from a reported zero. New events use three-valued is_byok strings.
A legacy false confirms billing only if the raw response explicitly reports false.
A missing charge or unconfirmed OpenRouter billing keeps the full reservation open.
"""

from typing import Literal

from pydantic import Field

from ..contracts import Contract

BillingMode = Literal["confirmed_no", "confirmed_yes", "unknown"]

SETTLEMENT_VIEW = """
CREATE TEMP VIEW IF NOT EXISTS settlement_view AS
WITH journal AS (
    SELECT e.run_id, c.id AS call_id,
           json_extract(CAST(p.body AS TEXT), '$.reservation_microusd') AS reservation,
           json_extract(CAST(a.body AS TEXT), '$.cost_microusd') AS reported_microusd,
           CASE
               WHEN json_extract(CAST(a.body AS TEXT), '$.is_byok') = 'confirmed_no'
                   THEN 'confirmed_no'
               WHEN json_extract(CAST(a.body AS TEXT), '$.is_byok') = 'confirmed_yes'
                 OR json_type(CAST(a.body AS TEXT), '$.is_byok') = 'true'
                   THEN 'confirmed_yes'
               WHEN json_type(CAST(a.body AS TEXT), '$.is_byok') = 'false'
                 AND COALESCE(json_type(CAST(raw.body AS TEXT), '$.usage.is_byok'),
                              json_type(CAST(raw.body AS TEXT), '$.response.usage.is_byok'))
                     = 'false'
                   THEN 'confirmed_no'
               ELSE 'unknown'
           END AS billing_mode
    FROM call c JOIN episode e ON e.id=c.episode_id JOIN asset p ON p.hash=e.plan
    LEFT JOIN event j ON j.call_id=c.id LEFT JOIN asset a ON a.hash=j.data
    LEFT JOIN result r ON r.call_id=c.id LEFT JOIN asset raw ON raw.hash=r.raw
    WHERE c.role='tutor'
      AND json_type(CAST(p.body AS TEXT), '$.reservation_microusd')='integer'
)
SELECT run_id, call_id, reported_microusd, billing_mode,
       CASE WHEN reported_microusd IS NOT NULL AND billing_mode='confirmed_no'
            THEN 0 ELSE reservation END AS reserved_microusd
FROM journal
"""


class Settlement(Contract):
    run_id: str
    call_id: str
    reported_microusd: int | None = Field(ge=0, strict=True)
    billing_mode: BillingMode
    reserved_microusd: int = Field(ge=0, strict=True)
