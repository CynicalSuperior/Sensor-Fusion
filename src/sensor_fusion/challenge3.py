from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from .challenge1 import parse_datetime
from .config import data_root, output_root, reports_root
from .geo import add_grid_cell, to_local_km


def _activity_from_ew_report(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    observed = parse_datetime(df["timestamp"])
    lat = df["end_point_latitude"].fillna(df["start_point_latitude"])
    lon = df["end_point_longitude"].fillna(df["start_point_longitude"])
    return pd.DataFrame(
        {
            "source": "ew_report",
            "observed_at": observed,
            "lat": lat,
            "lon": lon,
            "activity_type": df["mission"].astype(str) + "/" + df["uav_type"].astype(str),
            "result": df["result_text_category"],
        }
    )


def _activity_from_ew_observation(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    observed = parse_datetime(df["date_observe"]).fillna(parse_datetime(df["date_create"]))
    return pd.DataFrame(
        {
            "source": "ew_observation",
            "observed_at": observed,
            "lat": df["start_point_latitude"],
            "lon": df["start_point_longitude"],
            "activity_type": df["object_type"].astype(str) + "/" + df["ew_type_normalized"].astype(str),
            "result": df["status"],
        }
    )


def _activity_from_infantry(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    observed = parse_datetime(df["date_observe"]).fillna(parse_datetime(df["date_create"]))
    return pd.DataFrame(
        {
            "source": "infantry",
            "observed_at": observed,
            "lat": df["start_point_latitude"],
            "lon": df["start_point_longitude"],
            "activity_type": df["object_type"].astype(str) + "/" + df["route_type"].fillna("").astype(str),
            "quantity": pd.to_numeric(df["quantity"], errors="coerce").fillna(1),
        }
    )


def load_activities(root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    uav = pd.concat(
        [
            _activity_from_ew_report(root / "challenge_3_infantry_uav/ew_report_data.csv"),
            _activity_from_ew_observation(root / "challenge_3_infantry_uav/ew_data.csv"),
        ],
        ignore_index=True,
        sort=False,
    )
    infantry = _activity_from_infantry(root / "challenge_3_infantry_uav/infantry_movement_data.csv")
    uav = uav.dropna(subset=["observed_at", "lat", "lon"]).copy()
    infantry = infantry.dropna(subset=["observed_at", "lat", "lon"]).copy()
    uav = add_grid_cell(uav, "lat", "lon", resolution_deg=0.05)
    infantry = add_grid_cell(infantry, "lat", "lon", resolution_deg=0.05)
    return uav, infantry


def overlap_window(uav: pd.DataFrame, infantry: pd.DataFrame) -> tuple[pd.Timestamp, pd.Timestamp]:
    start = max(uav["observed_at"].min(), infantry["observed_at"].min())
    end = min(uav["observed_at"].max(), infantry["observed_at"].max())
    return start, end


def active_overlap_window(uav: pd.DataFrame, infantry: pd.DataFrame) -> tuple[pd.Timestamp, pd.Timestamp]:
    raw_start, raw_end = overlap_window(uav, infantry)
    u = uav[(uav["observed_at"] >= raw_start) & (uav["observed_at"] <= raw_end)]
    i = infantry[(infantry["observed_at"] >= raw_start) & (infantry["observed_at"] <= raw_end)]
    u_days = u["observed_at"].dt.floor("D")
    i_days = i["observed_at"].dt.floor("D")
    start = max(u_days.min(), i_days.min())
    end = min(u_days.max(), i_days.max()) + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)
    return start, end


def daily_lag_correlation(uav: pd.DataFrame, infantry: pd.DataFrame, max_lag_days: int = 14) -> pd.DataFrame:
    start, end = active_overlap_window(uav, infantry)
    idx = pd.date_range(start.floor("D"), end.ceil("D"), freq="D")
    uav_daily = uav.set_index("observed_at").sort_index().loc[start:end].resample("D").size().reindex(idx, fill_value=0)
    inf_daily = (
        infantry.set_index("observed_at").sort_index().loc[start:end].resample("D").size().reindex(idx, fill_value=0)
    )
    rows = []
    for lag in range(-max_lag_days, max_lag_days + 1):
        shifted = uav_daily.shift(lag)
        pair = pd.concat([shifted.rename("uav"), inf_daily.rename("infantry")], axis=1).dropna()
        corr = pair["uav"].corr(pair["infantry"]) if pair["uav"].nunique() > 1 and pair["infantry"].nunique() > 1 else np.nan
        rows.append(
            {
                "lag_days": lag,
                "interpretation": "positive means UAV series is shifted later" if lag > 0 else "negative means UAV leads infantry",
                "pearson_correlation": corr,
                "paired_days": len(pair),
                "uav_count": int(pair["uav"].sum()),
                "infantry_count": int(pair["infantry"].sum()),
            }
        )
    return pd.DataFrame(rows)


def daily_counts(uav: pd.DataFrame, infantry: pd.DataFrame) -> pd.DataFrame:
    start, end = active_overlap_window(uav, infantry)
    idx = pd.date_range(start.floor("D"), end.ceil("D"), freq="D")
    uav_daily = uav.set_index("observed_at").sort_index().loc[start:end].resample("D").size().reindex(idx, fill_value=0)
    inf_daily = (
        infantry.set_index("observed_at").sort_index().loc[start:end].resample("D").size().reindex(idx, fill_value=0)
    )
    return pd.DataFrame({"date": idx.date.astype(str), "uav_activity": uav_daily.values, "infantry_activity": inf_daily.values})


def burst_days(counts: pd.DataFrame, column: str) -> pd.DataFrame:
    mean = counts[column].mean()
    std = counts[column].std(ddof=0)
    threshold = mean + 1.5 * std
    out = counts[counts[column] >= threshold].copy()
    out["threshold"] = threshold
    return out.sort_values(column, ascending=False)


def lead_lag_proximity(
    uav: pd.DataFrame,
    infantry: pd.DataFrame,
    radius_km: float = 10.0,
    max_abs_hours: int = 72,
) -> pd.DataFrame:
    start, end = active_overlap_window(uav, infantry)
    uav_window = uav[(uav["observed_at"] >= start - pd.Timedelta(hours=max_abs_hours)) & (uav["observed_at"] <= end)].copy()
    inf_window = infantry[(infantry["observed_at"] >= start) & (infantry["observed_at"] <= end)].copy()
    if uav_window.empty or inf_window.empty:
        return pd.DataFrame(columns=["lag_bin_hours", "matches", "infantry_events_with_match"])

    all_coords = pd.concat([uav_window[["lat", "lon"]], inf_window[["lat", "lon"]]], ignore_index=True)
    xy_all = to_local_km(all_coords["lat"], all_coords["lon"])
    uav_xy = xy_all[: len(uav_window)]
    inf_xy = xy_all[len(uav_window) :]
    tree = cKDTree(uav_xy)
    uav_times = uav_window["observed_at"].to_numpy(dtype="datetime64[ns]")

    bins = list(range(-max_abs_hours, max_abs_hours + 7, 6))
    hist = {f"{bins[i]} to {bins[i + 1]}": 0 for i in range(len(bins) - 1)}
    infantry_with_match = {key: set() for key in hist}

    for idx, (point, inf_time) in enumerate(zip(inf_xy, inf_window["observed_at"].to_numpy(dtype="datetime64[ns]"), strict=False)):
        neighbors = tree.query_ball_point(point, r=radius_km)
        if not neighbors:
            continue
        diffs = (inf_time - uav_times[neighbors]) / np.timedelta64(1, "h")
        for diff in diffs:
            if diff < -max_abs_hours or diff > max_abs_hours:
                continue
            for left, right in zip(bins[:-1], bins[1:], strict=False):
                if left <= diff < right:
                    key = f"{left} to {right}"
                    hist[key] += 1
                    infantry_with_match[key].add(idx)
                    break

    return pd.DataFrame(
        {
            "lag_bin_hours": list(hist.keys()),
            "matches": list(hist.values()),
            "infantry_events_with_match": [len(infantry_with_match[key]) for key in hist],
        }
    )


def spatial_hotspots(uav: pd.DataFrame, infantry: pd.DataFrame) -> pd.DataFrame:
    start, end = active_overlap_window(uav, infantry)
    u = uav[(uav["observed_at"] >= start) & (uav["observed_at"] <= end)]
    i = infantry[(infantry["observed_at"] >= start) & (infantry["observed_at"] <= end)]
    u_counts = u.groupby("grid_cell").size().rename("uav_activity")
    i_counts = i.groupby("grid_cell").size().rename("infantry_activity")
    joined = pd.concat([u_counts, i_counts], axis=1).fillna(0).reset_index()
    joined["combined_activity"] = joined["uav_activity"] + joined["infantry_activity"]
    joined["co_occurs_same_cell"] = (joined["uav_activity"] > 0) & (joined["infantry_activity"] > 0)
    return joined.sort_values("combined_activity", ascending=False)


def run(data_dir: str | Path | None = None, out_dir: str | Path | None = None, report_dir: str | Path | None = None) -> dict[str, Path]:
    root = data_root(data_dir)
    outputs = output_root(out_dir) / "challenge3"
    reports = reports_root(report_dir)
    outputs.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)

    uav, infantry = load_activities(root)
    counts = daily_counts(uav, infantry)
    lag_corr = daily_lag_correlation(uav, infantry)
    proximity = lead_lag_proximity(uav, infantry)
    hotspots = spatial_hotspots(uav, infantry)

    counts_path = outputs / "daily_activity_counts.csv"
    lag_path = outputs / "daily_lag_correlation.csv"
    proximity_path = outputs / "lead_lag_proximity.csv"
    hotspots_path = outputs / "spatial_hotspots.csv"
    report_path = reports / "challenge3_uav_ground_correlation.md"

    counts.to_csv(counts_path, index=False)
    lag_corr.to_csv(lag_path, index=False)
    proximity.to_csv(proximity_path, index=False)
    hotspots.to_csv(hotspots_path, index=False)
    report_path.write_text(_report(uav, infantry, counts, lag_corr, proximity, hotspots), encoding="utf-8")

    return {
        "daily_counts": counts_path,
        "lag_correlation": lag_path,
        "proximity": proximity_path,
        "hotspots": hotspots_path,
        "report": report_path,
    }


def _report(
    uav: pd.DataFrame,
    infantry: pd.DataFrame,
    counts: pd.DataFrame,
    lag_corr: pd.DataFrame,
    proximity: pd.DataFrame,
    hotspots: pd.DataFrame,
) -> str:
    start, end = overlap_window(uav, infantry)
    active_start, active_end = active_overlap_window(uav, infantry)
    best = lag_corr.dropna(subset=["pearson_correlation"]).sort_values("pearson_correlation", ascending=False).head(1)
    best_line = "No stable daily lag correlation could be computed."
    if not best.empty:
        row = best.iloc[0]
        best_line = (
            f"Best daily lag correlation: lag `{int(row.lag_days)}` days, "
            f"Pearson `{row.pearson_correlation:.3f}` across {int(row.paired_days)} paired days."
        )

    if int(proximity["matches"].sum()) == 0:
        prox_lines = "- No UAV/EW events were found within 10 km and +/-72 hours of infantry events."
    else:
        prox_top = proximity.sort_values("matches", ascending=False).head(5)
        prox_lines = "\n".join(
            f"- {row.lag_bin_hours} hours: {int(row.matches)} nearby UAV/infantry pairs, "
            f"{int(row.infantry_events_with_match)} infantry events with at least one match"
            for row in prox_top.itertuples()
        )

    co_occurs = hotspots[hotspots["co_occurs_same_cell"]]
    if co_occurs.empty:
        top_uav = hotspots[hotspots["uav_activity"] > 0].sort_values("uav_activity", ascending=False).head(5)
        top_inf = hotspots[hotspots["infantry_activity"] > 0].sort_values("infantry_activity", ascending=False).head(5)
        hotspot_lines = "No same-cell UAV/infantry overlap exists at 0.05 degree grid resolution.\n\nTop UAV/EW cells:\n"
        hotspot_lines += "\n".join(f"- {row.grid_cell}: {int(row.uav_activity)} UAV/EW events" for row in top_uav.itertuples())
        hotspot_lines += "\n\nTop infantry cells:\n"
        hotspot_lines += "\n".join(
            f"- {row.grid_cell}: {int(row.infantry_activity)} infantry events" for row in top_inf.itertuples()
        )
    else:
        hotspot_lines = "\n".join(
            f"- {row.grid_cell}: UAV {int(row.uav_activity)}, infantry {int(row.infantry_activity)}, "
            f"combined {int(row.combined_activity)}"
            for row in co_occurs.sort_values("combined_activity", ascending=False).head(10).itertuples()
        )
    uav_bursts = burst_days(counts, "uav_activity")
    inf_bursts = burst_days(counts, "infantry_activity")
    uav_burst_lines = "\n".join(f"- {row.date}: {int(row.uav_activity)} UAV events" for row in uav_bursts.itertuples()) or "- none"
    inf_burst_lines = (
        "\n".join(f"- {row.date}: {int(row.infantry_activity)} infantry events" for row in inf_bursts.itertuples())
        or "- none"
    )

    return f"""# Challenge 3 - UAV and Ground Activity Correlation

## Objective

Detect behavioral patterns and quantify how UAV/EW activity and infantry movement relate across time and space.

## Data Used

- UAV/EW activity records after coordinate/time cleaning: {len(uav):,}
- Infantry movement records after coordinate/time cleaning: {len(infantry):,}
- Raw temporal overlap: `{start}` to `{end}`
- Active overlap used for statistics: `{active_start}` to `{active_end}`

The two datasets do not share identifiers, so the analysis uses aggregate time-space evidence rather than direct row joins.

## Temporal Correlation

{best_line}

## Burst Days

UAV/EW bursts:

{uav_burst_lines}

Infantry bursts:

{inf_burst_lines}

## Spatial-Temporal Proximity

For each infantry event in the overlap period, the pipeline counts UAV/EW events within 10 km and +/-72 hours, grouped into 6-hour lead/lag bins. Positive lag means the UAV/EW event happened before the infantry event.

{prox_lines}

## Spatial Hotspots

{hotspot_lines}

## Interpretation

The reproducible evidence is strongest at the aggregate level. The available data supports quantified statements about overlap windows, bursts, lag bins, and hotspot cells. It does not support identity-level claims that a specific UAV event caused a specific infantry movement.
"""
