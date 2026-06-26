from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_ROOT = Path("/home/CynicalSuperior/Downloads")


def data_root(path: str | Path | None = None) -> Path:
    return Path(path).expanduser().resolve() if path else DEFAULT_DATA_ROOT


def output_root(path: str | Path | None = None) -> Path:
    return Path(path).expanduser().resolve() if path else REPO_ROOT / "outputs"


def reports_root(path: str | Path | None = None) -> Path:
    return Path(path).expanduser().resolve() if path else REPO_ROOT / "reports"

