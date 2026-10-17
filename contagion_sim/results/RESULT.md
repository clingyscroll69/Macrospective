# Blind backtest: Credit Suisse, Oct 1–4 2022

Engine frozen after the SVB run (engine.py sha256 17f3b916…). The config refactor reproduced 75/75 SVB runs exactly.
The prediction was pre-registered in PREREGISTRATION.json (sha256 099eba2a…, unchanged) before the outcome was researched, by a separate subagent that never saw the prediction.

| Test | Predicted (actual-response arm, 400 runs) | Record (actual_outcome.json) | Grade |
|---|---|---|---|
| Survives 72h | 100% of runs | Survived, no rescue in window | **PASS** |
| Deposits withdrawn in 72h | median 0.5%, p10–p90 0.05–2.9% | best estimate ~5% (range 2–8%), derived, no direct figure | **FAIL**: about 10× too low; only the low end of the record range touches the band |
| Where it hit | Asia-Pacific led, Switzerland ≈ 0 | Wealth Management across all regions, Asia hinted; Swiss retail ~1% | Directionally consistent, weak evidence |

## Why the size misses (diagnosis, not a fix)
1. **No large-account agents.** CS outflows came from wealth and institutional clients deciding through relationship managers. The plan's large-account agents (engine change 7) aren't built, and consumer-style thresholds tuned on SVB start-ups don't capture them.
2. **No market-signal channel.** CDS and share price kept moving all through the window, but the engine only reacts to rumours people read.
3. **Thresholds calibrated on a single case.** The thresholds come from SVB, and the evaluators scored Swiss alarm at 0.3–0.4, against 0.95 for SF. So almost nobody crosses the threshold.
4. **The 72-hour horizon misses a slow drain.** About 16–23% of deposits left over October, a pattern this engine doesn't model.

## Caveats
- The 72h "actual" is a judgment estimate derived from quarterly and monthly disclosures, not a reported figure.
- "Blind" means parameters were frozen. The models still knew the broad CS story.
- n = 1 backtest. A pass on survival direction is weak evidence on its own.
