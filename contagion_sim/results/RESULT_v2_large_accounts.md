# Retry with large-account agents (development pass, NOT blind)

The CS outcome was already known when this was built, so this checks whether the missing piece explains the gap. It is not a prediction.

## What was added (engine change 7)
- Large depositors as agents. Each agent re-reads its region every 6h and looks up stay / reduce / pull in a playbook written in advance by a Sonnet subagent (24 signal states: adoption level × trend × bank cash × alarm-vs-reassurance).
- Large-account share of deposits from pre-event facts: CS 0.61 (from the LCR split between wholesale and retail funding), 24 agents. SVB 0.67 (from Q4-22 client-niche mix), 27 agents.
- Without a playbook file the engine is unchanged (75/75 SVB runs reproduce exactly).
- One semantics fix after the first CS pass: "reduce" was compounding at every 6h check, so it now means "cut exposure to X% of original" and is applied once.

## Credit Suisse, 72h (actual ≈ 5% of deposits, range 2–8%; the whole of October ≈ 16–23%)
| Engine version | Survives | Withdrawn median (p10–p90) |
|---|---|---|
| v1 no agents (blind) | 100% | 0.5% (0.05–2.9%) |
| v2 agents, compounding reduce | 99.5% | 37% (26–46%) |
| v2 agents, fixed reduce | 100% | 26% (12–38%) |

## SVB regression with agents (actual: ~25% withdrawn Mar 9, ~$100B ≈ 58% more queued for Mar 10, seized Mar 10 morning)
| Response | v1 survival | v2 survival | v2 withdrawn median |
|---|---|---|---|
| Silence | 4% | 0% | 64% |
| CEO call (actual) | 2% | 0% | 64% |
| VC coalition | 11% | 0% | 56% |
| Full backstop | 23% | 0% | 49% |
| Regulator guarantee | 46% | 0% | 46% |

## Reading
1. **The direction is fixed and the size overshoots.** Large accounts were the missing mass: CS goes from 10× too low to about 5× too high. It now roughly matches CS's full October outflow, compressed into 3 days.
2. **The same bias shows in both banks: agents move too fast.** SVB now fails with 64% gone by 06:00 PT Mar 9; in reality about 25% left during Mar 9 and the larger queue came overnight. Agents act at 6h checks through the night on the "alarmed" signal alone. Real treasurers need business hours, approvals and somewhere to move the money.
3. **Agents can't see the company's response.** Their signals don't include an official statement or guarantee, so in SVB a regulator guarantee no longer changes the outcome. This is a design gap, not a finding about guarantees.

## Next fixes (principled, not fitted)
- Agents decide only during their region's business hours, with a decision lag (approval chain).
- Add an "official backstop" signal to the playbook state, so guarantees and committed capital reach large depositors directly.
- Then validate on a THIRD case that hasn't been looked at, because both SVB and CS have now informed the design.
