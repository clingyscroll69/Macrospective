# Verdict: R0_silence

## 1. Verdict
Under silence (no statement beyond the original press release), the bank survives 72h in only 0.04 of 400 runs (CI95 +/- 0.02), with typical failure at Mar 9 06:00 PT.

## 2. Rumour by rumour (top 5)
Ordered as in the engine's rumour sheet; each was present in 80 runs.
- **c0_i0** (arsonist, "get your money out of SVB TONIGHT"): converts 0.3631 of SF_Bay_Area and 0.1268 of New_York; reach 0.92 in SF_Bay_Area.
- **c4_i0** (arsonist, ">$250k should already be moving"): converts 0.2941 of SF_Bay_Area, 0.1268 of New_York and 0.0849 of London_UK.
- **c4_i1** (arsonist, Israeli founders): converts 0.311 of Israel, 0.0651 of London_UK, 0.0506 of India.
- **c1_i0** (arsonist, "Israeli founders, pull your funds"): converts 0.21 of Israel and 0.1538 of SF_Bay_Area.
- **c3_i1** (arsonist, "If your VC hasn't called you yet"): converts 0.1755 of SF_Bay_Area and 0.1392 of Boston.

The BASE rumour (400 runs) converts 0.2507 of SF_Bay_Area.

## 3. Region by region
- **SF_Bay_Area**: median withdrawn share of deposits 0.135; alarm-to-reassurance ratio 160.68; top converter BASE. It leads nearly every failure.
- **New_York**: 0.004 withdrawn; ratio 20.63; top converter BASE.
- **Boston**: 0.001; ratio 116.12; top converter c3_i1.
- **Austin_Seattle_LA**: 0.001; ratio 13.47; top converter c0_i0.
- **London_UK**: 0.001; ratio 23.78; top converter c4_i0.
- **Israel**: 0.002; ratio 214.87; top converter c4_i1.
- **India**: 0.0; ratio 378.33; top converter c4_i1.
- **Rest_of_US**: 0.0; ratio 7.35; top converter c2_i1.

## 4. Turning point
Every region's base alarm peaks at Mar 8 22:00 PT. First reassurance arrives Mar 8 18:00 PT in SF_Bay_Area, New_York, Austin_Seattle_LA and Rest_of_US, and later elsewhere (Mar 8 20:00 PT in Boston, Israel and India; Mar 8 21:00 PT in London_UK). Alarm outweighs reassurance everywhere, so the bank typically fails at Mar 9 06:00 PT, with a median 0.17 withdrawn before the stop.

## 5. Outcome types
- Fails at Mar 9 06:00 PT wire open, led by SF_Bay_Area: 0.68
- Fails later on Mar 9, led by SF_Bay_Area: 0.24
- Contained (bank survives 72h): 0.04
- Fails on Mar 10 or later, led by SF_Bay_Area: 0.01
- Fails at Mar 9 06:00 PT wire open, led by London_UK: 0.01
