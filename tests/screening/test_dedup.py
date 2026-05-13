from pathlib import Path

import pandas as pd
import pytest

from scripts.screening import dedup
from scripts.screening.consolidate import run as consolidate_run

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def bruto(tmp_path: Path) -> Path:
    out = tmp_path / "bruto.csv"
    consolidate_run(
        sources=[FIXTURES / "sample_wos.csv", FIXTURES / "sample_scopus.csv"],
        output=out,
    )
    return out


def test_dedup_by_doi_removes_exact_match(tmp_path: Path, bruto: Path) -> None:
    out = tmp_path / "dedup.csv"
    log = tmp_path / "dedup_log.csv"
    dedup.run(input=bruto, output=out, log=log, use_embeddings=False)
    df = pd.read_csv(out)
    # original: 9 rows; one DOI duplicate (10.1234/aer.2020.001 in both wos and scopus)
    # one title+author+year duplicate (no DOI in scopus row 4)
    # → 7 remaining after passes 1 and 2
    assert len(df) == 7


def test_dedup_log_records_decisions(tmp_path: Path, bruto: Path) -> None:
    out = tmp_path / "dedup.csv"
    log = tmp_path / "dedup_log.csv"
    dedup.run(input=bruto, output=out, log=log, use_embeddings=False)
    log_df = pd.read_csv(log)
    assert {"removed_doi", "kept_doi", "rule", "kept_source"} <= set(log_df.columns)
    assert (log_df["rule"] == "doi").sum() == 1
    assert (log_df["rule"] == "dedup_key").sum() == 1


def test_dedup_preserves_first_occurrence(tmp_path: Path, bruto: Path) -> None:
    out = tmp_path / "dedup.csv"
    dedup.run(input=bruto, output=out, log=tmp_path / "log.csv", use_embeddings=False)
    df = pd.read_csv(out)
    # First occurrence of 10.1234/aer.2020.001 is from wos (earlier in fixtures)
    aer_rows = df[df["doi"] == "10.1234/aer.2020.001"]
    assert len(aer_rows) == 1
    assert aer_rows.iloc[0]["source"] == "wos"
