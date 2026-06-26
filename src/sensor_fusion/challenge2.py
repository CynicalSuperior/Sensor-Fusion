from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import data_root, output_root, reports_root
from .timestamp_repair import repair_dataframe


INPUT_REL = "challenge_2_timeseries-error-autocorrection/timeseries-error-autocorrection-sample-dataset.csv"


def run(data_dir: str | Path | None = None, out_dir: str | Path | None = None, report_dir: str | Path | None = None) -> dict[str, Path]:
    root = data_root(data_dir)
    outputs = output_root(out_dir) / "challenge2"
    reports = reports_root(report_dir)
    outputs.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)

    src = root / INPUT_REL
    df = pd.read_csv(src, dtype=str, keep_default_na=False)
    repaired = repair_dataframe(df, "date", "time")

    cleaned_path = outputs / "challenge2_cleaned.csv"
    repaired.to_csv(cleaned_path, index=False)

    summary = (
        repaired.groupby(["repair_status", "repair_reason"], dropna=False)
        .size()
        .reset_index(name="rows")
        .sort_values(["repair_status", "rows"], ascending=[True, False])
    )
    summary_path = outputs / "challenge2_repair_summary.csv"
    summary.to_csv(summary_path, index=False)

    report_path = reports / "challenge2_timestamp_repair.md"
    report_path.write_text(_report(repaired, src, cleaned_path), encoding="utf-8")
    return {"cleaned": cleaned_path, "summary": summary_path, "report": report_path}


def _report(df: pd.DataFrame, src: Path, cleaned_path: Path) -> str:
    status_counts = df["repair_status"].value_counts().to_dict()
    reason_counts = df["repair_reason"].value_counts().head(12)
    unrecoverable = int((df["repair_status"] == "unrecoverable").sum())
    out_of_order = int(df["raw_out_of_order_after_repair"].sum())
    min_dt = df["repaired_datetime"].min()
    max_dt = df["repaired_datetime"].max()

    reason_lines = "\n".join(f"- {reason}: {count}" for reason, count in reason_counts.items())
    examples = df[df["repair_status"] == "repaired"].head(12)
    example_lines = "\n".join(
        f"- row {int(row.raw_row_index)}: `{row.original_date} {row.original_time}` -> "
        f"`{row.repaired_date} {row.repaired_time}` ({row.repair_reason})"
        for row in examples.itertuples()
    )

    return f"""# Challenge 2 - Timestamp Autocorrection

## Input

- Source: `{src}`
- Rows: {len(df):,}

## Method

The repair layer generates candidate datetimes from each raw `date` and `time`, then chooses the candidate that best fits local temporal continuity. It handles mixed date separators, compact dates, compact times, impossible minute values, one-digit hours, copied dates, missing day fields, and rows that need neighbor interpolation.

Rows that still cannot be assigned a timestamp are flagged as `unrecoverable`. The original row order is preserved and an additional `sort_order_after_repair` column shows where each row belongs after repair.

## Results

- Repaired range: `{min_dt}` to `{max_dt}`
- Status counts: {status_counts}
- Rows whose repaired sort order differs from raw order: {out_of_order:,}
- Unrecoverable rows: {unrecoverable:,}
- Cleaned output: `{cleaned_path}`

## Most Common Reasons

{reason_lines}

## Repair Examples

{example_lines}
"""

