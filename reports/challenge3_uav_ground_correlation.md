# Challenge 3 - UAV and Ground Activity Correlation

## Objective

Detect behavioral patterns and quantify how UAV/EW activity and infantry movement relate across time and space.

## Data Used

- UAV/EW activity records after coordinate/time cleaning: 29,727
- Infantry movement records after coordinate/time cleaning: 16,999
- Raw temporal overlap: `2025-09-03 09:23:00` to `2026-01-13 09:14:50.058000`
- Active overlap used for statistics: `2025-12-06 00:00:00` to `2026-01-13 23:59:59.999999999`

The two datasets do not share identifiers, so the analysis uses aggregate time-space evidence rather than direct row joins.

## Temporal Correlation

Best daily lag correlation: lag `2` days, Pearson `0.631` across 38 paired days.

## Burst Days

UAV/EW bursts:

- none

Infantry bursts:

- 2026-01-09: 159 infantry events
- 2026-01-07: 138 infantry events

## Spatial-Temporal Proximity

For each infantry event in the overlap period, the pipeline counts UAV/EW events within 10 km and +/-72 hours, grouped into 6-hour lead/lag bins. Positive lag means the UAV/EW event happened before the infantry event.

- No UAV/EW events were found within 10 km and +/-72 hours of infantry events.

## Spatial Hotspots

No same-cell UAV/infantry overlap exists at 0.05 degree grid resolution.

Top UAV/EW cells:
- g0.050_1031_757: 742 UAV/EW events
- g0.050_1032_757: 700 UAV/EW events
- g0.050_1031_755: 604 UAV/EW events
- g0.050_1031_758: 582 UAV/EW events
- g0.050_1031_760: 457 UAV/EW events

Top infantry cells:
- g0.050_1005_735: 302 infantry events
- g0.050_1005_734: 297 infantry events
- g0.050_1004_732: 288 infantry events
- g0.050_1005_736: 175 infantry events
- g0.050_1005_732: 119 infantry events

## Interpretation

The reproducible evidence is strongest at the aggregate level. The available data supports quantified statements about overlap windows, bursts, lag bins, and hotspot cells. It does not support identity-level claims that a specific UAV event caused a specific infantry movement.
