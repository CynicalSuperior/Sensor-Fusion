from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .config import data_root, output_root, reports_root
from .geo import add_grid_cell, coordinate_extent


CHALLENGE1_FILES = {
    "ew_observation": "challenge_1_data_fusion/ew_data.csv",
    "ew_report": "challenge_1_data_fusion/ew_report_data.csv",
    "communication_asset": "challenge_1_data_fusion/communication_asset_data.csv",
    "uav_observation": "challenge_1_data_fusion/uav_data.csv",
    "satellite": "challenge_1_data_fusion/satelite_data.csv",
    "sigint": "challenge_1_data_fusion/sigint_source_data.csv",
    "artillery": "challenge_1_data_fusion/artillery_data.csv",
}


TRUST_SCORE = {
    "A1": 0.98,
    "A2": 0.90,
    "A3": 0.82,
    "C2": 0.58,
    "C3": 0.50,
    "C4": 0.42,
    "F2": 0.25,
    "F3": 0.20,
    "CompletelyReliable": 0.95,
}


def parse_datetime(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", format="mixed", utc=True).dt.tz_convert(None)


def confidence_from_trust(series: pd.Series, default: float) -> pd.Series:
    return series.map(TRUST_SCORE).fillna(default).astype(float)


def normalize_operational_file(path: Path, source: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    observed = parse_datetime(df.get("date_observe", pd.Series(index=df.index, dtype=object)))
    created = parse_datetime(df.get("date_create", pd.Series(index=df.index, dtype=object)))
    observed = observed.fillna(created)

    lat = df.get("start_point_latitude")
    lon = df.get("start_point_longitude")
    end_lat = df.get("end_point_latitude")
    end_lon = df.get("end_point_longitude")
    confidence = confidence_from_trust(df.get("trust", pd.Series(index=df.index, dtype=object)), default=0.45)

    out = pd.DataFrame(
        {
            "source": source,
            "source_id": df["id"].astype(str),
            "object_id": df.get("object_id", "").astype(str),
            "observed_at": observed,
            "created_at": created,
            "lat": lat,
            "lon": lon,
            "end_lat": end_lat,
            "end_lon": end_lon,
            "geometry_type": df.get("geometry_type", ""),
            "object_type": df.get("object_type", ""),
            "app6_type": df.get("app6_type_ua", ""),
            "identity": df.get("standard_identity", ""),
            "status": df.get("status", ""),
            "quantity": pd.to_numeric(df.get("quantity", 1), errors="coerce").fillna(1),
            "trust": df.get("trust", ""),
            "source_type": df.get("source_type_ua", ""),
            "mission": "",
            "uav_type": "",
            "result": "",
            "route_identification": df.get("route_identification", ""),
            "route_type": df.get("route_type", ""),
            "signal_type": df.get("ew_type_normalized", ""),
            "confidence": confidence,
            "raw_file": path.name,
        }
    )
    return out


def normalize_ew_report(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    observed = parse_datetime(df["timestamp"])
    lat = df["start_point_latitude"].fillna(df["end_point_latitude"])
    lon = df["start_point_longitude"].fillna(df["end_point_longitude"])
    coord_role = np.where(df["start_point_latitude"].notna(), "start", "end")

    out = pd.DataFrame(
        {
            "source": "ew_report",
            "source_id": df["id"].astype(str),
            "object_id": "",
            "observed_at": observed,
            "created_at": pd.NaT,
            "lat": lat,
            "lon": lon,
            "end_lat": df["end_point_latitude"],
            "end_lon": df["end_point_longitude"],
            "geometry_type": "PointType",
            "object_type": "uav",
            "app6_type": df["uav_type"],
            "identity": "hostile_or_unknown",
            "status": df["result_text_category"],
            "quantity": pd.to_numeric(df["quantity"], errors="coerce").fillna(1),
            "trust": "",
            "source_type": "ew_report",
            "mission": df["mission"],
            "uav_type": df["uav_type"],
            "result": df["result_text_category"],
            "route_identification": "",
            "route_type": "",
            "signal_type": df["frequency_group"],
            "confidence": 0.55,
            "raw_file": path.name,
            "coordinate_role": coord_role,
        }
    )
    return out


def normalize_all(data_dir: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for source, rel in CHALLENGE1_FILES.items():
        path = data_dir / rel
        if source == "ew_report":
            frame = normalize_ew_report(path)
        else:
            frame = normalize_operational_file(path, source)
        frames.append(frame)

    events = pd.concat(frames, ignore_index=True, sort=False)
    events["coordinate_role"] = events.get("coordinate_role", "start").fillna("start")
    events = events[events["observed_at"].notna()].copy()
    events = add_grid_cell(events, "lat", "lon", resolution_deg=0.02)
    events["observed_date"] = events["observed_at"].dt.date.astype(str)
    events["time_bucket_6h"] = events["observed_at"].dt.floor("6h")
    events["object_family"] = (
        events["object_type"].replace("", np.nan).fillna(events["mission"]).replace("", np.nan).fillna("unknown")
    )
    return events


def build_clusters(events: pd.DataFrame) -> pd.DataFrame:
    group_cols = ["grid_cell", "time_bucket_6h", "object_family"]
    valid = events[(events["grid_cell"] != "") & events["time_bucket_6h"].notna()].copy()
    valid["source_count_weight"] = 1
    clusters = (
        valid.groupby(group_cols)
        .agg(
            event_count=("source_id", "count"),
            source_count=("source", "nunique"),
            sources=("source", lambda s: ",".join(sorted(set(map(str, s))))),
            first_observed=("observed_at", "min"),
            last_observed=("observed_at", "max"),
            centroid_lat=("lat", "mean"),
            centroid_lon=("lon", "mean"),
            total_quantity=("quantity", "sum"),
            mean_confidence=("confidence", "mean"),
            max_confidence=("confidence", "max"),
        )
        .reset_index()
        .sort_values(["source_count", "event_count", "first_observed"], ascending=[False, False, True])
    )
    clusters.insert(0, "cluster_id", [f"C{i:06d}" for i in range(1, len(clusters) + 1)])
    clusters["fusion_score"] = (
        1 - np.exp(-clusters["source_count"] * 0.65 - clusters["event_count"].clip(upper=20) * 0.08)
    ).round(3)
    return clusters


def sample_queries(events: pd.DataFrame) -> pd.DataFrame:
    dense_cell = events["grid_cell"].value_counts().index[0]
    middle_date = events["observed_at"].dt.date.value_counts().index[0]
    query = events[(events["grid_cell"] == dense_cell) & (events["observed_at"].dt.date == middle_date)]
    return query.sort_values("observed_at").head(200)


def run(data_dir: str | Path | None = None, out_dir: str | Path | None = None, report_dir: str | Path | None = None) -> dict[str, Path]:
    root = data_root(data_dir)
    outputs = output_root(out_dir) / "challenge1"
    reports = reports_root(report_dir)
    outputs.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)

    events = normalize_all(root)
    clusters = build_clusters(events)
    source_summary = source_quality_summary(events)
    query = sample_queries(events)

    events_path = outputs / "normalized_events.csv"
    clusters_path = outputs / "fusion_clusters.csv"
    summary_path = outputs / "source_summary.csv"
    query_path = outputs / "sample_geo_temporal_query.csv"
    report_path = reports / "challenge1_fusion.md"

    events.to_csv(events_path, index=False)
    clusters.to_csv(clusters_path, index=False)
    source_summary.to_csv(summary_path, index=False)
    query.to_csv(query_path, index=False)
    report_path.write_text(_report(events, clusters, source_summary, query_path), encoding="utf-8")

    return {
        "events": events_path,
        "clusters": clusters_path,
        "summary": summary_path,
        "query": query_path,
        "report": report_path,
    }


def source_quality_summary(events: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for source, group in events.groupby("source"):
        extent = coordinate_extent(group)
        rows.append(
            {
                "source": source,
                "rows": len(group),
                "unique_objects": group["object_id"].replace("", np.nan).nunique(dropna=True),
                "observed_min": group["observed_at"].min(),
                "observed_max": group["observed_at"].max(),
                "missing_coordinates": int(group[["lat", "lon"]].isna().any(axis=1).sum()),
                "mean_confidence": round(float(group["confidence"].mean()), 3),
                **extent,
            }
        )
    return pd.DataFrame(rows).sort_values("rows", ascending=False)


def _report(events: pd.DataFrame, clusters: pd.DataFrame, summary: pd.DataFrame, query_path: Path) -> str:
    source_lines = "\n".join(
        f"- {row.source}: {int(row.rows):,} normalized events, "
        f"{int(row.missing_coordinates):,} missing coordinates, "
        f"{row.observed_min} to {row.observed_max}"
        for row in summary.itertuples()
    )
    top_clusters = clusters.head(10)
    cluster_lines = "\n".join(
        f"- {row.cluster_id}: {row.object_family} in {row.grid_cell}, "
        f"{int(row.event_count)} events from {int(row.source_count)} sources, score {row.fusion_score}"
        for row in top_clusters.itertuples()
    )
    return f"""# Challenge 1 - Geo-Temporal Intelligence Fusion

## Objective

Create one searchable battlefield event model from UAV, EW, SIGINT, satellite, communication asset, and artillery data.

## Normalized Event Contract

Each source is mapped into:

`source, source_id, object_id, observed_at, created_at, lat, lon, end_lat, end_lon, geometry_type, object_type, app6_type, identity, status, quantity, trust, source_type, mission, uav_type, result, route_identification, route_type, signal_type, confidence, grid_cell, observed_date, time_bucket_6h`

## Data Loaded

- Normalized events: {len(events):,}
- Fusion clusters: {len(clusters):,}
- Observation range: `{events["observed_at"].min()}` to `{events["observed_at"].max()}`

## Source Summary

{source_lines}

## Fusion Method

Direct identifiers are sparse across sources, so `object_id` is preserved but not treated as the universal join key. The fusion layer uses a conservative geo-temporal bucket:

- spatial bucket: 0.02 degree grid cell
- time bucket: 6 hour window
- semantic bucket: normalized object family

This produces reproducible candidate clusters for analyst review. The cluster score increases when independent sources and repeated observations agree in the same cell/time/object-family bucket.

## Highest-Value Fusion Clusters

{cluster_lines}

## Query Layer

The sample query output demonstrates the intended analyst operation: "what happened in this grid cell on this date, ordered by time?"

- Sample query CSV: `{query_path}`

## Limitations

The method avoids overclaiming identity-level fusion where sources do not share identifiers. It is a candidate fusion model, designed to be explainable and auditable before operational use.
"""

