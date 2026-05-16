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
