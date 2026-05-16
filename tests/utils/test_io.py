import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.utils.io import sha256_file, read_corpus_csv, write_corpus_csv


def test_sha256_file_is_deterministic(tmp_path: Path) -> None:
    f = tmp_path / "a.txt"
    f.write_text("hello world\n")
    h1 = sha256_file(f)
    h2 = sha256_file(f)
    assert h1 == h2
    assert len(h1) == 64


def test_sha256_file_changes_with_content(tmp_path: Path) -> None:
    f = tmp_path / "a.txt"
    f.write_text("hello")
    h1 = sha256_file(f)
    f.write_text("world")
    h2 = sha256_file(f)
    assert h1 != h2


def test_write_and_read_corpus_csv_roundtrip(tmp_path: Path) -> None:
    df = pd.DataFrame(
        [
            {"doi": "10.1/a", "title": "x, with comma", "year": 2020},
            {"doi": "10.2/b", "title": "y", "year": 2021},
        ]
    )
    path = tmp_path / "out.csv"
    write_corpus_csv(df, path)
    out = read_corpus_csv(path)
    pd.testing.assert_frame_equal(out, df)


def test_read_corpus_csv_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_corpus_csv(tmp_path / "nope.csv")
