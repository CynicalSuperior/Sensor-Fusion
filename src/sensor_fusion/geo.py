from __future__ import annotations

import math
from typing import Iterable

import numpy as np
import pandas as pd

EARTH_RADIUS_KM = 6371.0088
DEFAULT_HEX_ORIGIN_LAT = 51.5
DEFAULT_HEX_ORIGIN_LON = 38.0
DEFAULT_HEX_SIZE_KM = 5.0


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


def _project_to_local_km(
    lat: float,
    lon: float,
    origin_lat: float = DEFAULT_HEX_ORIGIN_LAT,
    origin_lon: float = DEFAULT_HEX_ORIGIN_LON,
) -> tuple[float, float]:
    x = (float(lon) - origin_lon) * math.cos(math.radians(origin_lat)) * 111.320
    y = (float(lat) - origin_lat) * 110.574
    return x, y


def _unproject_from_local_km(
    x: float,
    y: float,
    origin_lat: float = DEFAULT_HEX_ORIGIN_LAT,
    origin_lon: float = DEFAULT_HEX_ORIGIN_LON,
) -> tuple[float, float]:
    lat = origin_lat + y / 110.574
    lon = origin_lon + x / (math.cos(math.radians(origin_lat)) * 111.320)
    return lat, lon


def _cube_round(q_float: float, r_float: float) -> tuple[int, int]:
    x = q_float
    z = r_float
    y = -x - z

    rx = round(x)
    ry = round(y)
    rz = round(z)

    x_diff = abs(rx - x)
    y_diff = abs(ry - y)
    z_diff = abs(rz - z)

    if x_diff > y_diff and x_diff > z_diff:
        rx = -ry - rz
    elif y_diff > z_diff:
        ry = -rx - rz
    else:
        rz = -rx - ry
    return int(rx), int(rz)


def hex_coords(
    lat: float,
    lon: float,
    hex_size_km: float = DEFAULT_HEX_SIZE_KM,
    origin_lat: float = DEFAULT_HEX_ORIGIN_LAT,
    origin_lon: float = DEFAULT_HEX_ORIGIN_LON,
) -> tuple[str, int, int]:
    if pd.isna(lat) or pd.isna(lon):
        return "", 0, 0
    x, y = _project_to_local_km(lat, lon, origin_lat=origin_lat, origin_lon=origin_lon)
    q_float = (math.sqrt(3) / 3 * x - 1 / 3 * y) / hex_size_km
    r_float = (2 / 3 * y) / hex_size_km
    q, r = _cube_round(q_float, r_float)
    return f"h{hex_size_km:g}_{q}_{r}", q, r


def hex_center_latlon(
    q: int,
    r: int,
    hex_size_km: float = DEFAULT_HEX_SIZE_KM,
    origin_lat: float = DEFAULT_HEX_ORIGIN_LAT,
    origin_lon: float = DEFAULT_HEX_ORIGIN_LON,
) -> tuple[float, float]:
    x = hex_size_km * math.sqrt(3) * (q + r / 2)
    y = hex_size_km * 1.5 * r
    return _unproject_from_local_km(x, y, origin_lat=origin_lat, origin_lon=origin_lon)


def add_hex_cell(
    df: pd.DataFrame,
    lat_col: str = "lat",
    lon_col: str = "lon",
    hex_size_km: float = DEFAULT_HEX_SIZE_KM,
) -> pd.DataFrame:
    out = df.copy()
    cells = [hex_coords(lat, lon, hex_size_km=hex_size_km) for lat, lon in zip(out[lat_col], out[lon_col], strict=False)]
    out["hex_cell"] = [cell for cell, _, _ in cells]
    out["hex_q"] = [q for _, q, _ in cells]
    out["hex_r"] = [r for _, _, r in cells]
    centers = [hex_center_latlon(q, r, hex_size_km=hex_size_km) if cell else (math.nan, math.nan) for cell, q, r in cells]
    out["hex_center_lat"] = [lat for lat, _ in centers]
    out["hex_center_lon"] = [lon for _, lon in centers]
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
