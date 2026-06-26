from __future__ import annotations

import math
from typing import Iterable

import numpy as np
import pandas as pd

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def grid_cell_id(lat: float, lon: float, resolution_deg: float = 0.02) -> str:
    if pd.isna(lat) or pd.isna(lon):
        return ""
    lat_i = math.floor(float(lat) / resolution_deg)
    lon_i = math.floor(float(lon) / resolution_deg)
    return f"g{resolution_deg:.3f}_{lat_i}_{lon_i}"


def add_grid_cell(
    df: pd.DataFrame,
    lat_col: str = "lat",
    lon_col: str = "lon",
    resolution_deg: float = 0.02,
) -> pd.DataFrame:
    out = df.copy()
    out["grid_cell"] = [
        grid_cell_id(lat, lon, resolution_deg=resolution_deg)
        for lat, lon in zip(out[lat_col], out[lon_col], strict=False)
    ]
    return out


def to_local_km(latitudes: Iterable[float], longitudes: Iterable[float]) -> np.ndarray:
    lat = np.asarray(list(latitudes), dtype=float)
    lon = np.asarray(list(longitudes), dtype=float)
    lat0 = np.nanmean(lat)
    lon0 = np.nanmean(lon)
    x = (lon - lon0) * math.cos(math.radians(lat0)) * 111.320
    y = (lat - lat0) * 110.574
    return np.column_stack([x, y])


def coordinate_extent(df: pd.DataFrame, lat_col: str = "lat", lon_col: str = "lon") -> dict[str, float]:
    valid = df[[lat_col, lon_col]].dropna()
    if valid.empty:
        return {}
    return {
        "lat_min": float(valid[lat_col].min()),
        "lat_max": float(valid[lat_col].max()),
        "lon_min": float(valid[lon_col].min()),
        "lon_max": float(valid[lon_col].max()),
    }

