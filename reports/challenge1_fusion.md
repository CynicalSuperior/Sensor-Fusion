# Challenge 1 - Geo-Temporal Intelligence Fusion

## Objective

Create one searchable battlefield event model from UAV, EW, SIGINT, satellite, communication asset, and artillery data.

## Normalized Event Contract

Each source is mapped into:

`source, source_id, object_id, observed_at, created_at, lat, lon, end_lat, end_lon, geometry_type, object_type, app6_type, identity, status, quantity, trust, source_type, mission, uav_type, result, route_identification, route_type, signal_type, confidence, grid_cell, observed_date, time_bucket_6h`

## Data Loaded

- Normalized events: 78,953
- Fusion clusters: 63,825
- Observation range: `2024-02-02 15:48:00` to `2026-01-13 09:24:10.728000`

## Source Summary

- uav_observation: 25,703 normalized events, 0 missing coordinates, 2024-02-02 15:48:00 to 2026-01-13 06:43:44.972000
- ew_report: 22,360 normalized events, 0 missing coordinates, 2025-09-30 22:15:00 to 2026-01-13 06:10:00
- artillery: 21,758 normalized events, 0 missing coordinates, 2025-09-30 20:09:30 to 2026-01-13 09:24:10.728000
- ew_observation: 7,367 normalized events, 0 missing coordinates, 2025-09-03 09:23:00 to 2026-01-13 09:14:50.058000
- sigint: 899 normalized events, 0 missing coordinates, 2024-09-14 10:09:31 to 2026-01-10 00:00:00
- communication_asset: 519 normalized events, 0 missing coordinates, 2025-10-20 00:00:00 to 2026-01-12 10:20:04.289000
- satellite: 347 normalized events, 0 missing coordinates, 2025-10-06 17:23:00 to 2026-01-08 12:25:00

## Fusion Method

Direct identifiers are sparse across sources, so `object_id` is preserved but not treated as the universal join key. The fusion layer uses a conservative geo-temporal bucket:

- spatial bucket: 0.02 degree grid cell
- time bucket: 6 hour window
- semantic bucket: normalized object family

This produces reproducible candidate clusters for analyst review. The cluster score increases when independent sources and repeated observations agree in the same cell/time/object-family bucket.

## Highest-Value Fusion Clusters

- C000001: unknown in g0.020_2580_1906, 13 events from 3 sources, score 0.95
- C000002: unknown in g0.020_2579_1907, 4 events from 3 sources, score 0.897
- C000003: unknown in g0.020_2579_1910, 4 events from 3 sources, score 0.897
- C000004: unknown in g0.020_2579_1908, 3 events from 3 sources, score 0.888
- C000005: unknown in g0.020_2580_1907, 3 events from 3 sources, score 0.888
- C000006: unknown in g0.020_2580_1889, 3 events from 3 sources, score 0.888
- C000007: unknown in g0.020_2578_1907, 3 events from 3 sources, score 0.888
- C000008: unknown in g0.020_2585_1891, 13 events from 2 sources, score 0.904
- C000009: unknown in g0.020_2586_1892, 13 events from 2 sources, score 0.904
- C000010: unknown in g0.020_2585_1891, 13 events from 2 sources, score 0.904

## Query Layer

The sample query output demonstrates the intended analyst operation: "what happened in this grid cell on this date, ordered by time?"

- Sample query CSV: `/home/CynicalSuperior/Projects/sensor-fusion/outputs/challenge1/sample_geo_temporal_query.csv`

## Limitations

The method avoids overclaiming identity-level fusion where sources do not share identifiers. It is a candidate fusion model, designed to be explainable and auditable before operational use.
