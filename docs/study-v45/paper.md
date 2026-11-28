# Tutor-Bench v4.5: Measuring Multi-Turn Tutoring Behavior and Situational Scaffolding in Small LLMs

- **Author:** David Weigend · **Study date:** November 26, 2026 (English rev., November 28, 2026) · **AI assistance:** AI coding and review tools assisted under human specification and review.
- **Companion pages:** [Results Summary (5 Figures)](./results/index.html) · [Interactive Explorer](./explorer/index.html) · [v5 Harness README](https://github.com/dweigend/ai-tutor-bench#readme) · [Reproducibility Guide](https://github.com/dweigend/ai-tutor-bench/blob/main/docs/reproducibility.md)

> **Scope:** Every metric measures **simulated tutoring behavior — not human learning gains, retention, or transfer** (Käser & Alexandron, 2024). AI-jury scores remain **exploratory** until German human calibration completes, and 5/24 live coach format failures (20.8% > 10%) locked pre-registered contrasts, so all arm comparisons are descriptive.

---

## Abstract

Small language models solve math and coding problems reliably yet often break down as multi-turn tutors — leaking solutions, dropping rules, or degrading under long prompts. **Tutor-Bench v4.5** (independent of Scale AI's TutorBench, Srinivasa et al., 2025) evaluates small Flash models across 16- and 24-turn German tutoring dialogues using identical prefix forks, cross-family AI judging, and deterministic text checks:

- **Hint gains hinge on Case T3:** Fixed one-turn hints led overall only via unanimous Case T3 scores; excluding T3, two runs of the same grid point in opposite directions against a short core prompt.
- **Extra prompt text is fragile:** A length-matched neutral placebo scored below the core prompt in both runs; a full static rule prompt helped in T3 yet collapsed in T8 (representation shift).
- **Judge spread rivals model gaps:** In open 16-turn chats, Muse-Ember and Gemini 3.8 Flash averaged above Qwen 3.8 Flash and GLM 5.3 Flash under both judges, but episode spans overlapped widely and Claude vs. Codex diverged by up to 19.4 pp (Krippendorff's α = 0.476).
- **Checkpoint multi-question spikes:** After a Turn 3 one-question tutor commitment, deterministic multi-question flags jumped to 73.3% (66/90) on the four checkpoints vs. 35.1% (143/407) on routine turns.

---

## 1. Motivation and Related Work

Unrestricted chatbots lift practice scores while harming unaided exam performance (−17%, Bastani et al., 2025; no net gain, Bassner et al., 2025), whereas structured tutors raise post-test outcomes (+0.63 SD, Kestin et al., 2025; +0.24 SD near transfer, Asher et al., 2026). Default assistants rarely scaffold: 95.5% of GPT-4o mini tutoring turns solved or explained directly (Lee et al., 2026), and fine-tuned tutors still leak solutions in 70–83% of pressure dialogues (Zhao et al., 2026). Learning-science principles therefore require multi-turn evaluation of gradual fading, task-focused feedback, representation shifts, and separation between tutor moves and human learning (Sawyer, 2006; Hattie & Timperley, 2007; Ainsworth, 2006; Käser & Alexandron, 2024).

Prior benchmarks — MathTutorBench (Macina et al., 2025), Bridge (Wang et al., 2024), MRBench (Maurya et al., 2025), and TutorBench (Srinivasa et al., 2025) — define English rubrics, while decoupling systems (DICE, Pal et al., 2026; StratL, Puech et al., 2025; ScaffoldLM, Li et al., 2026a) separate control from generation and multi-turn studies track instruction decay (Laban et al., 2025; LongTutor, Li et al., 2026b). Tutor-Bench v4.5 tests small Flash models across 16- and 24-turn German dialogues from bit-identical forks against explicit baselines (short core prompt, neutral placebo, wrong hint, full rules) under cross-family judging.

---

## 2. Measurement Design and Setup

Four core packages (**KP**) build sequentially: **KP4** checks the AI judges on English expert/novice pairs, **KP1a** profiles open 16-turn dialogues, **KP2a** compares scaffolding arms from identical prefixes across two runs of the same grid — **Run A (Nov 24, `L2`)** and **Run B (Nov 25, follow-up)** — and **KP2b** tracks 24-turn rule compliance. Agreement uses nominal **Krippendorff's α**.

### 2.1 Three-Layer Evidence Model and Two-Step Gate

1. **Level A (Deterministic):** Cell completions, aborts, coach format failures, and text detectors (`DOPPELFRAGE` multi-question flags, hint overlap).
2. **Exploratory Two-Family AI Jury:** `claude-sonnet-5-5` (low) and `gpt-6.2-sol` (low) blindly rate tutor turns on case-specific binary checks (Sirdeshmukh et al., 2025; Lee et al., 2024). The primary score (`prueffrage_d4_gated`) combines the pedagogical check (`prueffrage_binaer`) with a factual gate (`D4_fachlichkeit`, Feuer et al., 2025; Daheim et al., 2024) in a strict **two-step order**:
   - **Step 1 — Exclude unassessable pedagogical checks first:** If `prueffrage_binaer == "nicht_beurteilbar"`, exclude the turn from the denominator regardless of `D4_fachlichkeit` (in KP1a, 3 Claude and 6 Codex verdicts on dual-jury routes combine an unassessable pedagogical check with a factual error and are excluded here).
   - **Step 2 — Score remaining turns:** Among assessable turns, score **Pass (yes)** if `prueffrage_binaer == "ja"` **and** `D4_fachlichkeit != "nicht_zutreffend"` (including turns where `D4_fachlichkeit == "nicht_beurteilbar"` because no factual claim was made). Otherwise score **Failure (no)** (`prueffrage_binaer == "nein"` or `D4_fachlichkeit == "nicht_zutreffend"`). Factual errors on assessable turns remain in the denominator as failures.
   **Family separation** forbids any judge from sharing a model family with the evaluated tutor or coach (Panickssery et al., 2024; Verga et al., 2024). Because LLM consensus does not prove human validity (Cohn et al., 2026), calibrated Level B stays locked until German human blind coding completes.
3. **External Authorship Anchor (KP4):** Paired English expert- vs. novice-authored math replies from Bridge (Wang et al., 2024).

### 2.2 Models, Arms, Cases, and Methodological Constraints

- **Models & roles:** KP1a evaluates five Flash tutors (`meta/muse-ember`, `google/gemini-3.8-flash`, `openai/gpt-6-luna`, `qwen/qwen3.8-flash`, `z-ai/glm-5.3-flash`) plus a separate frontier panel (`GPT-6.1 Terra`, `Claude Sonnet 5.5` v1/v2, single cross-family judge). KP2a and KP2b evaluate `muse-ember` and `qwen3.8-flash`. Learner simulation / state judging crossed `gpt-6.2-sol` and `claude-sonnet-5-5` in KP1a (`gpt-6-luna` used Claude only to keep OpenAI separate), and used `claude-opus-5-5` (Run A) vs. `claude-sonnet-5-5` low (Run B) in KP2a/KP2b. The live coach used `gpt-6.2-sol` (max 80 `regex-v1` tokens; Codex judge excluded).
- **Scaffolding arms (exact texts in Appendix A):** **Fixed hint** (`p1_hinweis`, TTL = 1 turn), **Core prompt** (`p1_kern`, short baseline), **Full rules** (`p6_voll`, core + 453-token rule list), **Extra reasoning** (`p1_reasoning`, `1024` Qwen / `medium` Muse), **Placebo** (`p1_placebo`, length-matched neutral note), **Live coach** (`p1_frontier_coach`, live JSON hint, Claude-only jury), and **Wrong hint** (`p1_falschhinweis`, swapped mastered/open hint in T2).
- **Frozen prefix cases (KP2a, 150 cells/run = 2 models × 6 arms × 3 seeds + 6 Wrong hint in T2):**
  - **T2 (`STOP_DRIFT`, Turn 12, Attention):** Close a 3-turn math tangent in one sentence without jargon and return to Transformer overview.
  - **T3 (`HOLD_LEAD`, Turn 10, Fractions):** State common-denominator mastery and pose an unlike-denominator task.
  - **T7 (`CHECK_EVIDENCE`, Turn 8, Python lists):** Challenge unproven *"ok, sounds logical"* on `b = a` aliasing with an application task.
  - **T8 (`SWITCH_MODALITY`, Turn 8, Fractions):** After repeated impasse on 1/2 + 1/3, switch from verbal text to another representation and pose a small task without solving it.
- **24-turn dialogue (KP2b, Case T12 `KEEP_CONTRACT`):** 36 episodes (2 models × 6 arms × 3 seeds) on Python lists with a scripted Turn 3 tutor commitment (*"I will always ask for your guess first and ask exactly one question per turn"*, German: *„Ich frage immer zuerst nach deiner Vermutung und stelle genau eine Frage pro Zug.“*), checkpoints at Turns 8, 13, 18, 23, and hold Turn 24.
- **Constraints:** Run A (Nov 24 `L2`, 146 primary turns) and Run B (Nov 25, 145 primary turns, quote-normalizer fix + Sonnet low state judge; offline replay rescued 41/41 stored quote aborts) execute the same 150-cell grid (150/150 identical prefixes, 126/142 identical start tuples) — measuring stability, not independent samples. Pre-registered rule K5 locked contrasts after Live coach lost 5/24 (20.8% > 10%) cells to format errors. Placebo fell below Core in both runs. We omit binomial CIs on three-valued means (0 / 0.5 / 1) and report answer means, judge bounds (*Both Yes* / *≥1 Yes*), separate lenses, and all clusters.

---

## 3. External Judge Sanity Check (KP4 Bridge)

Judges blindly rated English expert- vs. novice-authored math replies from **Bridge** (Wang et al., 2024; 0–4 Likert, balanced ab/ba, seed 42). All four preferred experts well above 50% with **0 technical errors**:

| Judge | Subset | Expert wins | Ties | Novice | Errors | Expert win (95% CP) | Expert win (excl. ties) | Non-tie rate | `overlap_145` (Win / Excl. ties) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **`gpt-6.2-sol` (low)** | `test_210` | 155/210 | 41 | 14 | 0 | **73.8%** [67.3–79.6%] | 91.7% (155/169) | 80.5% (169/210) | **74.5%** / 92.3% |
| **`claude-sonnet-5-5` (low)** | `test_210` | 148/210 | 51 | 11 | 0 | **70.5%** [63.8–76.6%] | **93.1%** (148/159) | 75.7% (159/210) | **72.4%** / **92.9%** |
| **`z-ai/glm-5.3-flash`** | 482 | 324/482 | 93 | 65 | 0 | **67.2%** [62.8–71.4%] | 83.3% (324/389) | 80.7% (389/482) | 69.7% / 84.9% |
| **`qwen/qwen3.8-flash`** | 482 | 293/482 | 149 | 40 | 0 | **60.8%** [56.3–65.2%] | 88.0% (293/333) | 69.1% (333/482) | 65.5% / 86.4% |

- **Paired checks:** Sol and Sonnet are indistinguishable on `test_210` (p = 0.410, McNemar; 68.1% three-way agreement). GLM's win lead over Qwen on 482 pairs (p = 0.0090) vanishes once ties (149 vs. 93) are excluded (p = 0.286, n = 289). Three-way agreement on `overlap_145` spans **67.6%–71.0%** (heatmap in Explorer).
- **Limits:** Bridge reflects expert authorship, not quality ratings; 109/482 and 23/210 pairs share dialogue context; English single turns do not replace German multi-turn calibration (Fu & Liu, 2025).

---

## 4. Open 16-Turn Tutoring Profiles (KP1a)

Five Flash models ran four 16-turn German scenarios under a 199-character role prompt (36 episodes, 523/576 turns completed, 507 assessable). Differing default reasoning budgets and single-judge scoring for `gpt-6-luna` preclude a single leaderboard; we report **separate judge lenses** and episode min–max spans.

### 4.1 Core Flash Models

- **Dual-jury Krippendorff's α (4 models, n = 468, excluding `gpt-6-luna`):**
  - Binary check (`prueffrage_binaer`): **82.8%**, **α = 0.642** (n = 447).
  - Factual correctness (`D4_fachlichkeit`): **67.0%**, **α = 0.336** (n = 457).
  - Answer leakage (`preisgabe`): **72.8%**, **α = 0.425** (n = 427).
  - D4-gated check (`prueffrage_d4_gated`): **76.1%**, **α = 0.476** (n = 447) — pulled below 0.65 by low factual agreement.

| Model (effort) | Turns (Ep.) | Check · **Claude** | Check · **Codex** | **Answer mean** (ep. span) | D4 factual | Leakage ↓ |
|---|---:|---:|---:|---:|---:|---:|
| **`meta/muse-ember`** (minimal) | 113 (8) | 59.3% (64/108) | 39.8% (43/108) | 49.1% (8 ep.: 19–100%) | 70.7% | 36.2% |
| **`openai/gpt-6-luna`** (off, 1 sim.) | 55 (4) | 56.9% (29/51) | *excluded (family)* | 56.9%\* (4 ep.: 47–83%) | 94.5%\* | 37.3%\* |
| **`google/gemini-3.8-flash`** (low) | 114 (8) | 53.7% (58/108) | 36.4% (40/110) | 44.5% (8 ep.: 25–60%) | 71.2% | 20.8% |
| **`qwen/qwen3.8-flash`** (budget 256) | 126 (8) | 29.0% (36/124) | 22.8% (28/123) | 25.6% (8 ep.: 13–38%) | 41.4% | 36.7% |
| **`z-ai/glm-5.3-flash`** (low) | 115 (8) | 25.0% (28/112) | 16.4% (18/110) | 20.5% (8 ep.: 0–36%) | 34.9% | 52.5% |

*\* `gpt-6-luna` has Claude verdicts only; pooling inflates it by omitting the stricter Codex lens. Muse and Gemini average higher under both judges, yet episode ranges overlap heavily and Codex scores up to **19.4 pp** below Claude (`muse-ember`).*

### 4.2 Frontier Reference Panel (Separate Setup, Single Judge)

| Reference run | Turns ok | Single juror | Check (k/n) | D4 factual | Fit | Leakage ↓ | Sycophancy ↓ | `DOPPELFRAGE` |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| **`GPT-6.1 Terra`** | **64/64** | `claude-sonnet-5-5` | 60.0% (36/60) | **100%** (62/62) | 73.4% (47/64) | **19.6%** (11/56) | 0.0% (0/10) | **29.7%** (19/64) |
| *`Terra` matched to `Sonnet v1`* | 34/34 | `claude-sonnet-5-5` | 58.1% (18/31) | 100% (33/33) | 70.6% (24/34) | 25.8% (8/31) | 0.0% (0/8) | — |
| **`Claude Sonnet 5.5` v1** | 34/64 | `gpt-6.2-sol` | 83.9% (26/31) | **100%** (34/34) | 94.1% (32/34) | 44.1% (15/34) | 0.0% (0/10) | 76.5% (26/34) |
| **`Claude Sonnet 5.5` v2** | 32/64 | `gpt-6.2-sol` | 83.3% (25/30) | **100%** (32/32) | 93.8% (30/32) | 25.0% (8/32) | 0.0% (0/9) | 84.4% (27/32) |

Both frontier models hit 100% factual accuracy and 0% sycophancy; under Claude, Terra (60.0%) sat near top Flash routes. All eight Sonnet episodes halted early on state-judge errors (Turns 13 / 3 / 13 / 5 in v1; 3 / 3 / 13 / 13 in v2), and Sonnet still flagged high `DOPPELFRAGE` (76.5% / 84.4%). Full panel in Explorer.

---

## 5. Situational Scaffolding at Identical Prefixes (KP2a)

> **Contrast status:** Live coach lost **5/24 (20.8% > 10%)** cells to format failures in Run B, locking pre-registered contrasts (K5), and had Claude judging only. Run B (145 turns) and Run A (`L2`, 146 turns) run the same 150-cell grid (inter-jury α = 0.825 Run B, 0.744 Run A, 0.785 combined on non-coach arms).

### 5.1 Arm Summary Across Both Executions

| Arm (KP2a) | Run B (n · mean · Cl/Cx) | Run A · `L2` (n · mean · Cl/Cx) | **Combined** | **Mean** | **Both / ≥1 Yes** | **Cl / Cx** | **Best–Worst** |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Fixed hint** (`p1_hinweis`) | 24 · 62.5% · 71/54% | 24 · 68.8% · 67/71% | 48 / 48 | **65.6%** | 56.2% / 75.0% | 68.8 / 62.5% | 65.6–65.6% |
| **Core prompt** (`p1_kern`) | 24 · 58.3% · 58/58% | 24 · 50.0% · 46/54% | 48 / 48 | **54.2%** | 50.0% / 58.3% | 52.1 / 56.2% | 54.2–54.2% |
| **Extra reasoning** (`p1_reasoning`) | 24 · 39.6% · 42/38% | 24 · 58.3% · 63/54% | 48 / 48 | **49.0%** | 43.8% / 54.2% | 52.1 / 45.8% | 49.0–49.0% |
| **Full rules** (`p6_voll`) | 24 · 41.7% · 42/42% | 23 · 54.3% · 52/57% | 47 / 48 | **47.9%** | 46.8% / 48.9% | 46.8 / 48.9% | 46.9–49.0% |
| **Live coach** (`p1_frontier_coach`, Cl) | 19 · 42.1% · 42/— | 21 · 52.4% · 52/— | 40 / 48 | **47.5%** | 47.5% *(1 judge)* | 47.5% / excl. | 39.6–56.2% |
| **Placebo** (`p1_placebo`) | 24 · 37.5% · 46/29% | 24 · 41.7% · 42/42% | 48 / 48 | **39.6%** | 33.3% / 45.8% | 43.8 / 35.4% | 39.6–39.6% |
| **Wrong hint** (`p1_falschhinweis`, T2) | 6 · 0.0% · 0/0% | 6 · 16.7% · 33/0% | 12 / 12 | **8.3%** | 0.0% / 16.7% | 16.7 / 0.0% | 8.3–8.3% |

Fixed hint leads overall in both runs, while neutral Placebo trails Core in **both** (−20.8 pp Run B, −8.3 pp Run A). Extra reasoning flips sign against Core across runs.

### 5.2 Pre-Registered Rules and Hypotheses (H1–H6)

| Rule / Hypothesis | Planned criterion | Descriptive observation | Status |
|---|---|---|---|
| **Censoring lock (K5)** | ≤ 10% lost/arm | Live coach lost **5/24 (20.8% > 10%)** to format errors in Run B | **Triggered → locked** |
| **Human calibration** | α ≥ 0.65, bias ≤ 10 pp | German blind coding pending | **Pending → locked** |
| **H1 (Early ≤ T8)** | Full rules ≥ Fixed hint | Reversed: Fixed hint 17.5/24 vs. Full rules 13.5/23 (T8 drop: 1.5/11) | **Locked** |
| **H2 (Late ≥ T15)** | Fixed hint > Full rules | Same direction on small n: T23 2.0/5 vs. 0.0/3 (T24 2.5/5 vs. 0.0/3) | **Locked** |
| **H3 (T2 specificity)** | Hint − Wrong ≥ 2/6 | Floor effect: +0.5/6 in both runs (Core 0.0/6) | **Uninformative** |
| **H4 (Fine-tuned)** | SFT/RL vs. Flash | Out of scope for v4.5 | **Out of scope** |
| **H5 (Coach stability)** | 3-seed variance | 9/9 format failures across KP2a/KP2b; full model reversal | **Descriptive** |
| **H6 (Equivalence)** | abs(Full − Core) ≤ 3/30 | Run B −4.0 (n=24), Run A +0.5 (n=23/24); Placebo failed neutrality | **Locked** |

### 5.3 Individual Clusters and Leave-One-Case-Out Sensitivity

All 50 populated cells (`Combined [Run B + Run A] (Run B alone)`):

| Cluster | `p1_hinweis` | `p1_kern` | `p6_voll` | `p1_reasoning` | `p1_placebo` | `p1_frontier_coach` | `p1_falschhinweis` |
|---|---:|---:|---:|---:|---:|---:|---:|
| **T2 · Muse-Ember** | 1.0/6 (0.0/3) | 0.0/6 (0.0/3) | 0.0/6 (0.0/3) | 0.0/6 (0.0/3) | 0.0/6 (0.0/3) | 0.0/6 (0.0/3) | 0.5/6 (0.0/3) |
| **T2 · Qwen 3.8 Flash** | 1.0/6 (0.5/3) | 0.0/6 (0.0/3) | 0.0/6 (0.0/3) | 0.0/6 (0.0/3) | 0.0/6 (0.0/3) | 0.0/5 (0.0/2) | 0.5/6 (0.0/3) |
| **T3 · Muse-Ember** | **6.0/6** (3.0/3) | 1.5/6 (0.0/3) | 5.0/6 (2.0/3) | 1.5/6 (0.5/3) | 1.5/6 (0.0/3) | 1.0/5 (1.0/3) | — |
| **T3 · Qwen 3.8 Flash** | **6.0/6** (3.0/3) | 4.0/6 (3.0/3) | 4.0/6 (2.0/3) | 3.0/6 (1.5/3) | 0.0/6 (0.0/3) | 2.0/4 (0.0/2) | — |
| **T7 · Muse-Ember** | 6.0/6 (3.0/3) | 6.0/6 (3.0/3) | 6.0/6 (3.0/3) | 6.0/6 (3.0/3) | 5.5/6 (2.5/3) | 5.0/5 (3.0/3) | — |
| **T7 · Qwen 3.8 Flash** | 5.5/6 (2.5/3) | 6.0/6 (3.0/3) | 6.0/6 (3.0/3) | 5.0/6 (2.0/3) | 3.5/6 (2.0/3) | 4.0/4 (1.0/1) | — |
| **T8 · Muse-Ember** | 2.0/6 (1.5/3) | 5.5/6 (3.0/3) | **1.5/6** (0.0/3) | 5.5/6 (2.5/3) | 4.5/6 (2.5/3) | 5.0/5 (2.0/2) | — |
| **T8 · Qwen 3.8 Flash** | 4.0/6 (1.5/3) | 3.0/6 (2.0/3) | **0.0/5** (0.0/3) | 2.5/6 (0.0/3) | 4.0/6 (2.0/3) | 2.0/6 (1.0/3) | — |

T2 sits at a floor, T7 near ceiling, T3 carries the Fixed hint lead (12/12 vs. 5.5/12 Core), and T8 flips the pattern (Full rules 1.5/11; Fixed hint 6.0/12 vs. Core 8.5/12).

| Case selection | Fixed hint | Core prompt | Placebo | Hint − Core | Hint − Placebo | Placebo − Core | Hint − Core (ans.) |
|---|---:|---:|---:|---:|---:|---:|---:|
| All 4 cases | 31.5/48 (65.6%) | 26.0/48 (54.2%) | 19.0/48 (39.6%) | +11.5 pp | +26.0 pp | −14.6 pp | +5.5 ans. |
| Excluding T2 | 29.5/36 (81.9%) | 26.0/36 (72.2%) | 19.0/36 (52.8%) | +9.7 pp | +29.2 pp | −19.4 pp | +3.5 ans. |
| Excluding T3 | 19.5/36 (54.2%) | 20.5/36 (56.9%) | 17.5/36 (48.6%) | −2.8 pp | +5.6 pp | −8.3 pp | −1.0 ans. |
| Excluding T7 | 20.0/36 (55.6%) | 14.0/36 (38.9%) | 10.0/36 (27.8%) | +16.7 pp | +27.8 pp | −11.1 pp | +6.0 ans. |
| Excluding T8 | 25.5/36 (70.8%) | 17.5/36 (48.6%) | 10.5/36 (29.2%) | +22.2 pp | +41.7 pp | −19.4 pp | +8.0 ans. |

Without Case T3, the two runs reverse: Run B drops to 9.0/18 = 50.0% vs. 11.0/18 = 61.1% (**−11.1 pp**), while Run A stays ahead at 10.5/18 = 58.3% vs. 9.5/18 = 52.8% (**+5.6 pp**).

### 5.4 Mechanism Notes

- **Case T8 (`p6_voll`):** Raw outputs (e.g., Qwen seed 42: *"Picture 1/2 as a pizza. Half a pizza is 3 slices of a 6-slice pizza..."*) adopt visual analogies yet work out steps or solve 1/2 + 1/3 = 5/6 outright (Muse seed 44), while Qwen seeds 43–44 fail arithmetically. Separating prompt length from rule wording remains open.
- **Live coach:** Model ordering flipped completely between runs (**Muse 6/11 vs. Qwen 2/8** in Run B; **Muse 5/10 vs. Qwen 6/11** in Run A). All 9/9 format failures narrowly exceeded the `regex-v1` token cap without retry; an offline retry guard fixed 9/9 stored failures (live check open).
- **Surface checks:** Post-hoc scan flagged **113/566 (20.0%)** Run B turns for `DOPPELFRAGE`; only **1** `hinweis_leck` hit occurred.

---

## 6. 24-Turn Rule Compliance and Checkpoint Spikes (KP2b Case T12)

Across 36 planned 24-turn Python lists episodes (scripted Turn 3 one-question tutor commitment), **19/36** reached Turn 24 — 17 ended early (8 state-judge, 4 coach format, 3 rate-limit, 2 tutor errors) — yielding **599/864** visible turns and 39 Turn 23–24 jury answers:

| Arm (KP2b) | ok/6 | Turns | All turns | Turn 3+ ↓ | Turn 4+ ↓ | Leak | Turn 23 primary | Turn 24 hold |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Fixed hint** (`p1_hinweis`) | 5/6 | 121 | 51/121 (42.1%) | 42/110 (38.2%) | **40/105** (38.1%) | 1 / 16\* | 40.0% (2.0/5) | **50.0%** (2.5/5) |
| **Placebo** (`p1_placebo`) | 3/6 | 123 | 58/123 (47.2%) | 50/111 (45.0%) | **46/105** (43.8%) | 0 / 0 | 37.5% (1.5/4) | 33.3% (1.0/3) |
| **Extra reasoning** (`p1_reasoning`) | 5/6 | 122 | 77/122 (63.1%) | 65/110 (59.1%) | **62/105** (59.0%) | 0 / 0 | 20.0% (1.0/5) | 20.0% (1.0/5) |
| **Core prompt** (`p1_kern`) | 3/6 | 83 | 31/83 (37.3%) | 24/72 (33.3%) | **23/67** (34.3%) | 0 / 0 | 33.3% (1.0/3) | 0.0% (0.0/3) |
| **Full rules** (`p6_voll`) | 3/6 | 84 | 38/84 (45.2%) | 29/72 (40.3%) | **26/67** (38.8%) | 0 / 0 | 0.0% (0.0/3) | 0.0% (0.0/3) |
| **Live coach** (`p1_frontier_coach`) | 0/6 | 66 | 23/66 (34.8%) | 14/54 (25.9%) | **12/48** (25.0%) | 0 / 0 | No cell reached (0/6) | No cell reached (0/6) |
| **Total (36/36)** | **19/36** | **599** | **278/599** (46.4%) | **224/529** (42.3%) | **209/497** (42.1%) | **1 / 16** | **20 / 36** | **19 / 36** |

*\* Single `hinweis_leck` hit: Qwen Fixed hint seed 43, Turn 8 (16 clean turns followed).*

- **Checkpoint spikes (Turns 4–24):** `DOPPELFRAGE` flagged **209/497 (42.1%)** post-commitment turns (Turns 1–2 context: 54/70 = 77.1%; Turn 3: 15/32), jumping to **66/90 (73.3%)** on checkpoints (Turns 8, 13, 18, 23) vs. **143/407 (35.1%)** on other turns (routine Turn 20 also reached 13/21 = 61.9%). Hint-free Core triggered 3/3 on every checkpoint. Fixed turn positions, shrinking survivors (36 → 19; Live coach had 0/6 at Turns 23–24), and no no-commitment control arm prevent causal attribution.
- **Turn 23–24 jury (39 answers):** Inter-jury agreement reached **89.7%** on primary check (**α = 0.734**), **87.2%** on commitment kept (**α = 0.678**), and 39/39 `no` on meta-leaks. Surviving denominators are too small to establish retention.

---

## 7. Limitations and Software Separation

1. **Human calibration pending:** All German AI-jury scores remain exploratory until human blind coding passes α ≥ 0.65, FNR/FPR ≤ 15%, and absolute bias ≤ 10 pp (Cohn et al., 2026).
2. **Process behavior ≠ human learning:** Simulated learners measure tutor moves only; learning gains and transfer require human studies (Sawyer, 2006; Käser & Alexandron, 2024; Scarlatos et al., 2026).
3. **Open ablations:** Future runs should compare hints against both Core and Placebo, isolate prompt length from rule wording in T8, and test the retry-hardened coach live.
4. **Separation from `ai-tutor-bench` v5:** This paper documents the dated **v4.5** laboratory study; the public `ai-tutor-bench` (`0.1.0`) package ships the newer **v5** offline suite (161 synthetic cells) and does not reproduce v4.5 results.

---

## 8. References

- Ainsworth, S. (2006). DeFT: Learning with multiple representations. *Learning and Instruction*, 16(3), 183–198.
- Asher, M. W. et al. (2026). Designing LLM Tutoring Around Scaffolded Error Correction. [arXiv:2611.20061](https://arxiv.org/abs/2611.20061).
- Bassner, P. et al. (2025). Dissociation of performance and learning in AI-supported programming education. *Computers and Education: AI*, 10, 100537.
- Bastani, H. et al. (2025). Generative AI without guardrails can harm learning. *PNAS*, 122(26), e2422633122.
- Cohn, C. et al. (2026). Agreement Is Not Validity: Cross-Model LLM Consensus in K-12 Math Tutoring. [arXiv:2610.08703](https://arxiv.org/abs/2610.08703).
- Daheim, N. et al. (2024). Stepwise Verification and Remediation of Student Reasoning Errors. *EMNLP 2024*.
- Feuer, B. et al. (2025). Style Outweighs Substance: Failure Modes of LLM Judges. *ICLR 2025*.
- Fu, X. & Liu, W. (2025). How Reliable is Multilingual LLM-as-a-Judge? *Findings of EMNLP 2025*.
- Hattie, J. & Timperley, H. (2007). The power of feedback. *Review of Educational Research*, 77(1), 81–112.
- Käser, T. & Alexandron, G. (2024). Simulated Learners in Educational Technology. *IJAIED*, 34(2).
- Kestin, G. et al. (2025). AI tutoring outperforms in-class active learning. *Scientific Reports*, 15, 17458.
- Laban, P. et al. (2025). LLMs Get Lost in Multi-Turn Conversation. [arXiv:2505.06120](https://arxiv.org/abs/2505.06120).
- Lee, S. et al. (2026). LLM Pedagogical Behavior in AI Tutoring Interactions. [arXiv:2608.22993](https://arxiv.org/abs/2608.22993).
- Lee, Y. et al. (2024). CheckEval: Evaluating text generation using checklists. [arXiv:2403.18771](https://arxiv.org/abs/2403.18771).
- Li, Z. et al. (2026a). ScaffoldLM: Planning-Guided Tutoring with Assessment-Driven Memory. *ACL 2026*.
- Li, N. et al. (2026b). LongTutor: Long-term Personalized Tutoring. *ACL 2026*.
- Macina, J. et al. (2025). MathTutorBench: Open-ended Pedagogical Capabilities of LLM Tutors. *EMNLP 2025*.
- Maurya, K. K. et al. (2025). MRBench: Evaluation Taxonomy for AI Tutors. *NAACL 2025*.
- Pal, S. et al. (2026). DICE: Decoupling Capability from Intervention Necessity. [arXiv:2610.04825](https://arxiv.org/abs/2610.04825).
- Panickssery, A. et al. (2024). LLM Evaluators Recognize and Favor Their Own Generations. *NeurIPS 2024*.
- Puech, R. et al. (2025). StratL: Pedagogical Steering with Productive Failure. *Findings of ACL 2025*.
- Sawyer, R. K. (Ed., 2006). *The Cambridge Handbook of the Learning Sciences*. Cambridge University Press.
- Scarlatos, A. et al. (2026). Simulated Students in Tutoring Dialogues: Substance or Illusion? [arXiv:2601.04025](https://arxiv.org/abs/2601.04025).
- Sirdeshmukh, V. et al. (2025). MultiChallenge: Multi-Turn Conversation Evaluation. *Findings of ACL 2025*.
- Srinivasa, R. S. et al. (2025). TutorBench: Assessing Tutoring Capabilities of LLMs. [arXiv:2510.02663](https://arxiv.org/abs/2510.02663).
- Verga, P. et al. (2024). Replacing Judges with Juries. [arXiv:2404.18796](https://arxiv.org/abs/2404.18796).
- Wang, R. E. et al. (2024). Bridge: Bridging the Novice-Expert Gap in Math Remediation. *NAACL 2024*.
- Zhao, J. et al. (2026). Answer Leakage Robustness of LLM Tutors. *ACL 2026*.

---

## Appendix A: Experimental Prompt, Hint, and Placebo Texts

All treatments were delivered in German; English translations are shown below:

- **Core prompt (`p1_kern`):** *"You are a tutor in a German-language learning dialogue. The learner wants to understand the topic independently and explain it without you. You lead the conversation: keep track of the learning goal and what has been demonstrated, and set the next step yourself. Speak only as the tutor and leave the learner's next turn open."*
- **Full rules (`p6_voll`, 453 `regex-v1` tokens, 2,329 characters):** Prepends `p1_kern` verbatim, then adds seven situational action rules (attempt/justification, unproven agreement, first impasse, repeated impasse / representation shift with small follow-up task, digression, completed section, frustration/shortcut), a factual-judgment-before-tone block, and periodic progress summaries.
- **Fixed one-turn hints (TTL = 1 turn, translated from German):**
  - **Case T2 (`STOP_DRIFT`):** *"Status: Learning goal is an overview-level understanding of attention in Transformers. Demonstrated: selecting relevant words. Open: interaction with the rest of the model. The last three turns went deeper than this level. Close the detail in one sentence and move to the interaction with the rest of the model."*
  - **Case T2 Wrong hint (`p1_falschhinweis`):** Swaps "demonstrated" and "open" — directs the tutor back to *selecting relevant words* (already mastered) instead of the rest of the Transformer.
  - **Case T3 (`HOLD_LEAD`):** *"The learner just solved common-denominator addition correctly with justification. State in one sentence what that demonstrates, and pose the next step to two unlike denominators yourself."*
  - **Case T7 (`CHECK_EVIDENCE`):** *"The learner agreed but has not demonstrated understanding yet. Pose a small application task on mutable Python lists and shared references before moving on."*
  - **Case T8 (`SWITCH_MODALITY`):** *"The learner failed to understand the same point a second time. Your previous approach was a verbal explanation. Switch to another approach now: a small-number example or text sketch. Return a small task on it afterward."*
  - **Case T12 (`KEEP_CONTRACT`):** *"Commitment from Turn 3: I will always ask for your guess first and ask exactly one question per turn. It still applies."*
- **Length-matched neutral placebo (`p1_placebo`, Case T8 wording):** *"System note on conversation flow: This is an ongoing German-language learning chat with full context. All previous messages remain unchanged in the same order. Formulate your regular reply now. The text remains part of the chat as before."*
