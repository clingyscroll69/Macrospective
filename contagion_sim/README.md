# Contagion Simulator

Tests a company's response against a rumour by Monte Carlo over one shared social network.
The engine settles the numbers and the LLMs only write inputs (before the runs) and explanations
(after). This repo has two worked scenarios: **SVB, March 2023** and **Credit Suisse, October 2022**.

## Layout

| Path | What it is | Sponsor slot |
|---|---|---|
| `engine.py` | Simulation: network, rumours, retail thresholds, large-account agents, cash budget | Daytona runs it |
| `condense.py` | 1,000 runs → evidence pack (code, no LLM) | - |
| `numcheck.py` | Guardrail: every number in a verdict must appear in the evidence pack | - |
| `pipeline/llm.py` | One entry point for every pre-run LLM call, with caching | **Chalk** (`P.completion`) |
| `pipeline/pre_run.py` | Hour-0 weights, instigator casts, rumour scoring, large-account playbooks | **Chalk** |
| `pipeline/playbook_spec_v2.md` | Spec the playbook writer follows (business hours, approvals, official signal) | Chalk |
| `pipeline/daytona_sweep.py` | Batches of ~50 runs per sandbox, common seeds, merge | **Daytona** |
| `pipeline/droid_analyst.py` | Verdicts, ranking, number check; the Droid tools | **Factory Droid** |
| `pipeline/nessie_globe.py` | One run → globe playback file; optional Nessie withdrawals | **Capital One Nessie** |
| `data/svb/`, `data/cs/` | Frozen inputs for both scenarios (all LLM outputs included) | - |
| `data/actual_responses.json` | Researched timelines of what each bank actually said, and when | - |
| `results/` | Verdicts, the blind backtest (pre-registration + frozen engine), v2/v3 write-ups | - |

## Quick start (no sponsor accounts needed)

```bash
pip install -r requirements.txt
```

```bash
./run_local.sh data/cs 400
```

This uses the frozen inputs already in `data/cs`, runs the sweep locally with the same batching as
Daytona, then condenses and writes verdicts through the Anthropic API (`ANTHROPIC_API_KEY` or `ant auth login`).

## Pipeline

```
Droid intake ──► scenario.json + bank_config.json (facts, actual response_schedule)
                     │
Chalk (pre-run) ─────┼─► hour0_weights.json ─► instigators.json ─► rumour_scores.json ─► large_accounts_v2.json
                     │        (all frozen before any run; every response faces identical LLM output)
Daytona ─────────────┼─► runs.json   (5 responses × 1,000 runs; run k = seed 1000+k, storyline k mod 5)
                     │
code ────────────────┼─► evidence.json (condense.py)
                     │
Droid (final) ───────┴─► verdict_<response>.md ×5 + ranking.md   (numcheck rejects invented numbers)
```

## Integration checklist

Do these first, because they block everything else (plan: "Install droid and confirm Chalk access first").

1. **Chalk** (`pipeline/llm.py`, set `LLM_BACKEND=chalk`):
   - Implement `_chalk_complete` with `P.completion`.
   - Store region facts and company-type settings as Chalk features, not prompt text.
   - Cache on (template, inputs) and log prompt and model versions so the backtests attribute error.
   - I couldn't verify Chalk's Python API, so the function is a marked stub.
2. **Daytona** (`pipeline/daytona_sweep.py`):
   - `pip install daytona`, then pass one key per account via `--api-keys k1,k2,k3,k4`.
   - Every SDK call is marked `VERIFY`. I wrote them from memory and have not run them on Daytona.
   - Bake numpy and scipy into the image, since low tiers may restrict network access.
   - Tier pools: Tier 1 = 10 vCPU, Tier 2 = 100, Tier 3 = 250. Keep `max_parallel × 4 vCPU` under yours.
