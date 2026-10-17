# PacWest under R0_silence: engine readout

## 1. Verdict
The bank survives 72h in 0.93 of 250 runs (±0.03 at 95% CI), but the median run still sees 0.28 of deposits withdrawn before the stop.

## 2. Rumour by rumour (top 5, by converted share)
1. **c2_i0** (Arsonist 1, ~400k followers, present in 50 runs): the strongest converter. It converts 0.4011 in US_Venture_Hubs and 0.2884 in SF_Bay_Area. Reach is 0.95 and 0.94 respectively. It is the top converter in US_Venture_Hubs and Rest_of_US.
2. **c4_i0** (310k followers): converts 0.3398 in US_Venture_Hubs and 0.2414 in SF_Bay_Area.
3. **c0_i0** (VC-commentary account): converts 0.3177 in US_Venture_Hubs. It is the strongest in Los_Angeles_SoCal, at 0.0979 converted with 0.82 reach.
4. **c1_i1**: converts 0.2466 in SF_Bay_Area and 0.2183 in US_Venture_Hubs. It also reaches Los_Angeles_SoCal (0.85), converting 0.0793.
5. **c1_i0** and **c3_i0** are close behind. c3_i0 converts 0.238 in US_Venture_Hubs, and c1_i0 converts 0.247.

**BASE** (all 250 runs) is the top converter in three regions, led by Los_Angeles_SoCal at 0.0844. The YC chat mutator (c3_i2) barely spreads, with a reach of 0.04 at most.

## 3. Region by region
- **Los_Angeles_SoCal:** the alarm-to-reassurance ratio is 10.04. Median withdrawn share is 0.039. BASE is the top converter. This region leads the few failure types.
- **SF_Bay_Area:** the ratio is 13.84 and the median withdrawn share is 0.111, the highest of any region. BASE is the top converter.
- **Rest_of_California:** the ratio is 22.84, but median withdrawn is only 0.002.
- **US_Venture_Hubs:** the ratio is 16.83 and median withdrawn is 0.108. The top converter is c2_i0.
- **Rest_of_US:** the ratio is 4.15, the lowest, and median withdrawn is 0.002. The top converter is c2_i0.

## 4. Turning point
First reassurance appears Wed 19:00 PT in four regions (Wed 20:00 PT in Rest_of_California). Base alarm peaks at Wed 22:00 PT everywhere. In every region, alarm outweighs reassurance by a wide margin. Venture-hub and Bay Area spread peaks then land Wed 19:00 to Thu 06:00 PT, before the Thursday open. Still, most runs hold. The typical failure hour is Fri 08:00 PT.

## 5. Outcome types
- Contained (bank survives 72h): 0.93
- Fails Fri 10:00 PT, led by Los_Angeles_SoCal: 0.01
- Fails Fri 15:00 PT, led by Los_Angeles_SoCal: 0.01
- Fails Fri 14:00 PT, led by Los_Angeles_SoCal: 0.01
- Fails Fri 11:00 PT, led by US_Venture_Hubs: 0.0

Silence does not stop the rumours from reaching venture depositors. In this simulation, though, the bank mostly survives, and the rare failures are led by Los_Angeles_SoCal.