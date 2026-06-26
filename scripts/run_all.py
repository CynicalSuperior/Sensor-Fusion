#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sensor_fusion import challenge1, challenge2, challenge3  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run all battlefield data challenge pipelines.")
    parser.add_argument("--data-root", default="/home/CynicalSuperior/Downloads", help="Folder containing challenge data.")
    parser.add_argument("--outputs", default=str(REPO_ROOT / "outputs"), help="Output artifact folder.")
    parser.add_argument("--reports", default=str(REPO_ROOT / "reports"), help="Markdown report folder.")
    args = parser.parse_args()

    artifacts = {
        "challenge1": challenge1.run(args.data_root, args.outputs, args.reports),
        "challenge2": challenge2.run(args.data_root, args.outputs, args.reports),
        "challenge3": challenge3.run(args.data_root, args.outputs, args.reports),
    }
    for challenge, paths in artifacts.items():
        print(f"\n{challenge}")
        for name, path in paths.items():
            print(f"  {name}: {path}")


if __name__ == "__main__":
    main()

