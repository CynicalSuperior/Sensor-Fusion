from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import argparse
import json
from pathlib import Path
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pandas as pd

from . import challenge1
from .config import REPO_ROOT, data_root, output_root


def _json_default(value: object) -> str | float | int | None:
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _first(params: dict[str, list[str]], key: str, default: str = "") -> str:
    values = params.get(key)
    return values[0] if values else default


def _records(df: pd.DataFrame) -> list[dict[str, object]]:
    return json.loads(df.to_json(orient="records", date_format="iso"))


@dataclass
class FusionDataStore:
    repo_root: Path
    data_dir: Path
    outputs_dir: Path

    def __post_init__(self) -> None:
        self.challenge_output = self.outputs_dir / "challenge1"
        self.timeline_path = self.challenge_output / "timeline_events.csv"
        self.clusters_path = self.challenge_output / "fusion_clusters.csv"
        if not self.timeline_path.exists() or not self.clusters_path.exists():
            challenge1.run(self.data_dir, self.outputs_dir, self.repo_root / "reports")
        self.reload()

    def reload(self) -> None:
        self.events = pd.read_csv(self.timeline_path, parse_dates=["observed_at"], low_memory=False)
        self.clusters = pd.read_csv(self.clusters_path, parse_dates=["first_observed", "last_observed"], low_memory=False)
        for col in ["source", "object_family", "status", "app6_type", "signal_type", "mission", "uav_type"]:
            if col in self.events.columns:
                self.events[col] = self.events[col].fillna("").astype(str)

    def meta(self) -> dict[str, object]:
        return {
            "total_events": int(len(self.events)),
            "total_hexes": int(self.events["hex_cell"].nunique()),
            "total_clusters": int(len(self.clusters)),
            "sources": sorted(self.events["source"].dropna().unique().tolist()),
            "families": sorted(self.events["object_family"].dropna().unique().tolist()),
            "observed_min": self.events["observed_at"].min().isoformat(),
            "observed_max": self.events["observed_at"].max().isoformat(),
            "loaded_from": str(self.timeline_path),
        }

    def _filtered_events(self, params: dict[str, list[str]]) -> pd.DataFrame:
        df = self.events

        source = _first(params, "source")
        if source and source != "all":
            df = df[df["source"] == source]

        family = _first(params, "family")
        if family and family != "all":
            df = df[df["object_family"] == family]

        date_from = _first(params, "date_from")
        if date_from:
            start = pd.to_datetime(date_from, errors="coerce")
            if pd.notna(start):
                df = df[df["observed_at"] >= start]

        date_to = _first(params, "date_to")
        if date_to:
            end = pd.to_datetime(date_to, errors="coerce")
            if pd.notna(end):
                df = df[df["observed_at"] < end + pd.Timedelta(days=1)]

        min_conf = _first(params, "min_conf")
        if min_conf:
            try:
                df = df[df["confidence"] >= float(min_conf)]
            except ValueError:
                pass

        search = _first(params, "q").strip().lower()
        if search:
            fields = ["source_id", "object_id", "app6_type", "status", "signal_type", "mission", "uav_type"]
            mask = pd.Series(False, index=df.index)
            for field in fields:
                mask |= df[field].fillna("").astype(str).str.lower().str.contains(search, regex=False)
            df = df[mask]

        return df

    def hexes(self, params: dict[str, list[str]]) -> dict[str, object]:
        df = self._filtered_events(params)
        if df.empty:
            return {"hexes": [], "count": 0}

        grouped = (
            df.groupby(["hex_cell", "hex_q", "hex_r"])
            .agg(
                event_count=("source_id", "count"),
                source_count=("source", "nunique"),
                sources=("source", lambda s: sorted(set(map(str, s)))),
                first_observed=("observed_at", "min"),
                last_observed=("observed_at", "max"),
                center_lat=("hex_center_lat", "first"),
                center_lon=("hex_center_lon", "first"),
                mean_confidence=("confidence", "mean"),
                dominant_family=("object_family", lambda s: s.value_counts().index[0] if len(s) else ""),
            )
            .reset_index()
            .sort_values(["event_count", "source_count"], ascending=[False, False])
        )
        grouped["mean_confidence"] = grouped["mean_confidence"].round(3)
        return {
            "count": int(len(grouped)),
            "event_count": int(len(df)),
            "hexes": _records(grouped),
        }

    def timeline(self, params: dict[str, list[str]]) -> dict[str, object]:
        df = self._filtered_events(params)
        hex_cell = _first(params, "hex_cell")
        if hex_cell:
            df = df[df["hex_cell"] == hex_cell]

        try:
            limit = min(max(int(_first(params, "limit", "300")), 1), 1000)
        except ValueError:
            limit = 300

        df = df.sort_values("observed_at").head(limit)
        fields = [
            "observed_at",
            "hex_cell",
            "source",
            "source_id",
            "object_family",
            "object_type",
            "app6_type",
            "identity",
            "status",
            "quantity",
            "confidence",
            "lat",
            "lon",
            "mission",
            "uav_type",
            "result",
            "signal_type",
            "route_type",
        ]
        return {
            "count": int(len(df)),
            "limit": limit,
            "hex_cell": hex_cell,
            "events": _records(df[fields]),
        }


class FusionRequestHandler(SimpleHTTPRequestHandler):
    store: FusionDataStore

    def __init__(self, *args, directory: str | None = None, **kwargs) -> None:
        super().__init__(*args, directory=directory, **kwargs)

    def do_GET(self) -> None:  # noqa: N802 - stdlib method name
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self._handle_api(parsed.path, parse_qs(parsed.query))
            return
        if parsed.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def _handle_api(self, path: str, params: dict[str, list[str]]) -> None:
        try:
            if path == "/api/meta":
                payload = self.store.meta()
            elif path == "/api/hexes":
                payload = self.store.hexes(params)
            elif path == "/api/timeline":
                payload = self.store.timeline(params)
            elif path == "/api/reload":
                self.store.reload()
                payload = {"ok": True, **self.store.meta()}
            else:
                self._send_json({"error": "unknown endpoint"}, status=404)
                return
            self._send_json(payload)
        except Exception as exc:  # pragma: no cover - surfaced in browser during prototype work
            self._send_json({"error": str(exc)}, status=500)

    def _send_json(self, payload: dict[str, object], status: int = 200) -> None:
        body = json.dumps(payload, default=_json_default).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass


def serve(host: str, port: int, data_dir: str | Path | None = None, outputs_dir: str | Path | None = None) -> None:
    web_dir = REPO_ROOT / "web"
    store = FusionDataStore(REPO_ROOT, data_root(data_dir), output_root(outputs_dir))

    class Handler(FusionRequestHandler):
        pass

    Handler.store = store
    server = ThreadingHTTPServer((host, port), lambda *args, **kwargs: Handler(*args, directory=str(web_dir), **kwargs))
    print(f"Serving Sensor Fusion demo at http://{host}:{port}")
    print(f"Loaded {len(store.events):,} timeline events across {store.events['hex_cell'].nunique():,} hex cells")
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the sensor fusion map/timeline demo.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-root", default="/home/CynicalSuperior/Downloads")
    parser.add_argument("--outputs", default=str(REPO_ROOT / "outputs"))
    args = parser.parse_args()
    serve(args.host, args.port, args.data_root, args.outputs)


if __name__ == "__main__":
    main()
