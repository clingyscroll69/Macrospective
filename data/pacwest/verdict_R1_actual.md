# PacWest contagion: R1_actual

## 1. Verdict
**The bank is contained in 97% of 250 runs (±0.02), so it survives 72h under the actual press release.** Median withdrawn before the stop is 0.22.

## 2. Rumour by rumour (top 5 by converted share)
- **c2_i0** (Arsonist 1, ~400k followers): the strongest. Converted share is 0.3106 in US_Venture_Hubs and 0.2186 in SF_Bay_Area. Reach is 0.94 and 0.92 respectively. It is the top converter in US_Venture_Hubs and Rest_of_US.
- **c1_i1**: converted share is 0.2028 in SF_Bay_Area and 0.1686 in US_Venture_Hubs. Its reach of 0.83 in Los_Angeles_SoCal is the widest of the top five there.
- **c4_i0**: converted share is 0.2331 in US_Venture_Hubs and 0.1563 in SF_Bay_Area.
- **c0_i0**: converted share is 0.195 in US_Venture_Hubs and 0.1232 in SF_Bay_Area. It has the highest Los_Angeles_SoCal conversion of the arsonists at 0.041.
- **c1_i0**: converted share is 0.193 in US_Venture_Hubs and 0.1216 in SF_Bay_Area.

BASE is present in all 250 runs and is the top converter in three regions. The c3_i2 mutator has high scored alarm (0.71) but almost no reach (0.05 at most), so it has little effect.

## 3. Region by region
- **SF_Bay_Area:** alarm-to-reassurance ratio is 4.4 and median withdrawn share is 0.099. This is the most stressed region, along with the venture hubs.
- **US_Venture_Hubs:** the ratio is 4.85 and median withdrawn share is 0.095, the highest of any region. Rumour peaks come at Thu 06:00 PT.
- **Los_Angeles_SoCal:** the ratio is 1.62 and withdrawn share is 0.016. BASE is the top converter.
- **Rest_of_California:** the ratio is 1.18 and withdrawn share is 0.0.
- **Rest_of_US:** the ratio is 0.83, below parity, and withdrawn share is 0.0.

## 4. Turning point
Reassurance first appears at Wed 19:00 PT in four regions, and at Wed 20:00 PT in Rest_of_California. BASE alarm peaks at Wed 21:00 PT in every region. The engine's outcome rests on reassurance arriving before the alarm peaked. Only in the two tech-heavy regions did alarm still outweigh reassurance, by ratios of 4.4 and 4.85, and the venture-hub rumours kept peaking into Thu 06:00 PT.

## 5. Outcome types
- Contained (survives 72h): 0.97.
- Failure scenarios (Thu 06:00 PT and Thu 14:00 PT for US_Venture_Hubs or Los_Angeles_SoCal, Thu 17:00 PT, Fri 06:00 PT): each 0.0.

The typical failure hour, Fri 06:00 PT, describes the rare failing runs only. Failures that do occur are led by Los_Angeles_SoCal and US_Venture_Hubs, but they are too rare to register in any single outcome type.