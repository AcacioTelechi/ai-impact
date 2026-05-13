"""I/O helpers for the SLR pipeline: deterministic CSV read/write and file hashing."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd


def sha256_file(path: Path, chunk_size: int = 1 << 16) -> str:
    """Return the SHA-256 hex digest of a file, reading in chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def read_corpus_csv(path: Path) -> pd.DataFrame:
    """Read a corpus CSV with UTF-8 encoding and stable dtypes."""
    if not Path(path).exists():
        raise FileNotFoundError(f"Corpus file not found: {path}")
    return pd.read_csv(path, encoding="utf-8")


def write_corpus_csv(df: pd.DataFrame, path: Path) -> None:
    """Write a corpus CSV with UTF-8 encoding and stable formatting."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")
