# Verdict: R3_full_backstop

## 1. Verdict
Even with the strategic investor and discount-window announcement, the bank survives in only 0.23 of 400 runs (CI95 +/- 0.04); the typical failure hour is Mar 9 06:00 PT.

## 2. Rumour by rumour (top 5)
Ranked in the engine's rumour sheet order. SF_Bay_Area converted share shown first.
- **c0_i0** (arsonist, "3 GPs", present in 80 runs): SF_Bay_Area 0.3258, New_York 0.0709, Austin_Seattle_LA 0.0509. The strongest rumour, with SF alarm 0.81 and reach 0.94.
- **c4_i0** (arsonist, ">$250k should be moving"): SF_Bay_Area 0.2156, New_York 0.055, London_UK 0.0324.
- **BASE** (present in all 400 runs): SF_Bay_Area 0.2529, reach 0.68; New_York 0.0223. Median peak in SF is Mar 8 22:00 PT.
- **c3_i1** (arsonist, "the raise is a signal"): SF_Bay_Area 0.1546, Boston 0.0802. The only top rumour that bites in Boston.
- **c2_i1** (arsonist, "I moved ours"): SF_Bay_Area 0.2025, Austin_Seattle_LA 0.0365.

## 3. Region by region
- **SF_Bay_Area** is the engine. Alarm-to-reassurance ratio 3.72, median withdrawn share of deposits 0.125, top converter BASE. Reassurance first lands Mar 8 19:00 PT; the alarm peak follows at Mar 8 22:00 PT.
- **New_York**: ratio 1.0, withdrawn share 0.002, top converter BASE.
- **Boston**: ratio 0.65, top converter c3_i1.
- **Austin_Seattle_LA**: ratio 0.68, top converter c0_i0.
- **London_UK**: ratio 0.62, top converter c4_i0.
- **Israel**: ratio 0.83, top converter c4_i1.
- **India**: ratio 0.15, top converter c4_i1.
- **Rest_of_US**: ratio 0.34, top converter c4_i0.
Boston through Rest_of_US show a withdrawn share of 0.0; reassurance outweighs alarm everywhere except SF_Bay_Area, and New_York is only level with it.

## 4. Turning point
The announcement reaches SF_Bay_Area at Mar 8 19:00 PT, but base alarm still peaks at Mar 8 22:00 PT with a ratio of 3.72, so reassurance does not catch up there. Withdrawals reach a median of 0.14 of deposits before the stop. The pivotal moment is the Mar 9 06:00 PT wire open, where the engine's typical failure falls.

## 5. Outcome types
- Fails at Mar 9 06:00 PT wire open, led by SF_Bay_Area: 0.41
- Fails later on Mar 9, led by SF_Bay_Area: 0.3
- Contained (bank survives 72h): 0.23
- Fails on Mar 10 or later, led by SF_Bay_Area: 0.04
- Fails later on Mar 9, led by Israel: 0.01

The engine's outcome stands: the backstop helps, but SF_Bay_Area alarm outruns it in most runs.
