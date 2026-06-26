# Challenge 2 - Timestamp Autocorrection

## Input

- Source: `/home/CynicalSuperior/Downloads/challenge_2_timeseries-error-autocorrection/timeseries-error-autocorrection-sample-dataset.csv`
- Rows: 81,803

## Method

The repair layer generates candidate datetimes from each raw `date` and `time`, then chooses the candidate that best fits local temporal continuity. It handles mixed date separators, compact dates, compact times, impossible minute values, one-digit hours, copied dates, missing day fields, and rows that need neighbor interpolation.

Rows that still cannot be assigned a timestamp are flagged as `unrecoverable`. The original row order is preserved and an additional `sort_order_after_repair` column shows where each row belongs after repair.

## Results

- Repaired range: `2024-09-15 04:05:00` to `2026-01-13 13:50:00`
- Status counts: {'valid': 81384, 'repaired': 419}
- Rows whose repaired sort order differs from raw order: 12
- Unrecoverable rows: 0
- Cleaned output: `/home/CynicalSuperior/Projects/sensor-fusion/outputs/challenge2/challenge2_cleaned.csv`

## Most Common Reasons

- valid: 81384
- date_context,time_clean: 117
- date_compact,time_clean: 117
- date_format,time_clean: 105
- date_clean,time_format: 42
- date_compact,time_compact: 11
- date_clean,time_compact: 8
- interpolated_from_neighbors: 6
- date_clean,time_value: 5
- date_context_missing_day,time_clean: 2
- date_format,time_format: 1
- date_clean,time_keyboard_slip: 1

## Repair Examples

- row 23: `12.03.2025 12::18` -> `12.03.2025 12:18` (date_clean,time_format)
- row 46: `14.03.2025 18:68` -> `14.03.2025 18:08` (date_clean,time_value)
- row 62: `16.03.2025 18.18` -> `16.03.2025 18:18` (date_clean,time_format)
- row 81: `19.33.2025 09:59` -> `19.03.2025 09:59` (date_context,time_clean)
- row 332: `02.04.202 04:52` -> `02.04.2025 04:52` (date_format,time_clean)
- row 413: `03-04-2025  18:38` -> `03.04.2025 18:38` (date_format,time_clean)
- row 414: `03-04-2025  18:41` -> `03.04.2025 18:41` (date_format,time_clean)
- row 415: `03-04-2025  18:38` -> `03.04.2025 18:38` (date_format,time_clean)
- row 471: `05.04.2025 6:29` -> `05.04.2025 06:29` (date_clean,time_format)
- row 472: `05.04.2025 10.04` -> `05.04.2025 10:04` (date_clean,time_format)
- row 473: `05.04.2025 10.48` -> `05.04.2025 10:48` (date_clean,time_format)
- row 474: `05.04.2025 10.68` -> `05.04.2025 10:58` (date_clean,time_value)
