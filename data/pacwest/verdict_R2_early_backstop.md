# PacWest Contagion Simulation: R2_early_backstop

## 1. Verdict
**The bank is contained in 0.99 of 250 runs (ci95 ±0.01); median withdrawn before stop is 0.11.**

## 2. Rumour by rumour (top 5)
Ranked by converted share where the rumour had the most impact.

- **c2_i0 (Arsonist 1, ~400k followers):** This is the strongest in US_Venture_Hubs, with converted share 0.1632 and reach 0.91. It also converted 0.1184 in SF_Bay_Area. It is present in 50 runs.
- **c1_i1 (fintech/VC-adjacent personality):** This is the strongest in SF_Bay_Area, with converted share 0.1512 and reach 0.87. It also reached 0.8 in Los_Angeles_SoCal, converting 0.0194.
- **c1_i0:** It converted 0.1077 in US_Venture_Hubs and 0.096 in SF_Bay_Area. Its reach in Los_Angeles_SoCal is only 0.11.
- **c0_i0:** It converted 0.0833 in SF_Bay_Area and 0.0828 in US_Venture_Hubs. It has the highest Los_Angeles_SoCal conversion of the top five, at 0.0218.
- **c4_i0:** It converted 0.0821 in US_Venture_Hubs and 0.0783 in SF_Bay_Area. Its Los_Angeles_SoCal reach is 0.15.

The BASE rumour reached 0.28 of Los_Angeles_SoCal and converted 0.0213 there. The mutator c4_i2 (invented wire limits) had reach of 0.02 or less everywhere, so it barely spread.

## 3. Region by region
- **Los_Angeles_SoCal:** First reassurance came Wed 19:00 PT, ahead of the Wed 21:00 PT alarm peak. The alarm-to-reassurance ratio is 0.69 and median withdrawn share is 0.003.
- **SF_Bay_Area:** This region is the most stressed. Its ratio is 1.65 (alarm exceeds reassurance), with median withdrawn share 0.058. Its top converter is c1_i1.
- **Rest_of_California:** First reassurance came Wed 20:00 PT. The ratio is 0.26 and median withdrawn share is 0.0.
- **US_Venture_Hubs:** The ratio is 1.05 and median withdrawn share is 0.051. Its top converter is c2_i0.
- **Rest_of_US:** The ratio is 0.38 and median withdrawn share is 0.0.

## 4. Turning point
Reassurance arrived at Wed 19:00 PT in four of the five regions (Rest_of_California followed at 20:00). All of this came before the shared Wed 21:00 PT alarm peak. The backstop therefore landed ahead of the peak. Only SF_Bay_Area (1.65) and US_Venture_Hubs (1.05) saw alarm outweigh reassurance. Even there, withdrawals stayed at 0.058 and 0.051 of deposits, and the bank did not fail.

## 5. Outcome types
- Contained (bank survives 72h): 0.99
- Fails Thu 16:00 PT, led by Los_Angeles_SoCal: 0.0
- Fails Thu 14:00 PT, led by US_Venture_Hubs: 0.0
- Fails Fri 09:00 PT, led by Los_Angeles_SoCal: 0.0

The typical failure hour in the rare failing runs is Thu 16:00 PT.