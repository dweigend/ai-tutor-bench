# Tutor-Bench v4.5: Measuring Multi-Turn Tutoring Behavior and Situational Scaffolding in Small LLMs

- **Author:** David Weigend · **AI assistance:** AI coding and review tools assisted with harness engineering, verification scripts, editing, and independent audits under human specification and verification.
- **Document type:** Technical benchmark report (Revision v1.1 · English edition prior to human gold calibration)
- **Study date:** November 26, 2026 · **English revision:** November 28, 2026 · **Study freeze:** `v4.5` (`3e01a5a5…`), runtime fix `3390b13`
- **Companion pages:** [Executive Results Report (5 Figures)](./results/index.html) · [Interactive Data Explorer](./explorer/index.html) · [AI Tutor Bench README (v5 Harness)](../../README.md) · [Reproducibility & Adapter Guide](../reproducibility.md)

> **Scope and epistemic boundary (applies to every result in this report):**
> This report separates three evidence layers: **(1) Level A · Deterministic** (denominators, technical failures, live API spend, SHA-256 digests, offline replay, and rule-based text detectors), **(2) Exploratory · Uncalibrated Two-Family AI Jury** (`claude-sonnet-5-5` and `gpt-6.2-sol`, strictly separated from the evaluated model family; German human blind coding is still pending, so calibrated Level B remains locked), and **(3) External English Authorship Reference** (KP4 Bridge pairs authored by human experts vs. novices; local KP5 MathTutorBench pre-check only, external API calls blocked over upstream license ambiguity). Every dialogue metric measures **tutoring behavior with simulated learners — not human learning gains, retention, or transfer** (Käser & Alexandron, 2024). Five of 24 live coach calls in KP2a failed the format check (20.8% > 10%), triggering the automatic pre-registration censoring lock; all arm contrasts are therefore descriptive, and the live coach arm was scored by Claude only.

---

## Abstract

