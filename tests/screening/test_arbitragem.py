# tests/screening/test_arbitragem.py
from pathlib import Path

import pandas as pd

from scripts.screening.arbitragem import fundir, kappa_table
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


def test_kappa_table_writes_latex_pairwise(tmp_path: Path):
    df = pd.DataFrame([
        {"decisao_sonnet": "duvida", "decisao_haiku": "excluir",
         "decisao_arbitro": "excluir", "origem_decisao": "arbitro"},
        {"decisao_sonnet": "incluir", "decisao_haiku": "duvida",
         "decisao_arbitro": "incluir", "origem_decisao": "arbitro"},
        {"decisao_sonnet": "duvida", "decisao_haiku": "duvida",
         "decisao_arbitro": "incluir", "origem_decisao": "arbitro"},
        {"decisao_sonnet": "incluir", "decisao_haiku": "incluir",
         "decisao_arbitro": "", "origem_decisao": "llm_concordante"},  # ignorado
    ])
    out = tmp_path / "arbitragem_kappa.tex"
    kappa_table(df, out)
    tex = out.read_text(encoding="utf-8")
    assert "tabular" in tex
    assert "kappa" in tex.lower() or "$\\kappa$" in tex
    assert "Sonnet" in tex and "Haiku" in tex
    assert r"\%" in tex
    assert tex.count("{") == tex.count("}")
    assert "n=3" in tex or "n = 3" in tex
    # Numerical checks: arb=[excluir,incluir,incluir], son=[incluir,incluir,incluir]
    # Árbitro×Sonnet: 2/3 agree (rows 1,2 match; row 0 differs)
    assert "2/3" in tex
    # Árbitro×Haiku: hai=[excluir,incluir,incluir] → 3/3 agree
    assert "3/3" in tex


def test_kappa_table_discloses_arbitro_falha(tmp_path: Path):
    df = pd.DataFrame([
        {"decisao_sonnet": "duvida", "decisao_haiku": "excluir",
         "decisao_arbitro": "excluir", "origem_decisao": "arbitro"},
        {"decisao_sonnet": "duvida", "decisao_haiku": "duvida",
         "decisao_arbitro": "", "origem_decisao": "arbitro_falha"},
    ])
    out = tmp_path / "k.tex"
    kappa_table(df, out)
    tex = out.read_text(encoding="utf-8")
    assert "n=1" in tex or "n = 1" in tex          # só 1 arbitrado real no κ
    assert "1 falha" in tex or "falhas técnicas" in tex  # falha divulgada
    assert tex.count("{") == tex.count("}")


def test_kappa_table_empty_when_no_arbitrados(tmp_path: Path):
    df = pd.DataFrame([
        {"decisao_sonnet": "incluir", "decisao_haiku": "incluir",
         "decisao_arbitro": "", "origem_decisao": "llm_concordante"},
    ])
    out = tmp_path / "k.tex"
    kappa_table(df, out)
    tex = out.read_text(encoding="utf-8")
    assert "tabular" in tex
    assert tex.count("{") == tex.count("}")


from scripts.screening import arbitragem


def _screening_csv(tmp_path: Path) -> Path:
    p = tmp_path / "03_screening_ta.csv"
    pd.DataFrame([
        _row("incluir", "incluir", "incluir", "10.1/bi"),
        _row("excluir", "excluir", "excluir", "10.1/be"),
        _row("incluir", "duvida", "incluir", "10.1/s1"),
        _row("duvida", "duvida", "incluir", "10.1/s2"),
    ]).to_csv(p, index=False)
    return p


def test_run_mock_produces_arbitrado_and_incluidos(tmp_path: Path):
    src = _screening_csv(tmp_path)
    arb = tmp_path / "03_screening_arbitrado.csv"
    inc = tmp_path / "03_incluidos_final.csv"
    kap = tmp_path / "arbitragem_kappa.tex"
    arbitragem.run(screening_csv=src, arbitrado_csv=arb, incluidos_csv=inc,
                   kappa_table_path=kap, cache_dir=tmp_path, mock=True)
    a = pd.read_csv(arb, keep_default_na=False)
    assert len(a) == 4
    assert {"decisao_arbitro", "decisao_final_arbitrada", "origem_decisao"} <= set(a.columns)
    assert (a["origem_decisao"] == "llm_concordante").sum() == 2  # bi + be
    assert a["decisao_final_arbitrada"].isin(["incluir", "excluir"]).all()
    i = pd.read_csv(inc, keep_default_na=False)
    assert (i["decisao_final_arbitrada"] == "incluir").all()
    assert len(i) == (a["decisao_final_arbitrada"] == "incluir").sum()
    assert kap.exists() and "tabular" in kap.read_text()
