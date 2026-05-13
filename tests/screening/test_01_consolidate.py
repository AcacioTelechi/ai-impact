from pathlib import Path

import pandas as pd
import pytest

from scripts.screening import consolidate


FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_consolidate_merges_all_csvs(tmp_path: Path) -> None:
    out = tmp_path / "corpus_bruto.csv"
    consolidate.run(
        sources=[FIXTURES / "sample_wos.csv", FIXTURES / "sample_scopus.csv"],
        output=out,
    )
    df = pd.read_csv(out)
    assert len(df) == 9
    assert set(df["source"].unique()) == {"wos", "scopus"}


def test_consolidate_validates_required_columns(tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("title,year\nfoo,2020\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing required columns"):
        consolidate.run(sources=[bad], output=tmp_path / "out.csv")


def test_consolidate_preserves_utf8(tmp_path: Path) -> None:
    out = tmp_path / "corpus_bruto.csv"
    consolidate.run(
        sources=[FIXTURES / "sample_scopus.csv"],
        output=out,
    )
    text = out.read_text(encoding="utf-8")
    assert "Inteligencia artificial" in text
    assert "français" in text
