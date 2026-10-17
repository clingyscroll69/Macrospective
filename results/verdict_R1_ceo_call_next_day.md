# Verdict: R1_ceo_call_next_day

## 1. Verdict
The 11:00 PT Mar 9 CEO "stay calm" call does not save the bank: survival share is 0.02 (95% CI 0.01) across 400 runs.

## 2. Rumour by rumour (top 5 by peak regional conversion)
- **c0_i0** (arsonist, "get your money out TONIGHT"): the strongest single driver. Converted 0.3951 of SF_Bay_Area, with reach of 0.93 there. It also hit New_York (0.1314) and Austin_Seattle_LA (0.094).
- **c4_i0** (arsonist, "anyone with >$250k should be moving"): converted 0.2979 in SF_Bay_Area and 0.1217 in New_York. It also reached London_UK (0.0836).
- **c4_i1** (arsonist, "Israeli founders, be early"): it is the Israel rumour. Converted 0.2702 in Israel, 0.0606 in London_UK and 0.0531 in India, with almost no reach in SF_Bay_Area (0.02).
- **c2_i1** (arsonist, "I moved ours an hour ago"): converted 0.2557 in SF_Bay_Area and 0.0619 in Austin_Seattle_LA.
- **BASE** (the original rumour, present in all 400 runs): converted 0.2407 in SF_Bay_Area, with reach of 0.59 there. It is the top converter in SF_Bay_Area and New_York.

## 3. Region by region
- **SF_Bay_Area**: the epicentre. Median withdrawn share of deposits is 0.141. Alarm peaked Mar 8 22:00 PT, first reassurance came Mar 8 19:00 PT, and the alarm-to-reassurance ratio is 162.03.
- **New_York**: median withdrawn 0.005, ratio 19.91, with rumour peaks around Mar 9 05:00 PT.
- **Boston**: median withdrawn 0.001, ratio 101.26.
- **Austin_Seattle_LA**: median withdrawn 0.001, ratio 14.28.
- **London_UK**: median withdrawn 0.001, ratio 25.76.
- **Israel**: median withdrawn 0.002, ratio 169.71.
- **India**: median withdrawn 0.0, ratio 407.1.
- **Rest_of_US**: median withdrawn 0.0, ratio 7.87, the lowest ratio, but its withdrawals stay at zero.

## 4. Turning point
The engine puts the typical failure at Mar 9 06:00 PT, when the wires open. That is before the CEO call at 11:00 PT. The base alarm peaked Mar 8 22:00 PT in every region, and the first reassurance anywhere arrived Mar 8 18:00 PT (New_York, Austin_Seattle_LA, Rest_of_US). The reassurance came too late and was too weak against alarm that had already built. Median withdrawn before the stop is 0.18.

## 5. Outcome types
- Fails at Mar 9 06:00 PT wire open, led by SF_Bay_Area: 0.73
- Fails later on Mar 9, led by SF_Bay_Area: 0.2
- Fails on Mar 10 or later, led by SF_Bay_Area: 0.03
- Contained (bank survives 72h): 0.02
- Fails at Mar 9 06:00 PT wire open, led by Israel: 0.01

Every failure path is led by SF_Bay_Area except the smallest (0.01), which Israel leads.
