# v3: realistic playbooks + actual official responses (development pass, NOT blind)

## Changes
- **Playbooks v2** (spec: playbook_spec_v2.md), written by Sonnet subagents:
  - Agents decide only in their region's business hours, unless they're a 24h desk.
  - Each has its own review frequency and approval delay (0–48h); approved transfers are submitted in business hours.
  - New `official` signal (none / statement / backstop). 36 states per agent, all actions judged by hand.
- **Actual response timelines** (actual_responses.json, researched; many exact times unpublished):
  - SVB: Becker "stay calm" call (~13:00 PT Mar 9); relationship-manager emails saying "business as usual" (~18:00 PT Mar 9). Both are statements.
  - CS: executive outreach to top clients (~10:00 Sun Oct 2); client talking points and "no formal approach for capital" (~09:00 Mon Oct 3). Both are statements.
  - Excluded: pre-start announcements (already in the starting context), trading halt and closure (outcomes), the Mar 12 guarantee (outside the window).
- Without playbooks the engine is unchanged (75/75 SVB runs reproduce exactly).

## Credit Suisse, 72h (actual ≈ 5%, range 2–8%)
| Version | Withdrawn median (p10–p90) |
|---|---|
| v1 no agents (blind) | 0.5% (0.05–2.9%) |
| v2 agents | 26% (12–38%) |
| **v3 actual responses** | **8.2% (2.6–15%)** |
| v3 silence (counterfactual) | 10.7% (4.8–18%) |

The actual falls inside the band. The real outreach is worth about 2.5 points against silence.

## SVB (actual: about 24% withdrawn during Mar 9, closed morning of Mar 10)
| Response | Survival | Withdrawn median | Typical failure |
|---|---|---|---|
| Silence | 0% | 12% | 07:00 PT Mar 9 |
| Actual (Becker call + RM emails) | 0% | 12% | 07:00 PT Mar 9 |
| VC coalition | 0% | 14% | 08:00 PT Mar 9 |
| Full backstop | 0% | 13% | 08:00 PT Mar 9 |
| Regulator guarantee | 1.5% | 13% | 08:00 PT Mar 9 (15% of runs reach Mar 10) |

**Diagnosis:** the agents now behave plausibly. Large accounts move only about 7–9% before the failure point, versus 60% in v2. But SVB fails at about 12% withdrawn, half of what the real bank absorbed on Mar 9. The cause is the cash inputs: 10% on hand plus 8% raised at 09:00 PT were my guesses in the first run and were never sourced from filings. In reality SVB borrowed through Mar 9 and was only short by evening. Backstops barely help because the bank is already dry before most treasurers' approvals clear. That reflects the cash inputs, not the value of a guarantee.

**Next step:** source SVB's real Mar 9 liquidity (cash, FHLB/discount-window capacity and timing) and rerun. Then do a blind test on an untouched third bank.
