# tests/screening/test_revisao_ingest.py
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.screening import revisao_ingest
from scripts.screening.revisao_ingest import normalize_decisao, apply_decisions
from scripts.screening.llm.batch_client import cache_key, custom_id


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


def test_run_writes_revisado_and_incluidos(tmp_path, capsys):
    screening = pd.DataFrame([
        _row("incluir", "incluir", "incluir", "10.1/bi"),
        _row("excluir", "excluir", "excluir", "10.1/be"),
        _row("incluir", "duvida", "incluir", "10.1/s1"),
        _row("duvida", "duvida", "incluir", "10.1/s2"),
    ])
    scsv = tmp_path / "03_screening_ta.csv"
    screening.to_csv(scsv, index=False)
    sheet = pd.DataFrame([
        {"review_id": _rid(screening.iloc[2].to_dict()), "decisao_humana": "i", "nota_humana": ""},
        {"review_id": _rid(screening.iloc[3].to_dict()), "decisao_humana": "", "nota_humana": ""},
    ])
    shcsv = tmp_path / "03_revisao_duvidas.csv"
    sheet.to_csv(shcsv, index=False)

    rev = tmp_path / "03_screening_revisado.csv"
    inc = tmp_path / "03_incluidos_final.csv"
    revisao_ingest.run(screening_csv=scsv, sheet_csv=shcsv,
                        revisado_csv=rev, incluidos_csv=inc)

    r = pd.read_csv(rev, keep_default_na=False)
    assert len(r) == 4
    assert {"decisao_final_revisada", "origem_decisao", "nota_humana"} <= set(r.columns)
    i = pd.read_csv(inc, keep_default_na=False)
    # incluídos = bi (llm) + s1 (humano i) + s2 (pendente→incluir) = 3
    assert len(i) == 3
    assert "10.1/be" not in set(i["doi"])
    out = capsys.readouterr().out
    assert "pendente" in out.lower()
    assert "1 PENDENTES" in out


def test_run_invalid_sheet_aborts_without_writing(tmp_path):
    screening = pd.DataFrame([_row("duvida", "duvida", "incluir", "10.1/s1")])
    scsv = tmp_path / "s.csv"; screening.to_csv(scsv, index=False)
    sheet = pd.DataFrame([
        {"review_id": _rid(screening.iloc[0].to_dict()), "decisao_humana": "talvez", "nota_humana": ""},
    ])
    shcsv = tmp_path / "sh.csv"; sheet.to_csv(shcsv, index=False)
    rev = tmp_path / "rev.csv"; inc = tmp_path / "inc.csv"
    with pytest.raises(ValueError):
        revisao_ingest.run(screening_csv=scsv, sheet_csv=shcsv,
                            revisado_csv=rev, incluidos_csv=inc)
    assert not rev.exists() and not inc.exists()
