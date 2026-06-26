# Sensor Fusion Challenge

Reproducible solution for the battlefield data challenges:

- Challenge 1: geo-temporal multi-source intelligence fusion
- Challenge 2: datetime series autocorrection
- Challenge 3: UAV and ground activity correlation

The pipeline reads the challenge files from `/home/CynicalSuperior/Downloads` by default and writes generated artifacts under this repository.

## Quick Start

```bash
cd /home/CynicalSuperior/Projects/sensor-fusion
python scripts/run_all.py
pytest -q
```

To use another data folder:

```bash
python scripts/run_all.py --data-root /path/to/data
```

## Outputs

Generated CSV artifacts are saved locally under `outputs/`:

- `outputs/challenge1/normalized_events.csv`
- `outputs/challenge1/fusion_clusters.csv`
- `outputs/challenge1/source_summary.csv`
- `outputs/challenge1/sample_geo_temporal_query.csv`
- `outputs/challenge2/challenge2_cleaned.csv`
- `outputs/challenge2/challenge2_repair_summary.csv`
- `outputs/challenge3/daily_activity_counts.csv`
- `outputs/challenge3/daily_lag_correlation.csv`
- `outputs/challenge3/lead_lag_proximity.csv`
- `outputs/challenge3/spatial_hotspots.csv`

Markdown reports are tracked in `reports/`:

- `reports/challenge1_fusion.md`
- `reports/challenge2_timestamp_repair.md`
- `reports/challenge3_uav_ground_correlation.md`

Large generated CSVs are gitignored because they are reproducible from the source data and should not be committed unintentionally.

## Challenge 1

The fusion pipeline normalizes UAV, EW, SIGINT, satellite, communication asset, artillery, and EW report data into a shared event contract:

```text
source, source_id, object_id, observed_at, created_at,
lat, lon, end_lat, end_lon, geometry_type, object_type,
app6_type, identity, status, quantity, trust, source_type,
mission, uav_type, result, route_identification, route_type,
signal_type, confidence, grid_cell, observed_date, time_bucket_6h
```

Because `object_id` is not a universal cross-source key, the fusion layer uses conservative candidate clustering by:

- 0.02 degree spatial grid
- 6 hour time bucket
- normalized object family

This produces analyst-reviewable fusion clusters rather than overclaiming object identity.

## Challenge 2

The timestamp repair layer generates candidate datetimes from dirty `date` and `time` fields, scores them against neighboring records, and outputs:

- original date/time
- repaired date/time
- parsed `repaired_datetime`
- `repair_status`
- `repair_reason`
- repaired sort order
- raw out-of-order flag

It handles mixed separators, compact date/time formats, impossible minute values, one-digit hours, copy/paste date errors, missing days, and interpolation from neighboring rows.

## Challenge 3

The correlation pipeline treats UAV/EW and infantry data as aggregate activity streams because there are no shared identifiers. It reports:

- active temporal overlap
- daily lead/lag correlation
- burst days
- spatial grid hotspots
- nearby UAV/infantry co-occurrence within 10 km and +/-72 hours

The current data shows temporal correlation signals, but no 10 km spatial-temporal proximity matches and no same-cell overlap at 0.05 degree grid resolution. That is reported as a negative finding rather than hidden.

## Tests

Unit tests focus on the highest-risk timestamp repair cases:

```bash
pytest -q
```

Current verification: 4 tests passing, and `python scripts/run_all.py` completes all three challenge pipelines.

