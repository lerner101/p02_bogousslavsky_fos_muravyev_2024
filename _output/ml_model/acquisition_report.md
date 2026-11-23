# Supplemental TAQ acquisition

Requested: 582,754 stock-days, 4,027 dates, 1,519 stocks.
Saved: 4,027 daily files, 582,754 rows.

Median observed query time: 94.57 seconds/day; measured days contain 10–303 stocks.
Requested daily universe: median 142, maximum 303 stocks.
Fixed daily-time extrapolation: 105.8 connection-hours, before concurrency and tuning.
Stock-day-proportional extrapolation for this request: 105.6 connection-hours.
Full available TAQ-link universe (19,643,596 rows): approximately 3559.7 connection-hours under the same proportional assumption.

These are rough bounds/scenarios, not validated runtime forecasts. Query plans, liquidity, network latency and WRDS load vary.
The full universe has not been requested. Acquisition covers training histories and ten scoring stocks only.
Missing endpoints remain missing; no reduced-feature model has been substituted.