3. **Factory Droid** (`pipeline/droid_analyst.py`):
   - Register `spawn_instigators`, `create_variant`, `start_sweep` and `fetch_results` as `@tool`s.
   - Droid is async-only, so `start_sweep` should return a job id.
   - Use a `Session` for "what if we announce 3 hours earlier?" (`create_variant`).
   - The prize rule says the README must state where Droid is used, so keep this table accurate.
4. **Nessie** (`pipeline/nessie_globe.py`):
   - Set `NESSIE_KEY` and `NESSIE_ACCOUNTS`, then run with `--post` to replay one run's withdrawals.
   - Bank demo only.

## Adding a new scenario

1. **`scenario.json`:** company type, start time, base rumour, region facts, and `responses`
   (counterfactuals plus `R1_actual`).
2. **`bank_config.json`:** facts only, from filings published before the event.
   - Regions, region shares, time-zone offsets, start hour and weekday, closed weekdays, wire hours.
   - Insurance limit, `cash_share`, `liquidity_schedule`.
   - `response_schedule`: for each response, a list of `{id, hour, type: statement|backstop}`.
     Put the company's *actual* statements at their actual times. Exclude closures and halts, which are
     outcomes, and anything before the start, which is already in the rumour context.
3. **`official_texts`** in `scenario.json`: text for each actual-statement id, so it gets scored.
4. **`large_account_facts.json`:** large-account share of deposits plus archetypes, from filings.
5. Then:

   ```bash
   python -m pipeline.pre_run data/<new>
   ```

   ```bash
   python -m pipeline.daytona_sweep data/<new> --runs 1000
   ```

   ```bash
   python condense.py data/<new>
   ```

   ```bash
   python -m pipeline.droid_analyst data/<new>
   ```

**For a blind backtest:**
- Hash `engine.py`.
- Write the prediction to a file and hash it.
- Only then research the outcome, using a researcher that never sees the prediction. `results/` shows the CS example.

## What's been validated (and what hasn't)

| Version | SVB | CS (72h, actual ~5%) | Notes |
|---|---|---|---|
| v1 retail only (blind for CS) | fails 06:00 PT Mar 9 | 0.5%: 10× too low | survival direction right |
| v2 + large-account agents | fails, 64% gone | 26%: 5× too high | agents compounding / overnight |
| v3 business hours, approvals, official signal, actual statements | fails 07:00 PT Mar 9 | **8.2% (2.6–15%)**: in range | not blind (outcomes known) |

Open problems, analysed but not fixed:
1. **SVB cash is too low.** `cash_share` 0.10 plus 0.08 at 09:00 PT were never sourced from filings.
   The real bank absorbed about 24% on Mar 9, so the engine fails at 13% gone.
2. **Withdrawals are truncated at failure.** The run stops at the failure hour, so "withdrawn" isn't comparable to full-day
   records. With failure disabled, SVB loses 34% during Thursday against 24% in reality.
3. **The run is front-loaded.** Approved large-account transfers all release at 08:00 local, and the overnight retail
   queue settles at the wire opening. Spread both through the business day.
4. **No untouched case yet.** SVB and CS have both shaped the design, so the next honest test needs a third bank
   (First Republic or PacWest, spring 2023).

## Performance

Measured on a laptop: about 1.2–1.6 CPU-seconds per 72h run at N=4,000.

- **Base case:** 5 × 1,000 runs is about 2–3 vCPU-hours. That's about 15–20 minutes on Tier 1 and about 1.5–2 minutes on Tier 2.
- **Cost:** about $0.20 at list price.

Before raising N to the plan's 20k–100k:
- **Vectorise `build_world()`.** It is roughly O(N²) because of per-node `rng.choice`.
- **Optional:** move the hourly loop to Numba (`cache=True`).

No performance optimisations have been made yet. The changes so far are correctness and features
(config-driven facts, agents, batching).

## Caveats to put in your pitch

- Some inputs are judgment, not disclosure: the uninsured split for CS, the per-niche large-account
  fractions for SVB, and many statement times.
- Scoring batches a whole region's messages in one call, so the evaluator may judge rumours against each other.
- "Blind" here means frozen parameters. The models knew the general story of both banks.
