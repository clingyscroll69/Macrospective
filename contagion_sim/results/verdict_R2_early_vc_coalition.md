# R2: Early VC coalition statement (Mar 8, 21:00 PT)

## 1. Verdict
The coalition statement does not save SVB: survival share is 0.11 (ci95 0.03) over 400 runs, with typical failure at Mar 9 06:00 PT.

## 2. Rumour by rumour (top 5)
- **c0_i0** (arsonist, "get your money out TONIGHT"): present in 80 runs; converts 0.3674 of SF_Bay_Area and 0.0954 of New_York. Most potent single rumour.
- **c4_i0** (arsonist, "should already be moving"): converts 0.2598 of SF_Bay_Area, 0.0804 of New_York, 0.0414 of London_UK.
- **BASE** (the original VC-pull-out story, all 400 runs): converts 0.2541 of SF_Bay_Area, 0.0234 of New_York; reach_share 0.64 in SF_Bay_Area.
- **c2_i1** ("Do NOT keep operating cash at SVB"): converts 0.2369 of SF_Bay_Area and 0.0508 of Austin_Seattle_LA.
- **c3_i1** ("it's a signal... get out"): converts 0.1716 of SF_Bay_Area and 0.0914 of Boston.

## 3. Region by region
- **SF_Bay_Area** drives the outcome: median withdrawn share of deposits 0.132. Reassurance arrives Mar 8 19:00 PT, but base alarm peaks Mar 8 22:00 PT; alarm-to-reassurance ratio is 6.77, so alarm dominates.
- **New_York**: ratio 1.66, median withdrawn 0.002.
- **Boston**: ratio 0.96, median withdrawn 0.001.
- **Austin_Seattle_LA**: ratio 1.18, median withdrawn 0.0.
- **London_UK**: ratio 0.72, median withdrawn 0.0.
- **Israel**: ratio 1.18, median withdrawn 0.0 (rumours c1_i0 and c4_i1 convert 0.1591 and 0.1691 locally, but this does not move the median).
- **India**: ratio 0.25, median withdrawn 0.0.
- **Rest_of_US**: ratio 0.56, median withdrawn 0.0.

## 4. Turning point
The statement lands at 21:00 PT, after SF_Bay_Area's first reassurance (Mar 8 19:00 PT) and just before base alarm peaks there (Mar 8 22:00 PT). Alarm outweighs reassurance in SF_Bay_Area at 6.77 to 1, and the engine reports a median 0.15 of deposits withdrawn before the stop. The wire opening at Mar 9 06:00 PT is when most runs fail.

## 5. Outcome types
- Fails at Mar 9 06:00 PT wire open, led by SF_Bay_Area: 0.59
- Fails later on Mar 9, led by SF_Bay_Area: 0.25
- Contained (bank survives 72h): 0.11
- Fails on Mar 10 or later, led by SF_Bay_Area: 0.02
- Fails later on Mar 9, led by Israel: 0.01

The engine's outcome stands: the coalition statement is too late and too weak against SF_Bay_Area alarm.
