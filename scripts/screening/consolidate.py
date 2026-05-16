"""Pipeline step 01: consolidate raw search exports into a single corpus CSV.

Reads each input CSV (one per base/search), validates required columns, and
concatenates them into `data/processed/01_corpus_bruto.csv`.

CLI:
    python -m scripts.screening.consolidate \
        --sources data/raw/searches/wos_*.csv data/raw/searches/scopus_*.csv \
        --output data/processed/01_corpus_bruto.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = ["source", "doi", "title", "authors", "year", "abstract", "venue", "language"]


def run(sources: list[Path], output: Path) -> None:
    """Concatenate input CSVs into a single corpus, validating required columns."""
    frames: list[pd.DataFrame] = []
    for src in sources:
        df = pd.read_csv(src, encoding="utf-8")
        missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
        if missing:
            raise ValueError(f"{src} missing required columns: {missing}")
        frames.append(df[REQUIRED_COLUMNS])
    combined = pd.concat(frames, ignore_index=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(output, index=False, encoding="utf-8")
    print(f"Consolidated {sum(len(f) for f in frames)} rows into {output}")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Consolidate raw search exports.")
    p.add_argument("--sources", nargs="+", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    run(args.sources, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
