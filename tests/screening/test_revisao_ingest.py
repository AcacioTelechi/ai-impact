# tests/screening/test_revisao_ingest.py
import numpy as np
import pandas as pd
import pytest

from scripts.screening.revisao_ingest import normalize_decisao


@pytest.mark.parametrize("raw,exp", [
    ("i", "incluir"), ("I", "incluir"), ("incluir", "incluir"),
    ("INCLUIR", "incluir"), (" e ", "excluir"), ("excluir", "excluir"),
    ("", "pendente"), ("   ", "pendente"), (None, "pendente"),
    (float("nan"), "pendente"), (np.nan, "pendente"), (pd.NA, "pendente"),
])
def test_normalize_valid_and_empty(raw, exp):
    assert normalize_decisao(raw) == exp


@pytest.mark.parametrize("bad", ["x", "talvez", "1", "sim", "yes", "s", "n", "nao", "não"])
def test_normalize_invalid_raises(bad):
    with pytest.raises(ValueError):
        normalize_decisao(bad)


from scripts.screening.revisao_ingest import apply_decisions
from scripts.screening.llm.batch_client import cache_key, custom_id


def _row(s, h, final, doi):
    return {
        "source": "wos", "doi": doi, "title": "T", "authors": "A",
        "year": 2020, "abstract": "x", "venue": "V", "language": "en",
        "decisao_sonnet": s, "justificativa_sonnet": "js", "confianca_sonnet": 0.5,
        "decisao_haiku": h, "justificativa_haiku": "jh", "confianca_haiku": 0.5,
        "decisao_final": final, "concordancia": "x", "criterio_exclusao": "",
    }


def _rid(d):
    return custom_id(cache_key(pd.Series(d)))


def test_apply_decisions_four_categories():
    screening = pd.DataFrame([
        _row("incluir", "incluir", "incluir", "10.1/bi"),   # ambos-incluir
        _row("excluir", "excluir", "excluir", "10.1/be"),    # ambos-excluir
        _row("incluir", "duvida", "incluir", "10.1/s1"),     # soft → humano i
        _row("duvida", "excluir", "incluir", "10.1/s2"),     # soft → humano e
        _row("duvida", "duvida", "incluir", "10.1/s3"),      # soft → pendente
    ])
    sheet = pd.DataFrame([
        {"review_id": _rid(screening.iloc[2].to_dict()), "decisao_humana": "i", "nota_humana": ""},
        {"review_id": _rid(screening.iloc[3].to_dict()), "decisao_humana": "e", "nota_humana": "fora"},
        {"review_id": _rid(screening.iloc[4].to_dict()), "decisao_humana": "", "nota_humana": ""},
    ])
    out = apply_decisions(screening, sheet)
    by = out.set_index("doi")
    assert by.loc["10.1/bi", "decisao_final_revisada"] == "incluir"
    assert by.loc["10.1/bi", "origem_decisao"] == "llm_concordante"
    assert by.loc["10.1/be", "decisao_final_revisada"] == "excluir"
    assert by.loc["10.1/be", "origem_decisao"] == "llm_concordante"
    assert by.loc["10.1/s1", "decisao_final_revisada"] == "incluir"
    assert by.loc["10.1/s1", "origem_decisao"] == "humano"
    assert by.loc["10.1/s2", "decisao_final_revisada"] == "excluir"
    assert by.loc["10.1/s2", "origem_decisao"] == "humano"
    assert by.loc["10.1/s2", "nota_humana"] == "fora"
    assert by.loc["10.1/s3", "decisao_final_revisada"] == "incluir"
    assert by.loc["10.1/s3", "origem_decisao"] == "pendente"
    assert len(out) == 5


def test_apply_decisions_robust_to_sheet_reordering():
    screening = pd.DataFrame([
        _row("duvida", "duvida", "incluir", "10.1/s1"),
        _row("incluir", "duvida", "incluir", "10.1/s2"),
    ])
    sheet = pd.DataFrame([
        {"review_id": _rid(screening.iloc[1].to_dict()), "decisao_humana": "e", "nota_humana": ""},
        {"review_id": _rid(screening.iloc[0].to_dict()), "decisao_humana": "i", "nota_humana": ""},
    ])  # ordem invertida de propósito
    out = apply_decisions(screening, sheet).set_index("doi")
    assert out.loc["10.1/s1", "decisao_final_revisada"] == "incluir"
    assert out.loc["10.1/s2", "decisao_final_revisada"] == "excluir"


def test_apply_decisions_invalid_value_raises_listing_rows():
    screening = pd.DataFrame([_row("duvida", "duvida", "incluir", "10.1/s1")])
    sheet = pd.DataFrame([
        {"review_id": _rid(screening.iloc[0].to_dict()), "decisao_humana": "talvez", "nota_humana": ""},
    ])
    with pytest.raises(ValueError, match="talvez"):
        apply_decisions(screening, sheet)
