from __future__ import annotations

import pandas as pd

from scripts.screening.revisao_export import soft_includes
from scripts.screening.revisao_export import build_sheet

SHEET_COLS = [
    "review_id", "decisao_humana", "nota_humana",
    "year", "title", "venue", "authors", "abstract",
    "decisao_sonnet", "confianca_sonnet", "justificativa_sonnet",
    "decisao_haiku", "confianca_haiku", "justificativa_haiku", "doi",
]


def _row(s, h, final):
    return {
        "source": "wos", "doi": "", "title": "T", "authors": "A",
        "year": 2020, "abstract": "x", "venue": "V", "language": "en",
        "decisao_sonnet": s, "justificativa_sonnet": "js", "confianca_sonnet": 0.5,
        "decisao_haiku": h, "justificativa_haiku": "jh", "confianca_haiku": 0.5,
        "decisao_final": final, "concordancia": "x", "criterio_exclusao": "",
    }


def test_soft_includes_excludes_both_incluir_and_both_excluir():
    df = pd.DataFrame([
        _row("incluir", "incluir", "incluir"),   # ambos-incluir → fora
        _row("excluir", "excluir", "excluir"),    # ambos-excluir → fora
        _row("incluir", "duvida", "incluir"),     # soft → dentro
        _row("duvida", "excluir", "incluir"),     # soft → dentro
        _row("incluir", "excluir", "incluir"),    # divergência → dentro
        _row("duvida", "duvida", "incluir"),      # soft → dentro
    ])
    sel = soft_includes(df)
    assert len(sel) == 4
    # nenhum ambos-incluir nem qualquer excluir-final no resultado
    assert ((sel["decisao_sonnet"] == "incluir") & (sel["decisao_haiku"] == "incluir")).sum() == 0
    assert (sel["decisao_final"] == "excluir").sum() == 0


def test_build_sheet_schema_and_empty_human_cols():
    df = pd.DataFrame([_row("incluir", "duvida", "incluir"),
                       _row("duvida", "duvida", "incluir")])
    sheet = build_sheet(df)
    assert list(sheet.columns) == SHEET_COLS
    assert len(sheet) == 2
    assert (sheet["decisao_humana"] == "").all()
    assert (sheet["nota_humana"] == "").all()
    # review_id estável e consistente com batch_client
    from scripts.screening.llm.batch_client import cache_key, custom_id
    assert sheet.iloc[0]["review_id"] == custom_id(cache_key(df.iloc[0]))


def test_build_sheet_review_id_unique_per_row():
    df = pd.DataFrame([
        {**_row("duvida", "duvida", "incluir"), "doi": "10.1/a"},
        {**_row("duvida", "duvida", "incluir"), "doi": "10.1/b"},
    ])
    sheet = build_sheet(df)
    assert sheet["review_id"].nunique() == 2