Small language models solve math and programming problems reliably, yet often break down as multi-turn tutors: they reveal solutions early, drop conversation rules, or degrade under long static prompts. **Tutor-Bench v4.5** (an independent multi-turn laboratory study, distinct from Scale AI's TutorBench, Srinivasa et al., 2025) evaluates low-cost Flash models across 16- and 24-turn German tutoring dialogues using SHA-256-frozen prefix forks, family-separated learner simulation and judging, deterministic surface checks, and provider-ledger cost tracking ($0.982986 total OpenRouter live spend across the Nov 24–25 core runs and Nov 25–26 follow-up runs).

Four exploratory findings emerge across four linked core evaluation packages (an English expert-authorship judge check, open 16-turn profiles, frozen prefix-fork scaffolding across two executions, and 24-turn rule compliance). First, fixed one-turn hints led overall only because of unanimous scores in a single case (holding the pedagogical lead in fraction addition); excluding that case, the two executions point in opposite directions against a short core prompt. Second, a length-matched neutral placebo scored below the short core prompt in both executions, and a long static rule prompt behaved case-by-case — helping on holding the lead yet dropping sharply when switching representation after repeated fraction impasse. Third, in open 16-turn dialogues, Muse-Ember and Gemini 3.8 Flash averaged higher than Qwen 3.8 Flash and GLM 5.3 Flash under both judges, though episode ranges overlapped substantially and Claude and Codex diverged by up to 19.4 percentage points (Krippendorff's α = 0.476 on the gated score). Fourth, after a scripted Turn 3 one-question tutor commitment, deterministic multi-question flags clustered heavily at the four scripted checkpoint turns (73.3% vs. 35.1% on other post-commitment turns). Because live coach censoring locked pre-registered contrasts and German human calibration remains pending, all AI-jury scores stay exploratory and measure simulated tutoring behavior rather than human learning.

---

## 1. Motivation and Related Work

Field studies point to a clear tension when deploying generative AI in education. Unrestricted chatbot access lifts short-term practice scores while reducing unaided exam performance (−17% relative to control for GPT Base in Bastani et al., 2025; no net pre/post learning gain despite higher practice scores in Bassner et al., 2025). By contrast, pedagogically structured tutors achieve measurable immediate post-test gains (0.63 SD in a university physics RCT, Kestin et al., 2025; +0.24 SD on near transfer, Asher et al., 2026). Observational studies illustrate why default assistants fall short: in Lee et al.'s (2026) analysis of GPT-4o mini tutoring interactions, 95.5% of observed responses solved (55.2%) or directly explained (40.3%) the problem rather than scaffolding student reasoning, and even fine-tuned tutor models disclose solutions in 70–83% of adversarial pressure dialogues (Zhao et al., 2026).

Four tutoring principles from the learning sciences (Sawyer, 2006; Houdé & Borst, 2022) require multi-turn evaluation:

1. **Gradual fading tied to learner attempts** instead of premature worked solutions or service menus (Sawyer, 2006, pp. 72, 153; Patall et al., 2014).
2. **Task- and process-focused feedback** instead of generic praise or sycophantic agreement with misconceptions (Hattie & Timperley, 2007; Sharma et al., 2024).
3. **Guided representation shifts under persistent impasse** without overwhelming small models with long static rule lists (Ainsworth, 2006; Leutner & Biele, 2025; Jaroslawicz et al., 2025).
4. **Strict separation between observed tutoring behavior and verified human learning** (Sawyer, 2006, p. 152; Domínguez Figaredo & Fernández De la Cruz, 2026; Käser & Alexandron, 2024).

### Positioning Against Existing Benchmarks and Scaffolding Systems

| Reference | Core contribution | How Tutor-Bench v4.5 complements it |
|---|---|---|
| **SWE-bench** (Jimenez et al., 2024), **SWE-bench Verified** (OpenAI, 2024), & **DeepSWE** (Agentica, 2025) | Deterministic execution verification, human-validated subsets, open trajectories, and explicit ablations. | Brings engineering discipline (SHA-256 forks, deterministic Level A, provider cost ledger, automatic censoring locks) to open teaching dialogues where unit tests cannot score pedagogy alone. |
| **Artificial Analysis** (2025/2026) | Independent quality, latency, and cost transparency across providers. | Keeps judge lenses strictly separate and avoids composite leaderboards whenever simulators, wrappers, or judges differ across models. |
| **MathTutorBench** (Macina et al., 2025), **Bridge** (Wang et al., 2024), **MRBench** (Maurya et al., 2025), **TutorBench** (Srinivasa et al., 2025) | English pedagogical taxonomies, expert/novice response pairs, and case-specific rubrics. | Tests 16- to 24-turn German dialogues from bit-identical SHA-256 prefix forks across six scaffolding arms plus a wrong-hint control, using Bridge (KP4) up front as an English sanity check on the AI judges. |
| **DICE** (Pal et al., 2026), **StratL** (Puech et al., 2025), **ScaffoldLM** (Li et al., 2026a), **Progressive Help** (Arjona-Giner et al., 2026), **TRAVER** (Wang et al., 2025) | Decouple pre-turn pedagogical control and diagnosis from surface response generation. | Tests on inexpensive Flash models with explicit control arms (neutral placebo, wrong hint, full rule prompt, extra reasoning) whether one-turn hints (TTL = 1) beat a short core prompt — showing that an empty insertion can degrade responses below baseline. |
| **Multi-turn decay studies** (Laban et al., 2025; Li et al., 2024; LongTutor, Li et al., 2026b) | Document multi-turn performance decay (−39%) and persona/instruction drift after ~8 turns. | Tracks violations of a concrete Turn 3 one-question tutor commitment (`DOPPELFRAGE`) turn-by-turn across 24 turns (Case T12), separating the four scripted checkpoint turns from routine follow-ups and separating Turn 23 from the unsupported hold turn Turn 24. |

Tutor-Bench v4.5 asks one concrete systems question: *How well do fast, low-cost Flash models sustain pedagogical scaffolding across multi-turn German dialogues, where do long rule prompts or turn commitments break down, and under what methodological safeguards can situational hints be evaluated cleanly?*

---

## 2. Measurement Design, Pre-Registration, and Freeze Deviations

The evaluation separates deterministic accounting from exploratory AI ratings and external human-authored anchors. Four core evaluation packages (**KP**, from German *Kernpaket*) build sequentially: **KP4** sanity-checks the judges on English expert/novice pairs, **KP1a** profiles open 16-turn dialogues, **KP2a** isolates scaffolding arms from identical dialogue forks across two executions — **Run A (Nov 24, pre-fix, archived as `L2`)** and **Run B (Nov 25, post-fix follow-up)** — and **KP2b** measures 24-turn rule compliance. Throughout this report, inter-judge agreement is measured with **Krippendorff's α** (nominal coding unless noted). Where a multi-cell run paused on a rate limit and resumed cleanly from the next unstarted cell without duplicating API calls, we refer to each resumed execution segment as a **hop**.

### 2.1 Three-Layer Epistemic Model and Family Separation

1. **Level A (Deterministic):** Counts every quantity requiring no model judgment — completed and aborted cells, primary opportunities, state-judge errors, coach format failures, length truncations, identical outputs, live API spend reconciled against OpenRouter `/api/v1/key`, rule-based text detectors (`DOPPELFRAGE`, `SERVICE_MENUE`, `PAUSCHALLOB_PREFIX`, hint overlap), and bit-reproducible offline replay.
2. **Exploratory, Uncalibrated Two-Family AI Jury (prior to Level B):** Blindly rates individual tutor turns using `claude-sonnet-5-5` (low) and `gpt-6.2-sol` (low) on case-specific binary check questions (Sirdeshmukh et al., 2025; Lee et al., 2024). The primary composite metric (`prueffrage_d4_gated`) combines the pedagogical check (`prueffrage_binaer`) with a factual-accuracy gate (`D4_fachlichkeit`, Feuer et al., 2025; Daheim et al., 2024) in a strict **two-step execution order**:
   - **Step 1 — Exclude unassessable pedagogical checks first:** If `prueffrage_binaer == "nicht_beurteilbar"`, exclude the turn from the denominator regardless of `D4_fachlichkeit` (in KP1a, 3 Claude verdicts and 6 Codex verdicts on the four dual-jury routes combine an unassessable pedagogical check with a factual error and are excluded here).
   - **Step 2 — Score remaining turns (pass vs. failure):** Among assessable turns, score **Pass (yes)** if `prueffrage_binaer == "ja"` **and** `D4_fachlichkeit != "nicht_zutreffend"` (including turns where `D4_fachlichkeit == "nicht_beurteilbar"` because no factual claim was made). Otherwise score **Failure (no)** (`prueffrage_binaer == "nein"` or `D4_fachlichkeit == "nicht_zutreffend"`). Factual errors on assessable turns therefore remain in the denominator as scored failures.
   Strict **family separation** forbids any judge from sharing a model family with the evaluated tutor or hint-generating coach (Panickssery et al., 2024; Verga et al., 2024). Because agreement between two LLMs does not prove human construct validity (Cohn et al., 2026), calibrated **Level B** remains locked until German human blind coding completes.
3. **External Authorship Reference:** KP4 tests the judges on 482 and 210 English expert- vs. novice-authored math tutoring pairs from Bridge (Wang et al., 2024, MIT license). KP5 MathTutorBench (Macina et al., 2025) passed local verification across all 9 files (488 standard, 194 hard items; estimated $0.857), but external API calls remain blocked over conflicting upstream license notices (CC BY 4.0 vs. CC BY-SA 4.0).

### 2.2 Model Roles, Experimental Matrix, and Pre-Registered Hypotheses

The table below maps every model and CLI wrapper to its exact role across packages (complete treatment prompt, hint, and placebo texts appear in **Appendix A**):

| Role | Package(s) | Model / channel | Notes & family-separation rule |
|---|---|---|---|
| **Evaluated Flash tutors** | KP1a (5 routes), KP2a & KP2b (2 routes) | `meta/muse-ember`, `qwen/qwen3.8-flash` (all); `google/gemini-3.8-flash`, `openai/gpt-6-luna`, `z-ai/glm-5.3-flash` (KP1a only) via OpenRouter | Default reasoning budgets logged per route (KP1a); KP2a and KP2b evaluate `muse-ember` and `qwen3.8-flash`. |
| **Frontier reference tutors** | KP1a separate panel | `GPT-6.1 Terra` (`codex-cli`), `Claude Sonnet 5.5` v1/v2 (`claude-cli`) | Separate CLI wrappers and single cross-family judge; never pooled with OpenRouter routes. |
| **Live scaffolding coach** | KP2a, KP2b (Live coach arm) | `gpt-6.2-sol` via `codex-cli` (OpenAI family) | Generates one-turn German JSON hints (`coach_prompt.txt`, max 80 `regex-v1` tokens); excludes Codex judge by family separation. |
| **Learner simulator & state judge** | KP1a, KP2a, KP2b | KP1a: crossed **Cx** (`codex-cli` · `gpt-6.2-sol`) and **Cl** (`claude-cli` · `claude-sonnet-5-5`); KP2a/KP2b: `claude-opus-5-5` in Run A (Nov 24), `claude-sonnet-5-5` (low) in Run B (Nov 25 follow-up) | `gpt-6-luna` ran with Cl only (OpenAI family excluded); the Claude-low pair shares Anthropic family between learner and state judge while staying separate from OpenRouter tutors and the OpenAI coach. |
| **Two-family AI jury** | KP4, KP1a, KP2a, KP2b | `claude-sonnet-5-5` (low, `claude-cli`) and `gpt-6.2-sol` (low, `codex-cli`) | Blind per-turn binary rubric; Codex excluded on `gpt-6-luna` and the Live coach arm. |

**Scaffolding arm names (English labels used in prose vs. raw journal IDs):**

| English name | Raw journal ID | Role in KP2a / KP2b |
|---|---|---|
| **Fixed hint** | `p1_hinweis` | Short core prompt + fixed case-specific one-turn hint (TTL = 1 turn) |
| **Core prompt** | `p1_kern` | Undisturbed short German tutor prompt (baseline) |
| **Full rules** | `p6_voll` | Core prompt + full static rule list (453 `regex-v1` tokens, 2,329 characters) |
| **Extra reasoning** | `p1_reasoning` | Core prompt + higher reasoning budget (`1024` tokens Qwen, `medium` Muse) |
| **Placebo** | `p1_placebo` | Core prompt + length-matched neutral system insertion (control) |
| **Live coach** | `p1_frontier_coach` | Core prompt + live one-turn JSON hint from `gpt-6.2-sol` (Claude-only jury) |
| **Wrong hint** | `p1_falschhinweis` | Core prompt + swapped demonstrated/open hint in Case T2 only (specificity control) |

- **KP1a (Open 16-turn route profiles, 36 OpenRouter episodes):** Five Flash routes crossed with four German 16-turn scenarios (`python-listen`, `bruchaddition`, `attention-dialog`, `alphafold-dialog`) under the short role prompt `rolle` (199 characters), crossing Cx (Codex) and Cl (Claude) simulators where family separation allows. Out of 576 planned turns, 523 completed cleanly, with 3 tutor errors and 50 follow-up turns censored by premature episode stops (including 3 state-judge errors). Across allowed judge lenses, 507 answers carry an assessable primary check verdict. Because turns within a dialogue correlate, the episode (4 or 8 per route) is the higher-level cluster unit.
- **KP2a (Prefix-fork scaffolding, 150 cells per execution):** Every arm branches from the exact same SHA-256-frozen German dialogue prefix (`faelle.json`) at four distinct pedagogical moments:
  - **Case T2 (`STOP_DRIFT`, Turn 12 — Transformer attention):** An overview-level explanation drifts three turns into dot-product scaling and softmax formulas, ending with a bare learner "ok". Primary criterion: close the technical detail in one sentence, introduce no new jargon, and return to how attention fits into the rest of the Transformer.
  - **Case T3 (`HOLD_LEAD`, Turn 10 — Fraction addition):** The learner has just solved 5/12 + 2/12 with justification across several common-denominator exercises. Primary criterion: state what was demonstrated with common denominators and proactively pose a concrete question or task with unlike denominators.
  - **Case T7 (`CHECK_EVIDENCE`, Turn 8 — Python lists):** After the tutor explains `b = a` reference aliasing, the learner gives unproven agreement (*"o.k. das klingt logisch. weiter"* — *"ok, that sounds logical. continue"*). Primary criterion: pose an application task on shared list references requiring more than yes/no without giving away the answer.
  - **Case T8 (`SWITCH_MODALITY`, Turn 8 — Fraction addition):** The learner hits a repeated impasse on 1/2 + 1/3 after a verbal explanation (*"Das verstehe ich immer noch nicht."* — *"I still don't understand that."*). Primary criterion: switch from verbal explanation to another representation type (number example, text sketch, analogy, or counterexample) on the same obstacle and return a small exercise without solving the target problem.
  The grid crosses 2 Flash routes (`qwen/qwen3.8-flash`, `meta/muse-ember`) × 6 regular arms (Core prompt, Full rules, Fixed hint, Placebo, Extra reasoning, Live coach) × 3 seeds (42, 43, 44) = 144 cells. Adding 6 Wrong hint specificity controls in Case T2 brings each execution to 150 cells (600 planned tutor turns).
- **KP2b (24-turn instruction compliance in Case T12, 36 episodes):** One continuous 24-turn Python lists dialogue (`KEEP_CONTRACT`) where the runner (`with_agreement` in `pilot.py`) programmatically prepends a **scripted tutor commitment** to the tutor's Turn 3 reply (*"I will always ask for your guess first and ask exactly one question per turn"*, German: *„Ich frage immer zuerst nach deiner Vermutung und stelle genau eine Frage pro Zug.“*). Fixed learner checkpoint prompts are appended at Turns 8, 13, 18, and 23 (asking for explanations on `append`, variable reassignment, shallow copy, and nested lists), followed by an unsupported retention turn at Turn 24, across 2 models × 6 arms × 3 seeds = 36 episodes (864 planned turns). Primary criterion at Turn 23 (and separately at Turn 24): elicit the learner's prediction before explaining and ask exactly one question.
- **Pre-registered hypotheses (hash-frozen in-repo specification `v4/pilot/vorregistrierung.json`, not an external public registry; defined on 10 planned clusters / 30 primary turns per arm across KP2a + KP2b):**
  - **H1 (Early turns through Turn 8):** On early opportunities through Turn 8 (Cases T7 and T8; Case T3 sits at Turn 10 and falls outside ≤ Turn 8), Full rules performs at least as well as Fixed hint.
  - **H2 (Late turns from Turn 15):** In long dialogues (Case T12, primary Turn 23, separate hold Turn 24), Fixed hint outperforms Full rules.
  - **H3 (Content specificity in Case T2 at Turn 12):** Fixed hint beats Wrong hint by at least 2 hits out of 6.
  - **H4 (Fine-tuned SFT/RL tutor models):** Reserved in `vorregistrierung.json` for later model-training modules and out of scope for the v4.5 Flash comparison.
  - **H5 (Coach stability):** Live `gpt-6.2-sol` coach variance and over-correction are logged descriptively across three tutor seeds (with format failures also recorded).
  - **H6 (Equivalence / null rule):** If `|Full rules − Core prompt| ≤ 3` hits across 30 opportunities (and `≤ 2` per model) without triggering censoring, report no difference above threshold.
  - **Automatic censoring lock (rule K5):** If subscription-CLI censoring (`abo_zensiert`) exceeds 10% of planned cells in any arm, or differs by more than 5 pp between two arms, the runner (`pilot.py`) sets the contrast-lock flag (*descriptive denominator reporting only, no formal superiority claim*).
- **Cluster-aware reporting without false precision:** We omit binomial Wilson intervals on three-valued answer means (0 / 0.5 / 1) and pooled significance tests across dependent repeats. Instead, we report answer means, hard judge-agreement bounds (*Both Yes* to *At least 1 Yes*), separate Claude and Codex lenses, and all 8 individual Case × Model clusters.

### 2.3 Freeze Deviation Log

All eight deviations after the v4.5 freeze (`3e01a5a5…`) are disclosed alongside their verification anchors and interpretive impact:

| ID | Deviation from v4.5 freeze (`3e01a5a5…`) | Affected runs | Evidence / anchor | Interpretive consequence |
|---|---|---|---|---|
| **DEV-1** | **Quote-normalizer fix and simulator profile switch:** `normalize_quote` (`3390b13`) plus switch from `claude-opus-5-5` to `V5_CLAUDE_LOW_PAIR` (`claude-sonnet-5-5` low + `--system-prompt`, without minting a new freeze hash). | KP2a / KP2b Run B (follow-up) | Commit `3390b13`, `runtime/v5/simulators.py` | Only offline replay (41/41) isolates the code fix; live gains reflect both the fix and the simulator change. |
| **DEV-2** | **Simulator calibration Gate 2 pending:** Null-strategy check reached 15/16 (`sonnet-codex`) and 14/16 (`claude-low-pair`); human blind check pending. | KP2a / KP2b Run B (follow-up) | `laeufe/vor-v5-kalibrierung-2026-11-25.md` | Simulator quality remains provisional; the pair profile shares a family between learner and state judge while staying separate from tutor and coach. |
| **DEV-3** | **Single-judge Live coach arm:** Pre-registration envisioned two cross-family judges (`opus` + `neon`) or manual hand coding by David; only `claude-sonnet-5-5` scored the Live coach arm (Codex excluded by family separation). | KP2a & KP2b Live coach | `kp2a-explorativ-auswertung.json` | No inter-jury Krippendorff's α exists for the Live coach arm; comparisons with Live coach are valid only under the shared Claude lens. |
| **DEV-4** | **Censoring lock (K5) triggered (descriptive denominator reporting only):** Live coach lost 5/24 (20.8% > 10%) cells to format failures in Run B (and 13/150 cells were censored in Run A); the runner locked formal contrasts. | KP2a & KP2b | `summary-hop2.json` | All pre-registered contrast decisions stay locked; all arm tables serve exploratory analysis. |
| **DEV-5** | **`DOPPELFRAGE` not logged by runner in KP2a:** The runner check in `pilot.py` (`run_episode`) activates only when a Turn 3 commitment is configured, leaving all 566 journal rows as `null`. | KP2a Run A & Run B | `runtime/v4/pilot.py` (`run_episode`) | Logged as n/a in the runner; the 113/566 (20.0%) rate comes from an explicitly labeled post-hoc `regeln.v1` scan. |
| **DEV-6** | **Placebo manipulation check failed:** Placebo fell below Core prompt in both KP2a executions (37.5% vs. 58.3% in Run B; 41.7% vs. 50.0% in Run A). | KP2a | `final_combined_stats.json` | Beating Placebo does not prove an advantage over an undisturbed core prompt; follow-up designs require both baselines. |
| **DEV-7** | **Early exploratory disclosure before blind coding:** Exploratory KP1a profiles appeared in an internal interim report before German human blind coding of the 523 turns. | KP1a coding protocol | Internal blind-coding protocol | Disclosed as prior knowledge; coding bundles themselves remain fully anonymized (`blind_id`, no model or arm labels). |
| **DEV-8** | **Two executions of the same KP2a grid (Run A Nov 24 `L2` vs. Run B Nov 25 follow-up):** Run A (`146` primary turns) ran on Nov 24 **before** fix `3390b13` (initial runtime digest `ab17aa95…`, continuation hops 2–4 `9251eceb…`, `claude-opus-5-5` state judge, 133 ok and 10 state-judge errors). Run B (`145` primary turns, runtime `e5eb6e0a…`) ran on Nov 25 after the fix. Both share 150/150 identical prefixes and 126/126 identical non-coach start tuples (126/142 including live coach hints). | KP2a Run A (`L2`) & Run B | `final_verified_truth.json` | Not two independent samples — two executions of the same case/model/seed grid measuring run-to-run stability. |

---

## 3. Deterministic Accounting and Replay Verification

Before examining pedagogical verdicts, Level A establishes complete spend reconciliation across all runs behind the evidence and isolates the technical effect of the quote-normalizer repair.

### 3.1 OpenRouter Live Cost Ledger

| Run / package (chronological) | OpenRouter live diff (USD) | Journal sum (USD) | Approved cap (USD) | Denominator & integrity |
|---|---:|---:|---:|---|
| **KP1a open profiles** (Nov 24, core) | 0.249436 | 0.249699 | 0.90 | 36/36 episodes started, 523/576 turns ok, 3 HTTP-429 + 3 state-judge stops |
| **KP2a Attempt 1 + Run A (`L2`)** (Nov 24–25, core) | 0.176250 | 0.176250 | 0.85 | Attempt 1 aborted on 5h CLI quota ($0.055280); Run A (`L2`, $0.120970): 150/150 started, 133 ok, 146 primary turns |
| **KP2b original pre-fix run** (Nov 25, core) | 0.053810 | 0.053810 | 1.30 | 36/36 started, 5 ok, 31 state-judge quote aborts (input for offline replay) |
| *Subtotal · Nov 24–25 Core runs* | *0.479496* | *0.479759* | *3.05* | *15.7% of $3.05 core cap (live balance 4.058547 → 4.538042)* |
| **KP4 Bridge-482** (Nov 25, GLM + Qwen main) | 0.175931 | 0.176022 | 0.40 | 964 + 964 calls (GLM 0, Qwen 4 errors prior to catch-up) |
| *Interim movement KP4 → KP2a* (Nov 25) | 0.000091 | — | — | Accounted separately |
| **KP2a Run B follow-up** (Nov 25, post-fix, 2 hops) | 0.114555 *(hop diff 0.114430)* | 0.114555 | 0.75 | 150/150 started, 140 ok, 566/600 turns, 0 identical outputs |
| **KP2b pilot pre-run** (Nov 25, 3 aborted cells) | 0.021292 | 0.021292 | *(in 0.75)* | 3 cells, cleanly separated |
| **KP2b main follow-up** (Nov 25–26, hops 1–4) | 0.175478 | 0.175478 | *(in 0.75)* | 16 ok + 17 error ends + 1 open (19 turns) + 2 unstarted (`hop4:tutor.cost_usd = 0.175477866 USD`) |
| **Catch-up runs** (Nov 26: 4 Qwen KP4 + 3 KP2b cells) | 0.016144 | 0.016364 (0.000679 + 0.015685) | 0.01 + 0.15 | KP4 Qwen 482/482 (0 err.) · KP2b 3/3 ok (72/72 turns, 0 err.) |
| *Subtotal · Nov 25–26 Follow-up & catch-up* | *0.503490* | *0.503711* | *2.80* | *18.0% of $2.80 envelope (active sub-caps sum to $1.31; 1 µ$ row rounding)* |
| **Total Study Spend (Nov 24–26, 2026)** | **0.982986** | **0.983470** | **5.85** | **16.8% of $5.85 combined caps · `SHA256SUMS 281/281 OK` archive; 3/3 derived JSONs; 15/15 freeze** |

The $0.982986 total covers **all OpenRouter API spend** behind the reported results ($0.479496 across the Nov 24–25 core runs plus $0.503490 across the Nov 25–26 follow-up and catch-up runs; individual 6-decimal follow-up rows round to $0.503491, 1 µ$ above the exact key-balance delta of $0.503490). Subscription CLI runs (KP1a Terra and Sonnet v1/v2, KP4 Sol and Sonnet on `test_210`, live `gpt-6.2-sol` coach calls, and all two-family jury evaluations) carried no OpenRouter billing and have no separate per-call dollar attribution. GPU training on Runpod for the separate 9B scaffolding-adapter track (~$1.49 total) is accounted outside this study. In KP2a Run B, the immediate hop diff was $0.114430, while the $0.114555 journal total includes delayed provider settlement.

### 3.2 Offline Proof for the Quote-Normalizer Fix vs. Live Follow-Up

Early v4.5 runs frequently aborted when the state judge returned slightly altered punctuation in required verbatim quotes. Offline replay separates the code fix from the simultaneous simulator switch:

- **Deterministic offline replay (isolated causal proof for commit `3390b13`):** Re-validating every stored `state_judge_fehler` raw response from v4.5 through the hardened `normalize_quote` / `quote_matches_tutor` validator (`runtime/v4/execution.py`) rescued **10/10 (100%)** failed transitions in KP2a and **31/31 (100%)** in KP2b — **41/41** overall.
- **Live follow-up runs (combined effect of code fix and Opus → Sonnet low switch):** Complete cells rose from 133/150 (Run A) to 140/150 (Run B) in KP2a (`state_judge_fehler`: 10 → 4) and from 5/36 (159 turns) to **19/36** (599 deduplicated turns; `state_judge_fehler`: 31/36 → 8/36) in KP2b.

The historical quote failures were a normalization artifact, whereas the remaining live stops (4 in KP2a, 8 in KP2b) reflect substantive phase-transition rejections by the lighter Sonnet low state judge.

---

## 4. External Sanity Check on Human Expert Authorship (KP4 Bridge)

Before scoring German multi-turn tutors, KP4 checks whether our AI judges recognize human teaching expertise on paired English math tutoring responses from **Bridge** (Wang et al., 2024; MIT license; blind 0–4 Likert rating in balanced ab/ba order, seed 42). Bridge labels reflect **human expert vs. novice authorship** rather than independent per-pair human quality ratings. All four tested models preferred expert-authored responses well above chance with **0 technical errors**, led by the two judges used in our main jury (`gpt-6.2-sol` and `claude-sonnet-5-5`).

| Judge / route | Subset | Expert wins | Ties | Novice | Errors | Expert win rate (95% CP) | Expert win (excl. ties) | Non-tie rate | `overlap_145` (Win / Excl. ties) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **`codex-cli` · `gpt-6.2-sol` (low)** | `test_210` | 155/210 | 41 | 14 | 0 | **73.8%** [67.3–79.6%] | 91.7% (155/169) | 80.5% (169/210) | **74.5%** / 92.3% |
| **`claude-cli` · `claude-sonnet-5-5` (low)** | `test_210` | 148/210 | 51 | 11 | 0 | **70.5%** [63.8–76.6%] | **93.1%** (148/159) | 75.7% (159/210) | **72.4%** / **92.9%** |
| **`z-ai/glm-5.3-flash`** (OpenRouter) | 482 | 324/482 | 93 | 65 | 0 | **67.2%** [62.8–71.4%] | 83.3% (324/389) | 80.7% (389/482) | 69.7% / 84.9% |
| **`qwen/qwen3.8-flash`** (OpenRouter, 482/482) | 482 | 293/482 | 149 | 40 | 0 | **60.8%** [56.3–65.2%] | 88.0% (293/333) | 69.1% (333/482) | 65.5% / 86.4% |

- **Paired judge comparisons:**
  - GLM vs. Qwen on the exact same 482 pairs: under strict expert-win counting, GLM leads (p = 0.0090, exact McNemar; 82 GLM-only wins vs. 51 Qwen-only) because Qwen assigns far more ties (149 vs. 93). Restricted to the 289 pairs where both models pick a winner, no reliable difference remains (p = 0.286, 8 GLM-only vs. 14 Qwen-only).
  - `gpt-6.2-sol` vs. `claude-sonnet-5-5` on the same 210 pairs: both jury families are statistically indistinguishable (p = 0.410, exact McNemar; 30 Sol-only vs. 23 Sonnet-only) and agree on the three-way outcome in **68.1%** (143/210) of pairs. Across all six judge pairs on the shared `overlap_145` subset (108/28/9 for Sol, 105/32/8 for Sonnet, 101/26/18 for GLM, 95/35/15 for Qwen), three-way agreement ranges from **67.6% to 71.0%**.
- **Methodological limits:** Exact 95% Clopper-Pearson intervals (95% CP) are nominal because 109/482 and 23/210 pairs share dialogue context and novice replies. Accuracy on English single turns provides a sanity check only — it does not replace human calibration on German multi-turn dialogues (Fu & Liu, 2025).

---

## 5. Open 16-Turn Route Profiles (KP1a)

KP1a observes how five inexpensive Flash routes and two frontier subscription references tutor learners across open 16-turn dialogues under a minimal role prompt (199 characters). Because `gpt-6-luna` permits only the Claude judge (55 turns, 4 episodes, 1 simulator Cl), routes ran under different default reasoning budgets (`off`, `minimal`, `low`, `budget 256`), and subscription models ran through separate CLI wrappers, we omit a combined leaderboard and report **separate profiles per judge lens** with episode min–max spans.

### 5.1 OpenRouter Core Routes

Out of 576 planned turns across 36 episodes, 523 completed cleanly and 507 carry an assessable primary check verdict.

- **Family-separated inter-jury reliability (Krippendorff's α recomputed strictly on the 4 dual-jury routes, n = 468 turns, excluding `gpt-6-luna`):**
  - Binary check question (`prueffrage_binaer`, both assessable): **82.8%** exact agreement, **α = 0.642** (n = 447 pairs; three-class across all n = 468: 81.6%, α = 0.645).
  - Factual correctness (`D4_fachlichkeit`): **67.0%** exact agreement, **α = 0.336** (n = 457).
  - Premature answer leakage (`preisgabe`): **72.8%** exact agreement, **α = 0.425** (n = 427).
  - Composite D4-gated check (`pf_d4_gated`, primary score, using the exact two-step gate from §2.1): **76.1%** exact agreement, **α = 0.476** (n = 447).
  Because factual correctness D4 gates the check question, its low agreement (α = 0.336) propagates directly into `pf_d4_gated` (α = 0.476, well below the study's 0.65 human-calibration bar), and turns are clustered within 8 episodes per route. *(Revision note v1.1: the archived German draft `9de246af` reported raw agreement across n = 523 / 498 / 509 before removing `gpt-6-luna`'s family-excluded Codex votes; all four figures above reflect the clean family-separated calculation.)*

| Route (OpenRouter, v4.5) | Turns (Ep. · Sim. Cx / Cl) | Check · **Claude lens** (k/n) | Check · **Codex lens** (k/n) | Check · **Answer mean** (episode span) | D4 factual (votes) | Leakage ↓ (votes) |
|---|---:|---:|---:|---:|---:|---:|
| **`meta/muse-ember`** (minimal) | 113 (8 ep. · 64 Cx / 49 Cl) | 59.3% (64/108) | 39.8% (43/108) | 49.1% (8 ep.: 19–100%) | 70.7% | 36.2% |
| **`openai/gpt-6-luna`** (off, 1 sim.) | 55 (4 ep. · 55 Cl) | 56.9% (29/51) | *excluded (family)* | 56.9%\* (4 ep.: 47–83%) | 94.5%\* | 37.3%\* |
| **`google/gemini-3.8-flash`** (low) | 114 (8 ep. · 64 Cx / 50 Cl) | 53.7% (58/108) | 36.4% (40/110) | 44.5% (8 ep.: 25–60%) | 71.2% | 20.8% |
| **`qwen/qwen3.8-flash`** (budget 256) | 126 (8 ep. · 64 Cx / 62 Cl) | 29.0% (36/124) | 22.8% (28/123) | 25.6% (8 ep.: 13–38%) | 41.4% | 36.7% |
| **`z-ai/glm-5.3-flash`** (low) | 115 (8 ep. · 55 Cx / 60 Cl) | 25.0% (28/112) | 16.4% (18/110) | 20.5% (8 ep.: 0–36%) | 34.9% | 52.5% |

*\* `gpt-6-luna` has only the Claude lens (1 simulator Cl = `claude-cli`, 4 episodes; Cx = `codex-cli`). Under the shared Claude lens, `muse-ember` (59.3%), `gpt-6-luna` (56.9%), and `gemini-3.8-flash` (53.7%) sit close together; comparing pooled answer means directly would inflate `gpt-6-luna` solely because the stricter Codex judge is absent. Although `muse-ember` and `gemini-3.8-flash` average higher than `qwen3.8-flash` and `glm-5.3-flash` under both judge lenses, episode ranges overlap substantially (`muse-ember` 19–100%, `qwen3.8-flash` 13–38%, `glm-5.3-flash` 0–36%) and inter-jury agreement is low (α = 0.476). D4 factual accuracy and answer leakage count valid judge **votes**, not answer averages. Across every dual-jury route, Codex scores lower than Claude — by up to **19.4 pp** on `muse-ember` ((64 − 43) / 108 = 19.44%).*

### 5.2 Separate Reference Panel: Subscription Frontier Models

Two frontier models ran the same four 16-turn scenarios outside the OpenRouter comparison; separate CLI wrappers, single judges, and premature stops keep them in an independent panel:

| Subscription run (UTC window) | Turns ok (Ep.) | Simulator / state judge / single juror | Check (k/n) | D4 factual (k/n) | Fit | Leakage ↓ | Sycophancy ↓ | `DOPPELFRAGE` |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| **`GPT-6.1 Terra`** (06:04–06:20 UTC) | **64/64** (4 ep.) | `claude-sonnet-5-5` (low) | 60.0% (36/60) | **100%** (62/62) | 73.4% (47/64) | **19.6%** (11/56) | 0.0% (0/10) | **29.7%** (19/64) |
| *`Terra` matched to `Sonnet v1`* | 34/34 (4 ep.) | `claude-sonnet-5-5` (low) | 58.1% (18/31) | 100% (33/33) | 70.6% (24/34) | 25.8% (8/31) | 0.0% (0/8) | — |
| **`Claude Sonnet 5.5` v1** (06:25–06:36 UTC) | 34/64 (4 ep.) | `gpt-6.2-sol` (low / low / low) | 83.9% (26/31) | **100%** (34/34) | 94.1% (32/34) | 44.1% (15/34) | 0.0% (0/10) | 76.5% (26/34) |
| **`Claude Sonnet 5.5` v2** (14:10–14:23 UTC) | 32/64 (4 ep.) | `gpt-6.2-sol` (low / **medium** / low) | 83.3% (25/30) | **100%** (32/32) | 93.8% (30/32) | 25.0% (8/32) | 0.0% (0/9) | 84.4% (27/32) |

- **Key observations:** Both frontier models achieved 100% factual accuracy (D4) and 0% sycophancy. Under the shared Claude lens, Terra (60.0%, 36/60) sat close to the higher-averaging Flash routes (`muse-ember` 59.3%, `gpt-6-luna` 56.9%). All eight Sonnet episodes ended prematurely with `simulator_zustand_fehler` (*"state judge proposed a transition outside the phase contract"*): at Turns **13 / 3 / 13 / 5** in v1 and **3 / 3 / 13 / 13** in v2 (Python / Fractions / Attention / AlphaFold) despite upgrading the state judge to `gpt-6.2-sol` medium. Because the subscription turn journal did not log raw state-judge JSON, no single validator rule can be isolated causally. Even frontier models frequently ask multiple questions at once (`DOPPELFRAGE` 76.5% / 84.4% for Sonnet) or leak solutions without targeted process control.

---

## 6. Situational Scaffolding at Identical Prefixes (KP2a)

KP2a tests the core intervention question from bit-identical dialogue prefixes: *Does a one-turn situational hint just before a difficult moment improve Flash tutor turns compared to a short core prompt or a long static rule prompt?*

> **Contrast status (`vorregistrierung.json`):** Five of 24 Live coach calls (20.8% > 10%) failed the format check in Run B (Nov 25 follow-up), triggering the automatic censoring lock (K5), and the Live coach arm was scored by Claude only. Every pre-registered contrast decision therefore stays **locked** (*descriptive denominator reporting only*). To check run-to-run stability, we place **Run B (Nov 25, post-fix follow-up; 145 scored primary turns, runtime `e5eb6e0a…`)** beside the earlier **Run A (Nov 24, pre-fix `L2`; 146 scored primary turns, runtime `ab17aa95…` / `9251eceb…`, `claude-opus-5-5` state judge, 133 ok and 10 state-judge errors)**. Run A and Run B are **not independent samples** (150/150 identical cell prefixes, 126/126 identical non-coach start tuples, 126/142 including live coach hints). Inter-jury Krippendorff's α on `prueffrage_d4_gated` (non-coach arms) was **α = 0.825** (91.3%, n = 126) in Run B, **α = 0.744** (87.2%, n = 125) in Run A, and **α = 0.785** (89.2%, n = 251) combined.

### 6.1 Arm Summary Across Both Executions

Each row reports the three-valued answer mean (0 / 0.5 / 1), hard judge-agreement bounds (*Both Yes* to *At least 1 Yes*), separate Claude/Codex lenses, and the Best–Worst missingness range over the full planned denominator (48 planned turns combined; 12 for Wrong hint):

| Arm (KP2a) | Run B · Follow-up (Nov 25: n · mean · Cl / Cx) | Run A · `L2` (Nov 24: n · mean · Cl / Cx) | **Combined (n / plan)** | **Combined mean** | **Bounds (Both / ≥1 Yes)** | **Cl / Cx (combined)** | **Best–Worst /Plan** |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Fixed hint** (`p1_hinweis`) | 24 · 62.5% · 71 / 54% | 24 · 68.8% · 67 / 71% | 48 / 48 | **65.6%** | 56.2% / 75.0% | 68.8 / 62.5% | 65.6–65.6% |
| **Core prompt** (`p1_kern`) | 24 · 58.3% · 58 / 58% | 24 · 50.0% · 46 / 54% | 48 / 48 | **54.2%** | 50.0% / 58.3% | 52.1 / 56.2% | 54.2–54.2% |
| **Extra reasoning** (`p1_reasoning`) | 24 · 39.6% · 42 / 38% | 24 · 58.3% · 63 / 54% | 48 / 48 | **49.0%** | 43.8% / 54.2% | 52.1 / 45.8% | 49.0–49.0% |
| **Full rules** (`p6_voll`) | 24 · 41.7% · 42 / 42% | 23 · 54.3% · 52 / 57% | 47 / 48 | **47.9%** | 46.8% / 48.9% | 46.8 / 48.9% | 46.9–49.0% |
| **Live coach** (`p1_frontier_coach`, Cl only) | 19 · 42.1% · 42 / — | 21 · 52.4% · 52 / — | 40 / 48 | **47.5%** | 47.5% *(1 judge)* | 47.5% / excl. | 39.6–56.2% |
| **Placebo** (`p1_placebo`) | 24 · 37.5% · 46 / 29% | 24 · 41.7% · 42 / 42% | 48 / 48 | **39.6%** | 33.3% / 45.8% | 43.8 / 35.4% | 39.6–39.6% |
| **Wrong hint** (`p1_falschhinweis`, T2 only) | 6 · 0.0% · 0 / 0% | 6 · 16.7% · 33 / 0% | 12 / 12 | **8.3%** | 0.0% / 16.7% | 16.7 / 0.0% | 8.3–8.3% |

Two patterns hold across both executions: Fixed hint reaches the highest overall descriptive mean (62.5% in Run B and 68.8% in Run A), while the neutral Placebo falls below Core prompt in **both** runs (−20.8 pp in Run B and −8.3 pp in Run A; under both judge lenses combined: Claude −8.3 pp, Codex −20.8 pp). Meanwhile, Extra reasoning flips sharply relative to Core prompt between runs (39.6% vs. 58.3% in Run B; 58.3% vs. 50.0% in Run A).

### 6.2 Pre-Registered Rules Status

Thresholds defined in `vorregistrierung.json` for 30 opportunities (10 clusters across KP2a + KP2b) are never rescaled retroactively to 24 or 48:

| Pre-registered rule | Planned universe | Descriptive observation (KP2a Run B follow-up, exploratory) | Formal status |
|---|---|---|---|
| **Censoring lock (K5)** (≤ 10% per arm, diff ≤ 5 pp) | Per arm (KP2a n = 24, KP2b n = 6) | Live coach lost 5/24 (20.8% > 10%) cells in Run B; runner locked contrasts | **Triggered → contrasts locked** |
| **Human calibration** (α ≥ 0.65, FNR/FPR ≤ 15%, abs(Bias) ≤ 10 pp) | Holdout after German blind coding | Pending (AI jury uncalibrated) | **Pending → contrasts locked** |
| **`h_p_min_diff` (≥ 6) & `fc_p_min_diff` (≥ 6)** | 30 opportunities (10 clusters) | In KP2a (n = 24): Fixed hint − Placebo = +6.0 (15.0 vs. 9.0); under Claude lens Live coach 8/19 (42.1%) vs. Placebo 11/24 (45.8%); Placebo failed neutrality (9.0 vs. Core 14.0) | **Locked** (24 ≠ 30, Placebo not neutral) |
| **`p6_p1_min_abs_diff` (≥ 5) & `h6_max_abs_diff` (≤ 3)** | 30 opportunities (10 clusters) | Full rules − Core = −4.0 in Run B (10.0 vs. 14.0); +0.5 in Run A (12.5 vs. 12.0) | **Locked** (24 ≠ 30) |
| **`richtung_min_clusteranteil` (≥ 0.70)** | 10 clusters (Case × Model) | In KP2a (8 clusters): Fixed hint > Placebo in 5/8 (62.5%), Fixed hint > Core in 2/8 (25.0%) in Run B | **Locked** (8 ≠ 10 clusters) |
| **No-model-below & reversal guard (≥ 2/3 seeds)** | 2 models (15 opportunities/model) | Run B Fixed hint vs. Core: Muse 7.5 vs. 6.0, Qwen 7.5 vs. 8.0 (Qwen below Core); Fixed hint vs. Placebo: Muse 7.5 vs. 5.0, Qwen 7.5 vs. 4.0 | **Locked** |
| **`t2_h_f_min_diff` (≥ 2 in Case T2, n = 6) — Specificity H3** | 6 opportunities in Case T2 | Run B: 0.5/6 vs. 0.0/6 (+0.5; Core also 0.0/6); Run A: 1.5/6 vs. 1.0/6 (+0.5) | **Locked / uninformative (floor effect in T2)** |
| **Guardrail against direct Extra reasoning vs. Fixed hint contrast** | Excluded comparison | Not run; Extra reasoning vs. Core reverses across executions | **Observed (no direct contrast)** |

### 6.2a Pre-Registered Hypotheses (H1–H6) Outcomes

| Hypothesis | Pre-registered prediction | Descriptive observation (combined / per run) | Formal status |
|---|---|---|---|
| **H1** | Early turns through Turn 8 (T7 + T8): Full rules ≥ Fixed hint | Runs against prediction: Fixed hint 17.5/24 vs. Full rules 13.5/23 combined (8.5/12 vs. 6.0/12 Run B; 9.0/12 vs. 7.5/11 Run A), driven by Full rules collapsing in T8 (1.5/11) | **Locked** (censoring & calibration pending) |
| **H2** | Late turns from Turn 15 (Case T12, Turn 23): Fixed hint > Full rules | Points in predicted direction on small surviving denominators: Turn 23 2.0/5 vs. 0.0/3 (Turn 24 hold 2.5/5 vs. 0.0/3) | **Locked** (censoring & calibration pending) |
| **H3** | Content specificity in Case T2 (Turn 12): Fixed hint − Wrong hint ≥ 2/6 | Floor effect across arms: 0.5/6 vs. 0.0/6 in Run B; 1.5/6 vs. 1.0/6 in Run A (+0.5 each; Core 0.0/6) | **Locked / uninformative** |
| **H4** | Fine-tuned SFT/RL tutor models vs. base Flash models | Not tested in v4.5; reserved for separate fine-tuning track | **Out of scope for v4.5** |
| **H5** | Live coach variance and over-correction across 3 tutor seeds (descriptive) | High format failure (5/24 Run B + 3/24 Run A in KP2a; 4/6 in KP2b) and full route reversal (Muse 6/11 vs. Qwen 2/8 → 5/10 vs. 6/11) | **Descriptive (observed)** |
| **H6** | Equivalence / null rule (abs(Full rules − Core) ≤ 3 on 30 opps, ≤ 2 per model) | Run B Full rules − Core = −4.0 on n = 24; Run A = +0.5 on n = 23/24; cannot evaluate equivalence under censoring lock | **Locked** (censoring & 24 ≠ 30) |

### 6.3 Individual Cluster Matrix

All 50 populated cells across the 8 Case × Model clusters are derived directly from the raw journals and family-separated jury (format: `Combined [Run B + Run A] (Run B follow-up alone)`):

| Cluster (Case × Model) | `p1_hinweis` | `p1_kern` | `p6_voll` | `p1_reasoning` | `p1_placebo` | `p1_frontier_coach` (Cl only) | `p1_falschhinweis` |
|---|---:|---:|---:|---:|---:|---:|---:|
| **T2 · Muse-Ember** (Turn 12) | 1.0/6 (0.0/3) | 0.0/6 (0.0/3) | 0.0/6 (0.0/3) | 0.0/6 (0.0/3) | 0.0/6 (0.0/3) | 0.0/6 (0.0/3) | 0.5/6 (0.0/3) |
| **T2 · Qwen 3.8 Flash** (Turn 12) | 1.0/6 (0.5/3) | 0.0/6 (0.0/3) | 0.0/6 (0.0/3) | 0.0/6 (0.0/3) | 0.0/6 (0.0/3) | 0.0/5 (0.0/2) | 0.5/6 (0.0/3) |
| **T3 · Muse-Ember** (Turn 10) | **6.0/6** (3.0/3) | 1.5/6 (0.0/3) | 5.0/6 (2.0/3) | 1.5/6 (0.5/3) | 1.5/6 (0.0/3) | 1.0/5 (1.0/3) | — |
| **T3 · Qwen 3.8 Flash** (Turn 10) | **6.0/6** (3.0/3) | 4.0/6 (3.0/3) | 4.0/6 (2.0/3) | 3.0/6 (1.5/3) | 0.0/6 (0.0/3) | 2.0/4 (0.0/2) | — |
| **T7 · Muse-Ember** (Turn 8) | 6.0/6 (3.0/3) | 6.0/6 (3.0/3) | 6.0/6 (3.0/3) | 6.0/6 (3.0/3) | 5.5/6 (2.5/3) | 5.0/5 (3.0/3) | — |
| **T7 · Qwen 3.8 Flash** (Turn 8) | 5.5/6 (2.5/3) | 6.0/6 (3.0/3) | 6.0/6 (3.0/3) | 5.0/6 (2.0/3) | 3.5/6 (2.0/3) | 4.0/4 (1.0/1) | — |
| **T8 · Muse-Ember** (Turn 8) | 2.0/6 (1.5/3) | 5.5/6 (3.0/3) | **1.5/6** (0.0/3) | 5.5/6 (2.5/3) | 4.5/6 (2.5/3) | 5.0/5 (2.0/2) | — |
| **T8 · Qwen 3.8 Flash** (Turn 8) | 4.0/6 (1.5/3) | 3.0/6 (2.0/3) | **0.0/5** (0.0/3) | 2.5/6 (0.0/3) | 4.0/6 (2.0/3) | 2.0/6 (1.0/3) | — |

The matrix exposes stark case stratification: Case T2 (`STOP_DRIFT`) sits at a floor across nearly every arm (0/12 for Core prompt, Full rules, Extra reasoning, and Placebo; 0/11 observed of 12 planned for Live coach), leaving only three cases that separate arms; Case T7 (`CHECK_EVIDENCE`) sits near ceiling (12/12 for Core prompt and Full rules, 11.5/12 for Fixed hint); Case T3 (`HOLD_LEAD`) carries most of the Fixed hint lead (12/12 unanimous vs. 5.5/12 Core prompt, while Full rules also reaches 9.0/12); and Case T8 (`SWITCH_MODALITY`) flips the picture, with Full rules dropping to 1.5/11 (missing 1 Qwen cell in Run A; even a full hit there yields at most 2.5/12) and Fixed hint also trailing Core prompt (6.0/12 vs. 8.5/12, while Placebo matches Core prompt at 8.5/12; Muse Live coach also missed 1 Run B cell, 2.0/2 observed).

### 6.3a Leave-One-Case-Out Sensitivity (Dependence on Case T3)

Each row pools Run B (follow-up) and Run A (`L2`) across the remaining clusters (differences computed from unrounded means):

| Case selection | Fixed hint | Core prompt | Placebo | Hint − Core | Hint − Placebo | Placebo − Core | Hint − Core (ans.) |
|---|---:|---:|---:|---:|---:|---:|---:|
| All 4 cases | 31.5/48 (65.6%) | 26.0/48 (54.2%) | 19.0/48 (39.6%) | +11.5 pp | +26.0 pp | −14.6 pp | +5.5 ans. |
| Excluding T2 | 29.5/36 (81.9%) | 26.0/36 (72.2%) | 19.0/36 (52.8%) | +9.7 pp | +29.2 pp | −19.4 pp | +3.5 ans. |
| Excluding T3 | 19.5/36 (54.2%) | 20.5/36 (56.9%) | 17.5/36 (48.6%) | −2.8 pp | +5.6 pp | −8.3 pp | −1.0 ans. |
| Excluding T7 | 20.0/36 (55.6%) | 14.0/36 (38.9%) | 10.0/36 (27.8%) | +16.7 pp | +27.8 pp | −11.1 pp | +6.0 ans. |
| Excluding T8 | 25.5/36 (70.8%) | 17.5/36 (48.6%) | 10.5/36 (29.2%) | +22.2 pp | +41.7 pp | −19.4 pp | +8.0 ans. |

Separating the two executions shows why the hint advantage does not hold consistently without Case T3: in Run B (follow-up) alone, Fixed hint sits at 9.0/18 = 50.0% vs. Core prompt 11.0/18 = 61.1% (**−11.1 pp**; Placebo 9.0/18 = 50.0%, −11.1 pp vs. Core), whereas in Run A (`L2`) Fixed hint stays at 10.5/18 = 58.3% vs. Core prompt 9.5/18 = 52.8% (**+5.6 pp**; Placebo 8.5/18 = 47.2%, −5.6 pp vs. Core). Over all four cases, the per-run Fixed hint − Core gap is +4.2 pp in Run B (Claude +12.5 pp, Codex −4.2 pp) and +18.8 pp in Run A (Claude +20.8 pp, Codex +16.7 pp).

### 6.4 Qualitative Mechanism Notes and Level-A Checks in KP2a

- **Case T8 (Full rules) — case-bound drop, cause still open:** Inspecting raw Turn 8 replies (such as Qwen seed 42, translated from German: *"Picture 1/2 as a pizza. Half a pizza is the same as 3 slices of a 6-slice pizza, and 1/3 is 2 slices of that same 6-slice pizza."*) argues against the model ignoring the representation-shift rule. Instead, several Full rules replies introduce the visual analogy while walking through intermediate conversion steps (or solving 1/2 + 1/3 = 5/6 outright, as in Muse seed 44), leaving less room for student work, while other replies (Qwen seeds 43 and 44) break down arithmetically. Controlled ablations are needed to separate prompt length from rule wording.
- **Live coach route reversal and format-error root cause:** Under the Claude lens, model ordering inside Live coach reverses completely between executions (Muse 6/11 vs. Qwen 2/8 in Run B; **Muse 5/10 vs. Qwen 6/11** in Run A), ruling out a stable model advantage. All **9/9** `coach_format_fehler` failures across follow-up runs (5 in KP2a + 4 in KP2b) shared one technical cause: hints met the character limit but narrowly exceeded the stricter `regex-v1` token cap in single-shot generation without a retry. Offline replay of a hardened schema-and-retry guard (`coach_v2`) eliminated all 9/9 stored failures; live validation remains open.
- **Post-hoc `DOPPELFRAGE` and hint-leakage audit:** Because KP2a carried no Turn 3 commitment, the runner left `DOPPELFRAGE` as `null`. A post-hoc deterministic `regeln.v1` scan across all 566 Run B turns flagged **113/566 (20.0%)** replies containing multiple question prompts. Across the entire run, only **1** `hinweis_leck` hit occurred (Case T2, `muse-ember`, Live coach, seed 43, Turn 12: 8-word n-gram overlap with hint text, 0 meta-leaks), followed by 3 clean turns.

---

## 7. 24-Turn Instruction Compliance and Checkpoint Spikes (KP2b Case T12)

KP2b tests whether Flash tutors keep a **scripted tutor commitment** programmatically prepended by the runner (`with_agreement` in `pilot.py`) to the tutor's Turn 3 reply (*"I will always ask for your guess first and ask exactly one question per turn"*, German original: *„Ich frage immer zuerst nach deiner Vermutung und stelle genau eine Frage pro Zug.“*) across a 24-turn Python lists dialogue (Case T12). Merging the 33 completed cells from `kp2b-pilot-hop4.jsonl` (16 ok + 17 error terminations; excluding the 19 unfinished turns of one interrupted Extra reasoning seed-44 cell) with the 3-cell catch-up run (3/3 ok, 72/72 turns) covers all **36/36 planned episodes**: **19/36 ok** reached Turn 24, 8 ended on `state_judge_fehler`, 4 on `coach_format_fehler`, 3 on HTTP-429 stops, and 2 on `tutor_fehler`, yielding **599/864** deduplicated visible tutor turns and 39 jury-scored checkpoint answers (20 at Turn 23, 19 at Turn 24).

Turn 23 and Turn 24 columns report the answer mean (0 / 0.5 / 1) for the primary check across both judges.

| Arm (KP2b · Case T12) | Cells ok/6 | Turns (dedup.) | `DOPPELFRAGE` all | Turn 3+ ↓ | Turn 4+ ↓ | Leak (hits / follow) | Turn 23 primary | Turn 24 hold |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Fixed hint** (`p1_hinweis`) | 5/6 | 121 | 51/121 (42.1%) | 42/110 (38.2%) | **40/105** (38.1%) | 1 / 16\* | 40.0% (2.0/5) | **50.0%** (2.5/5) |
| **Placebo** (`p1_placebo`) | 3/6 | 123 | 58/123 (47.2%) | 50/111 (45.0%) | **46/105** (43.8%) | 0 / 0 | 37.5% (1.5/4) | 33.3% (1.0/3) |
| **Extra reasoning** (`p1_reasoning`) | 5/6 | 122 | 77/122 (63.1%) | 65/110 (59.1%) | **62/105** (59.0%) | 0 / 0 | 20.0% (1.0/5) | 20.0% (1.0/5) |
| **Core prompt** (`p1_kern`) | 3/6 | 83 | 31/83 (37.3%) | 24/72 (33.3%) | **23/67** (34.3%) | 0 / 0 | 33.3% (1.0/3) | 0.0% (0.0/3) |
| **Full rules** (`p6_voll`) | 3/6 | 84 | 38/84 (45.2%) | 29/72 (40.3%) | **26/67** (38.8%) | 0 / 0 | 0.0% (0.0/3) | 0.0% (0.0/3) |
| **Live coach** (`p1_frontier_coach`) | 0/6 | 66 | 23/66 (34.8%) | 14/54 (25.9%) | **12/48** (25.0%) | 0 / 0 | No cell reached (0/6) | No cell reached (0/6) |
| **Total (36/36 episodes)** | **19/36** | **599** | **278/599** (46.4%) | **224/529** (42.3%) | **209/497** (42.1%) | **1 / 16** | **20 ans. / 36 plan** | **19 ans. / 36 plan** |

*\* Single `hinweis_leck` hit occurred in Qwen Fixed hint seed 43 at Turn 8, followed by 16 clean turns through Turn 24; that episode scored no/no at both Turn 23 and Turn 24.*

- **Primary checkpoints vs. routine turns (uniform post-commitment window, Turns 4–24):** Using **Turn 4 onward** (497 visible of 756 planned turns) as the consistent post-commitment window, the deterministic detector flags **209/497 (42.1%)** turns (Turn 3 itself: 15/32; pre-commitment context Turns 1–2: 54/70 = 77.1%; by route from Turn 4+: `muse-ember` 89/236, `qwen3.8-flash` 120/261). Flags occur far more frequently on the **four scripted checkpoint turns (Turns 8, 13, 18, 23)** at **66/90 (73.3%)** (17/26, 16/23, 15/21, 18/20) than across all remaining turns in Turns 4–24 at **143/407 (35.1%)** — although individual routine turns such as Turn 20 (13/21 = 61.9%) and Turn 15 (12/22 = 54.5%) also rise. The hint-free Core prompt arm triggered `DOPPELFRAGE` in 3/3 surviving cells on all four checkpoints, showing that spikes occur without injected hints; because triggers occur at fixed turns, the design cannot isolate trigger complexity from turn position or changing survivor composition. Because no control arm ran without the Turn 3 commitment, the drop after Turn 3 is not causal. Late-turn arm weights also shift as cells drop out (36 → 19): Extra reasoning contributed 105 visible post-commitment turns (62 flagged), while Live coach contributed 48 (12 flagged) and had 0 survivors at Turns 23–24.
- **Inter-jury reliability (39 combined Turn 23 + Turn 24 answers):** Both judges agreed on 89.7% of answers for the primary criterion (Krippendorff's **α = 0.734**) and 87.2% for commitment kept (**α = 0.678**); `hinweis_meta_leck` was unanimously `no` in 39/39 cases (α undefined due to zero variance).
- **Turn 24 breakdown by rubric field:** On the primary criterion, Fixed hint (2.5/5 = 50.0%) combines two unanimous yes/yes verdicts and one split yes/no; Placebo (1.0/3 = 33.3%) and Extra reasoning (1.0/5 = 20.0%) each have one yes/yes; Core prompt and Full rules score 0.0/3; and Live coach reached **0/6 cells** (4 format errors + 2 state-judge errors). On the separate commitment-kept field, Core prompt received 0.5/3 (Muse seed 43: Claude yes, Codex no). The 2.0/5 → 2.5/5 difference for Fixed hint is half an answer point and does not establish retention.

---

## 8. Limitations, Open Evidence Gates, and Software Separation

1. **Human blind calibration remains pending:** Until German human blind coding (363 or 244 scored tutor turns depending on scope, plus priority KP2a/KP2b subsets) passes calibration (Krippendorff's α ≥ 0.65, FNR/FPR ≤ 15%, |Bias| ≤ 10 pp), every German AI-jury metric remains exploratory (Cohn et al., 2026).
2. **Process quality ≠ human learning:** Simulated learners (Käser & Alexandron, 2024; Scarlatos et al., 2026) measure observable tutor moves only. Demonstrating retention or transfer requires a separate study with human learners solving novel unaided post-test tasks (Sawyer, 2006, p. 152).
3. **Double-baseline retests and hardened coach live run pending:** Future tests must compare every hint arm against **both** Core prompt and Placebo, include explicit non-intervention counter-cases against over-scaffolding, separate prompt length from rule wording in Case T8, and validate the hardened `coach_v2` guard live (currently verified on 9/9 stored failures offline only).
4. **Strict separation from the public v5 software harness (`ai-tutor-bench 0.1.0`):** This report documents the dated **v4.5 laboratory study** (freeze `3e01a5a5…`). The public repository `ai-tutor-bench` (0.1.0) ships the newer **v5 offline suite** (161 synthetic cells, `freeze_sha256: 7d189527…`, deterministic `fixture` and `alternate` adapters) and excludes external model runs; **v4.5 results cannot be reproduced by running the v5 public suite**. Likewise, the 9B LoRA scaffolding coach (`Qwen/Qwen3.5-9B`, Run 3 Epoch 2) belongs to a separate training track evaluated on its own `dev_hard` split and is tracked separately outside this benchmark release.

---

## 9. Revision History and Verification Artifacts

Six factual corrections relative to the archived German baseline (`tutor-bench-paper-2026-11-26.md`, commit `9de246af`) are recorded here without altering the frozen study data (`SHA256SUMS` 3/3 OK on derived JSONs, 281/281 OK on raw archive, 15/15 on v4.5 freeze):

1. **Bridge column label (§4):** Renamed "Non-Tie-Quote" to **Expert win (excl. ties)** (`Expert / (Expert + Novice)`) and added the actual **Non-tie rate** (`(Expert + Novice) / n`); clarified that Bridge labels reflect **human expert authorship**.
2. **Family-separated KP1a inter-jury reliability (§5.1):** Recomputed Krippendorff's α for `prueffrage_binaer` (n = 447, α = 0.642), 3-class (n = 468, α = 0.645), `D4_fachlichkeit` (n = 457, α = 0.336), `preisgabe` (n = 427, α = 0.425), and `pf_d4_gated` (n = 447, 76.1%, α = 0.476) strictly on the four dual-jury routes (n = 468), removing `gpt-6-luna`'s family-excluded Codex votes.
3. **Missing coach cells in KP2b charts (§7):** Represented 0/0 surviving cells for Live coach at Turns 23 and 24 as `null` / **No cell reached (0/6)** rather than plotting 0%.
4. **Exact scaffolding case descriptions (§2.2, §6.3):** Aligned Case T2 (`STOP_DRIFT`, detail drift past overview goal), Case T3 (`HOLD_LEAD`, hold pedagogical lead to unlike denominators), and Case T7 (`CHECK_EVIDENCE`, check unproven agreement on Python list references) verbatim with `v4/pilot/faelle.json`.
5. **Exact Turn 3 commitment quote and speaker (§2.2, §7):** Replaced the informal learner-request paraphrase with the exact scripted tutor commitment prepended by `pilot.py` from `faelle.json` (*„Ich frage immer zuerst nach deiner Vermutung und stelle genau eine Frage pro Zug.“* — *"I will always ask for your guess first and ask exactly one question per turn."*).
6. **Complete OpenRouter cost accounting (§3.1):** Added the three Nov 24–25 core rows (KP1a, KP2a Attempt 1 + Run A `L2`, KP2b pre-fix; $0.479496) alongside the Nov 25–26 follow-up and catch-up rows ($0.503490) to report the full **$0.982986** OpenRouter spend behind all reported findings.

- **Archived predecessors (kept read-only):** German paper draft (`tutor-bench-paper-2026-11-26.md`, commit `9de246af`); early technical baseline report R1 (`berichte/tutor-bench-abschlussbericht/`, Nov 24, 2026, `fd98e0d4`).
- **Verification hashes:** v4.5 freeze `3e01a5a5…` (15/15 files), runtime fix `3390b13`, derived stats `paper/daten/SHA256SUMS.txt` (3/3 OK), private raw archive `SHA256SUMS` (281/281 OK).

---

## 10. References

- Agentica Project, UC Berkeley Sky Computing Lab, & Together AI (2025). *DeepSWE-Preview: Training a State-of-the-Art Coding Agent from Scratch by Scaling RL*. Open-source research release. [huggingface.co/agentica-org/DeepSWE-Preview](https://huggingface.co/agentica-org/DeepSWE-Preview)
- Ainsworth, S. (2006). DeFT: A conceptual framework for considering learning with multiple representations. *Learning and Instruction*, 16(3), 183–198.
- Arjona-Giner, S., Llorens-Largo, F., García-Sigüenza, J., & Satorre-Cuerda, R. (2026). A Guided Multi-Agent Tutor for Progressive Help in Programming Practice. In *Proceedings of CAEPIA 2026* (Springer). DOI: `10.1007/978-3-032-43170-7_5`
- Artificial Analysis (2025/2026). *Independent AI Model & Performance Benchmarks*. [artificialanalysis.ai](https://artificialanalysis.ai/)
- Asher, M. W., Cao, M., & Carvalho, P. F. (2026). Turning Errors into Successes: Designing LLM Tutoring Around Scaffolded Error Correction. *arXiv preprint* [arXiv:2611.20061](https://arxiv.org/abs/2611.20061).
- Bassner, P., Lenk-Ostendorf, B., Beinstingel, R., Wasner, T., & Krusche, S. (2025). Less stress, better scores, same learning: The dissociation of performance and learning in AI-supported programming education. *Computers and Education: Artificial Intelligence*, 10, 100537. DOI: `10.1016/j.caeai.2025.100537`
- Bastani, H., Bastani, O., Sungu, A., Ge, H., Kabakcı, Ö., & Mariman, R. (2025). Generative AI without guardrails can harm learning: Evidence from high school mathematics. *Proceedings of the National Academy of Sciences (PNAS)*, 122(26), e2422633122. DOI: `10.1073/pnas.2422633122`
- Cohn, C., Fonteles, J., Vanacore, K., Mazza, G., Crawford, C., Hooper, T., Biswas, G., & Kizilcec, R. (2026). Agreement Is Not Validity: Cross-Model LLM Consensus in Diagnosing Student Failure Modes in K-12 Math Tutoring Dialogue. *arXiv preprint* [arXiv:2610.08703](https://arxiv.org/abs/2610.08703).
- Daheim, N., Macina, J., Kapur, M., Gurevych, I., & Sachan, M. (2024). Stepwise Verification and Remediation of Student Reasoning Errors with Large Language Model Tutors. In *Proceedings of EMNLP 2024*. [aclanthology.org/2024.emnlp-main.478](https://aclanthology.org/2024.emnlp-main.478/)
- Domínguez Figaredo, D., & Fernández De la Cruz, R. (2026). The learner who does not learn: when optimizing a pedagogical metric degrades LLM tutoring. *arXiv preprint* [arXiv:2610.12125](https://arxiv.org/abs/2610.12125).
- Feuer, B., Goldblum, M., Datta, T., Nambiar, S., Besaleli, R., Dooley, S., Cembalest, M., & Dickerson, J. P. (2025). Style Outweighs Substance: Failure Modes of LLM Judges in Alignment Benchmarking. In *Proceedings of ICLR 2025*. [arXiv:2409.15268](https://arxiv.org/abs/2409.15268)
- Fu, X., & Liu, W. (2025). How Reliable is Multilingual LLM-as-a-Judge? In *Findings of the Association for Computational Linguistics: EMNLP 2025*. [aclanthology.org/2025.findings-emnlp.587](https://aclanthology.org/2025.findings-emnlp.587/)
- Hattie, J., & Timperley, H. (2007). The power of feedback. *Review of Educational Research*, 77(1), 81–112.
- Houdé, O., & Borst, G. (Eds., 2022). *The Cambridge Handbook of Cognitive Development*. Cambridge University Press.
- Jaroslawicz, D., Whiting, B., Shah, P., & Maamari, K. (2025). How Many Instructions Can LLMs Follow at Once? *arXiv preprint* [arXiv:2507.11538](https://arxiv.org/abs/2507.11538).
- Jimenez, C. E., Yang, J., Wettig, A., Yao, S., Pei, K., Press, O., & Narasimhan, K. (2024). SWE-bench: Can Language Models Resolve Real-World GitHub Issues? In *Proceedings of ICLR 2024*. [arXiv:2310.06770](https://arxiv.org/abs/2310.06770)
- Käser, T., & Alexandron, G. (2024). Simulated Learners in Educational Technology: A Systematic Literature Review and a Turing-like Test. *International Journal of Artificial Intelligence in Education*, 34(2). DOI: `10.1007/s40593-023-00337-2`
- Kestin, G., Miller, K., Klales, A., Milbourne, T., & Ponti, G. (2025). AI tutoring outperforms in-class active learning: an RCT introducing a novel research-based design in an authentic educational setting. *Scientific Reports*, 15, 17458. DOI: `10.1038/s41598-025-97652-6`
- Laban, P., Hayashi, H., Zhou, Y., & Neville, J. (2025). LLMs Get Lost in Multi-Turn Conversation. *arXiv preprint* [arXiv:2505.06120](https://arxiv.org/abs/2505.06120).
- Lee, S., Baek, J., Park, J., & Shin, D. (2026). LLM Pedagogical Behavior in AI Tutoring Interactions. *arXiv preprint* [arXiv:2608.22993](https://arxiv.org/abs/2608.22993).
- Lee, Y., Kim, J., Kim, J., Cho, H., Kang, J., Kang, P., & Kim, N. (2024). CheckEval: A reliable LLM-as-a-Judge framework for evaluating text generation using checklists. *arXiv preprint* [arXiv:2403.18771](https://arxiv.org/abs/2403.18771).
- Leutner, D., & Biele, J. (2025). Without Integration, Everything Is Nothing: A Meta-Analysis of the Effectiveness of Instructional Support for Drawing-to-Learn. *Educational Psychology Review*, 37, 93.
- Li, K., Liu, T., Bashkansky, N., Bau, D., Viégas, F., Pfister, H., & Wattenberg, M. (2024). Measuring and Controlling Instruction (In)Stability in Language Model Dialogs. *arXiv preprint* [arXiv:2402.10962](https://arxiv.org/abs/2402.10962).
- Li, Z., Zhu, Q., Wang, M., Li, J., & Huang, H. (2026a). Planning-Guided Tutoring with Assessment-Driven Memory for Pedagogical LLM Tutors (ScaffoldLM). In *Proceedings of ACL 2026*. [aclanthology.org/2026.acl-long.325](https://aclanthology.org/2026.acl-long.325/)
- Li, N., Zhang, Z., Huang, Z., Li, R., Zhan, Y., Luo, Y., Liu, Q., & Chen, E. (2026b). LongTutor: Benchmarking Large Language Models for Long-term Personalized Tutoring. In *Proceedings of ACL 2026*. [aclanthology.org/2026.acl-long.1371](https://aclanthology.org/2026.acl-long.1371/)
- Macina, J., Daheim, N., Hakimi, I., Kapur, M., Gurevych, I., & Sachan, M. (2025). MathTutorBench: A Benchmark for Measuring Open-ended Pedagogical Capabilities of LLM Tutors. In *Proceedings of EMNLP 2025*. [aclanthology.org/2025.emnlp-main.11](https://aclanthology.org/2025.emnlp-main.11/)
- Maurya, K. K., Srivatsa, K. V. A., Petukhova, K., & Kochmar, E. (2025). Unifying AI Tutor Evaluation: An Evaluation Taxonomy for Pedagogical Ability Assessment of LLM-Powered AI Tutors (MRBench). In *Proceedings of NAACL 2025*. [aclanthology.org/2025.naacl-long.57](https://aclanthology.org/2025.naacl-long.57/)
- OpenAI (2024). *Introducing SWE-bench Verified*. Technical release (500 human-validated SWE-bench tasks). [openai.com/index/introducing-swe-bench-verified](https://openai.com/index/introducing-swe-bench-verified/)
- Pal, S., Ji, K., & Srihari, R. K. (2026). DICE: Decoupling Capability from Intervention Necessity in LLM Tutoring. *arXiv preprint* [arXiv:2610.04825](https://arxiv.org/abs/2610.04825).
- Panickssery, A., Bowman, S. R., & Feng, S. (2024). LLM Evaluators Recognize and Favor Their Own Generations. In *Advances in Neural Information Processing Systems (NeurIPS 2024)*. [arXiv:2404.13076](https://arxiv.org/abs/2404.13076)
- Patall, E. A., Sylvester, B. J., & Han, C.-w. (2014). The role of competence in the effects of choice on motivation. *Journal of Experimental Social Psychology*, 50, 27–44.
- Puech, R., Macina, J., Chatain, J., Sachan, M., & Kapur, M. (2025). Towards the Pedagogical Steering of Large Language Models for Tutoring: A Case Study with Modeling Productive Failure (StratL). In *Findings of ACL 2025*. [aclanthology.org/2025.findings-acl.1348](https://aclanthology.org/2025.findings-acl.1348/)
- Sawyer, R. K. (Ed., 2006). *The Cambridge Handbook of the Learning Sciences*. Cambridge University Press.
- Scarlatos, A., Lee, J., Woodhead, S., & Lan, A. (2026). Simulated Students in Tutoring Dialogues: Substance or Illusion? *arXiv preprint* [arXiv:2601.04025](https://arxiv.org/abs/2601.04025).
- Sharma, M., Tong, M., Korbak, T., Duvenaud, D., Askell, A., Bowman, S. R., et al. (2024). Towards Understanding Sycophancy in Language Models. In *Proceedings of ICLR 2024*. [arXiv:2310.13548](https://arxiv.org/abs/2310.13548)
- Sirdeshmukh, V., et al. (2025). MultiChallenge: A Realistic Multi-Turn Conversation Evaluation Benchmark Challenging to Frontier LLMs. In *Findings of ACL 2025*. [aclanthology.org/2025.findings-acl.958](https://aclanthology.org/2025.findings-acl.958/)
- Srinivasa, R. S., Che, Z., Zhang, C. B. C., Mares, D., Hernandez, E., Park, J., Lee, D., Mangialardi, G., Ng, C., Hernandez Cardona, E.-Y., Gunjal, A., He, Y., Liu, B., & Xing, C. (2025). TutorBench: A Benchmark To Assess Tutoring Capabilities Of Large Language Models. *arXiv preprint* [arXiv:2510.02663](https://arxiv.org/abs/2510.02663).
- Verga, P., Hofstatter, S., Althammer, S., Su, Y., Piktus, A., Arkhangorodsky, A., Xu, M., White, N., & Lewis, P. (2024). Replacing Judges with Juries: Evaluating LLM Generations with a Panel of Diverse Models. *arXiv preprint* [arXiv:2404.18796](https://arxiv.org/abs/2404.18796).
- Wang, R. E., Zhang, Q., Robinson, C., Loeb, S., & Demszky, D. (2024). Bridging the Novice-Expert Gap via Models of Decision-Making: A Case Study on Remediating Math Mistakes (Bridge). In *Proceedings of NAACL 2024*. [aclanthology.org/2024.naacl-long.120](https://aclanthology.org/2024.naacl-long.120/)
- Wang, J., Dai, Y., Zhang, Y., Ma, Z., Li, W., & Chai, J. (2025). Training Turn-by-Turn Verifiers for Dialogue Tutoring Agents: The Curious Case of LLMs as Your Coding Tutors. In *Findings of ACL 2025*. [aclanthology.org/2025.findings-acl.642](https://aclanthology.org/2025.findings-acl.642/)
- Zhao, J., Knežević, M., & Käser, T. (2026). Evaluating Answer Leakage Robustness of LLM Tutors against Adversarial Student Attacks. In *Proceedings of ACL 2026*. [aclanthology.org/2026.acl-long.1412](https://aclanthology.org/2026.acl-long.1412/)

---

## Appendix A: Experimental Prompt, Hint, and Placebo Texts

All treatments were delivered in German (`trainingsdaten/auswertung/dialogbenchmark/v4/pilot/`); English translations are provided below for readability:

- **Core prompt (`p1_kern`, `prompts.json`):** *"You are a tutor in a German-language learning dialogue. The learner wants to understand the topic independently and explain it without you. You lead the conversation: keep track of the learning goal and what has been demonstrated, and set the next step yourself. Speak only as the tutor and leave the learner's next turn open."*
- **Full rules (`p6_voll`, `prompts.json`, 453 `regex-v1` tokens, 2,329 characters):** Prepends `p1_kern` verbatim, then adds seven situational action rules (attempt/justification, unproven agreement, first impasse, repeated impasse / representation shift with small follow-up task, digression, completed section, frustration/shortcut), a factual-judgment-before-tone block, and periodic progress summaries.
- **Fixed one-turn hints (`hinweise.json`, TTL = 1 turn, translated from German):**
  - Case T2 (`STOP_DRIFT`): *"Status: Learning goal is an overview-level understanding of attention in Transformers. Demonstrated: selecting relevant words. Open: interaction with the rest of the model. The last three turns went deeper than this level. Close the detail in one sentence and move to the interaction with the rest of the model."*
  - Case T2 Wrong hint (`falschhinweis`, `faelle.json`): Swaps "demonstrated" and "open" — directs the tutor back to *selecting relevant words* (already mastered) instead of the rest of the Transformer.
  - Case T3 (`HOLD_LEAD`): *"The learner just solved common-denominator addition correctly with justification. State in one sentence what that demonstrates, and pose the next step to two unlike denominators yourself."*
  - Case T7 (`CHECK_EVIDENCE`): *"The learner agreed but has not demonstrated understanding yet. Pose a small application task on mutable Python lists and shared references before moving on."*
  - Case T8 (`SWITCH_MODALITY`): *"The learner failed to understand the same point a second time. Your previous approach was a verbal explanation. Switch to another approach now: a small-number example or text sketch. Return a small task on it afterward."*
  - Case T12 (`KEEP_CONTRACT`): *"Commitment from Turn 3: I will always ask for your guess first and ask exactly one question per turn. It still applies."*
- **Length-matched neutral placebo (`p1_placebo`, `faelle.json`, representative Case T8 wording):** *"System note on conversation flow: This is an ongoing German-language learning chat with full context. All previous messages remain unchanged in the same order. Formulate your regular reply now. The text remains part of the chat as before."*
