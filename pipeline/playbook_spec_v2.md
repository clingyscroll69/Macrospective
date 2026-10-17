# Large-account playbook spec v2

Each agent is a large depositor. The engine reads its playbook; no LLM runs during the simulation.

## Agent-level fields
- `review_every_hours` (1–12): how often the agent reassesses, counting only hours when it is working.
- `works_after_hours` (bool): true only for desks that monitor and decide around the clock (e.g. hedge-fund treasury, family office with a 24h desk). Otherwise the agent decides only in its region's local business hours (Mon–Fri 08:00–18:00).
- `approval_lag_hours` (0–48): wall-clock hours between deciding and actually submitting the transfer (committee, CFO/board sign-off, finding a destination bank, KYC at the new bank). Submissions also only happen in local business hours. Settlement then waits for the bank's wire window, which the engine handles.
- `deposit_share`, `region`, `archetype`, `instance`, `reason` as before.

## Signals at each review (its own region unless noted)
- `official`: the strongest official message so far (bank-wide):
  - `none`: no official message since the sim started
  - `statement`: the company or an executive has publicly reassured (memo, press statement, CEO call, client outreach), with no new money or guarantee
  - `backstop`: committed external capital, a central-bank/regulator facility, a deposit guarantee, or an acquisition by a strong buyer
- `adopt`: share of retail customers in its region that have withdrawn: `low` (<0.5%), `med` (0.5–3%), `high` (>3%)
- `cash`: bank-wide liquid cash vs start: `safe` (≥50% left) or `stressed` (<50%)
- `sent`: since its last review, alarm read in its region > reassurance read: `alarmed`, else `calm`

Key = "official|adopt|cash|sent". 3×3×2×2 = 36 states; every agent needs all 36.

## Actions
{"action": "stay" | "reduce" | "pull", "fraction": 0..1}
- `reduce`: cut exposure to (1 − fraction) of the ORIGINAL balance. This is a target, so repeating it doesn't drain more.
- `pull`: move everything remaining.
- Once money has left it does not come back within the 72h.

Think realistically: a "statement" from a bank under pressure can reassure some depositors and alarm others ("why are they denying it?"). A "backstop" usually matters far more to uninsured institutional money. Treasurers rarely move hundreds of millions on a single overnight rumour, but they act fast when peers are visibly leaving and cash is stressed.
