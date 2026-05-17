# tests/screening/test_arbitragem.py
import pandas as pd

from scripts.screening.arbitragem import fundir
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


def test_fundir_four_categories_plus_failure():
    screening = pd.DataFrame([
        _row("incluir", "incluir", "incluir", "10.1/bi"),
        _row("excluir", "excluir", "excluir", "10.1/be"),
        _row("incluir", "duvida", "incluir", "10.1/s1"),
        _row("duvida", "excluir", "incluir", "10.1/s2"),
        _row("duvida", "duvida", "incluir", "10.1/s3"),
    ])
    arb = {
        _rid(screening.iloc[2].to_dict()): {"decisao": "incluir", "justificativa": "ok", "confianca": 0.9},
        _rid(screening.iloc[3].to_dict()): {"decisao": "excluir", "justificativa": "E1", "confianca": 0.8},
        _rid(screening.iloc[4].to_dict()): {"decisao": "duvida", "justificativa": "parse_fail", "confianca": 0.0},
    }
    out = fundir(screening, arb).set_index("doi")
    assert out.loc["10.1/bi", "decisao_final_arbitrada"] == "incluir"
    assert out.loc["10.1/bi", "origem_decisao"] == "llm_concordante"
    assert out.loc["10.1/be", "decisao_final_arbitrada"] == "excluir"
    assert out.loc["10.1/be", "origem_decisao"] == "llm_concordante"
    assert out.loc["10.1/s1", "decisao_final_arbitrada"] == "incluir"
    assert out.loc["10.1/s1", "origem_decisao"] == "arbitro"
    assert out.loc["10.1/s1", "decisao_arbitro"] == "incluir"
    assert out.loc["10.1/s2", "decisao_final_arbitrada"] == "excluir"
    assert out.loc["10.1/s2", "origem_decisao"] == "arbitro"
    assert out.loc["10.1/s3", "decisao_final_arbitrada"] == "incluir"
    assert out.loc["10.1/s3", "origem_decisao"] == "arbitro_falha"
    assert len(out) == 5


def test_fundir_concordantes_have_empty_arbiter_cols():
    screening = pd.DataFrame([_row("incluir", "incluir", "incluir", "10.1/bi")])
    out = fundir(screening, {})
    assert out.iloc[0]["decisao_arbitro"] == ""
    assert out.iloc[0]["justificativa_arbitro"] == ""
    assert out.iloc[0]["confianca_arbitro"] == ""


def test_fundir_missing_rid_is_conservative_arbitro_falha():
    screening = pd.DataFrame([_row("duvida", "duvida", "incluir", "10.1/miss")])
    out = fundir(screening, {}).iloc[0]   # arb_by_rid vazio → rid ausente
    assert out["decisao_final_arbitrada"] == "incluir"   # nunca exclui por falta de árbitro
    assert out["origem_decisao"] == "arbitro_falha"
    assert out["decisao_arbitro"] == ""
