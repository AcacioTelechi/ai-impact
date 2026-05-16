import itertools
from pathlib import Path

import pandas as pd
import pytest

from scripts.screening import screening_ta
from scripts.screening.screening_ta import merge_conservative

LABELS = ["incluir", "excluir", "duvida"]


@pytest.mark.parametrize("s,h", itertools.product(LABELS, LABELS))
def test_merge_only_excludes_when_both_exclude(s, h):
    d = merge_conservative(
        {"decisao": s, "justificativa": "a", "confianca": 0.8, "criterio": "E1" if s == "excluir" else None},
        {"decisao": h, "justificativa": "b", "confianca": 0.6, "criterio": "E2" if h == "excluir" else None},
    )
    if s == "excluir" and h == "excluir":
        assert d["decisao_final"] == "excluir"
    else:
        assert d["decisao_final"] == "incluir"
    assert d["concordancia"] == ("concordam" if s == h else "divergem")
    if not (s == "excluir" and h == "excluir"):
        assert d["criterio_exclusao"] == ""


def test_merge_picks_criterio_from_higher_confidence_when_both_exclude():
    d = merge_conservative(
        {"decisao": "excluir", "justificativa": "x", "confianca": 0.6, "criterio": "E1"},
        {"decisao": "excluir", "justificativa": "y", "confianca": 0.9, "criterio": "E3"},
    )
    assert d["decisao_final"] == "excluir"
    assert d["criterio_exclusao"] == "E3"  # maior confiança


def test_merge_no_criterio_when_included():
    d = merge_conservative(
        {"decisao": "incluir", "justificativa": "x", "confianca": 0.9, "criterio": None},
        {"decisao": "excluir", "justificativa": "y", "confianca": 0.5, "criterio": "E1"},
    )
    assert d["decisao_final"] == "incluir"
    assert d["criterio_exclusao"] == ""


NEW_COLS = {
    "decisao_sonnet", "justificativa_sonnet", "confianca_sonnet",
    "decisao_haiku", "justificativa_haiku", "confianca_haiku",
    "decisao_final", "concordancia", "criterio_exclusao",
}


def _corpus(tmp_path: Path) -> Path:
    p = tmp_path / "02_dedup.csv"
    pd.DataFrame([
        {"source": "wos", "doi": "10.1/a", "title": "AI and employment in the US",
         "authors": "Smith, J.", "year": 2020, "abstract": "AI exposure on labor",
         "venue": "AER", "language": "en"},
        {"source": "wos", "doi": "10.1/b", "title": "Cooking recipes book",
         "authors": "Brown, P.", "year": 2019, "abstract": "food and recipes",
         "venue": "Food", "language": "en"},
    ]).to_csv(p, index=False)
    return p


def test_run_mock_produces_dual_schema(tmp_path: Path):
    src = _corpus(tmp_path)
    out = tmp_path / "03_screening_ta.csv"
    inc = tmp_path / "03_incluidos_ta.csv"
    screening_ta.run(input=src, output=out, incluidos=inc, mock=True)
    df = pd.read_csv(out)
    assert NEW_COLS <= set(df.columns)
    assert len(df) == 2
    assert df["decisao_final"].isin(["incluir", "excluir"]).all()
    inc_df = pd.read_csv(inc)
    assert (inc_df["decisao_final"] == "incluir").all()
    assert len(inc_df) == (df["decisao_final"] == "incluir").sum()


def test_run_preserves_original_columns(tmp_path: Path):
    src = _corpus(tmp_path)
    out = tmp_path / "03.csv"
    screening_ta.run(input=src, output=out, mock=True)
    df = pd.read_csv(out)
    assert {"source", "doi", "title", "authors", "year", "abstract",
            "venue", "language"} <= set(df.columns)


def test_mock_judge_returns_full_schema():
    """_mock_judge must emit the same keys as the real parse_response path."""
    from scripts.screening.screening_ta import _mock_judge
    for title, abstract in [("AI and jobs", "labor"), ("AI only", "x"), ("nothing", "y")]:
        d = _mock_judge(pd.Series({"title": title, "abstract": abstract}))
        assert set(d) == {"decisao", "justificativa", "confianca", "criterio"}
