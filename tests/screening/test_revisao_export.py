from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.screening.llm.batch_client import cache_key, custom_id
from scripts.screening.revisao_export import SHEET_COLS, build_sheet, soft_includes


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
    assert sheet.iloc[0]["review_id"] == custom_id(cache_key(df.iloc[0]))


def test_build_sheet_review_id_unique_per_row():
    df = pd.DataFrame([
        {**_row("duvida", "duvida", "incluir"), "doi": "10.1/a"},
        {**_row("duvida", "duvida", "incluir"), "doi": "10.1/b"},
    ])
    sheet = build_sheet(df)
    assert sheet["review_id"].nunique() == 2


from scripts.screening.revisao_export import merge_preserve


def test_merge_preserve_keeps_filled_decisions_and_adds_new():
    fresh = pd.DataFrame({
        "review_id": ["a", "b", "c"],
        "decisao_humana": ["", "", ""],
        "nota_humana": ["", "", ""],
        "title": ["TA", "TB", "TC"],
    })
    existing = pd.DataFrame({
        "review_id": ["a", "b"],
        "decisao_humana": ["i", "e"],
        "nota_humana": ["gostei", ""],
        "title": ["TA", "TB"],
    })
    merged = merge_preserve(fresh, existing)
    by = merged.set_index("review_id")
    assert by.loc["a", "decisao_humana"] == "i"      # preservado
    assert by.loc["a", "nota_humana"] == "gostei"    # preservado
    assert by.loc["b", "decisao_humana"] == "e"      # preservado
    assert by.loc["c", "decisao_humana"] == ""       # novo, vazio
    assert len(merged) == 3


def test_merge_preserve_retains_orphaned_decided_rows():
    """Linha decidida que sumiu do conjunto fresh não é descartada."""
    fresh = pd.DataFrame({
        "review_id": ["a"], "decisao_humana": [""], "nota_humana": [""],
        "title": ["TA"],
    })
    existing = pd.DataFrame({
        "review_id": ["a", "z"],
        "decisao_humana": ["", "i"],   # 'z' não está em fresh mas foi decidido
        "nota_humana": ["", "nota z"],
        "title": ["TA", "TZ"],
    })
    merged = merge_preserve(fresh, existing)
    assert "z" in set(merged["review_id"])
    z = merged.set_index("review_id").loc["z"]
    assert z["decisao_humana"] == "i"


def test_merge_preserve_no_existing_returns_fresh():
    fresh = pd.DataFrame({
        "review_id": ["a"], "decisao_humana": [""], "nota_humana": [""],
        "title": ["TA"],
    })
    out = merge_preserve(fresh, None)
    assert out.equals(fresh)


def test_merge_preserve_rejects_duplicate_review_id():
    fresh = pd.DataFrame({
        "review_id": ["a"], "decisao_humana": [""], "nota_humana": [""], "title": ["TA"],
    })
    existing = pd.DataFrame({
        "review_id": ["a", "a"],  # duplicado pelo usuário no LibreOffice
        "decisao_humana": ["i", "e"], "nota_humana": ["", ""], "title": ["TA", "TA"],
    })
    with pytest.raises(ValueError, match="review_id duplicado"):
        merge_preserve(fresh, existing)


def test_merge_preserve_nan_decisions_treated_as_blank():
    """existing lido sem keep_default_na=False traz NaN; deve virar ''."""
    fresh = pd.DataFrame({
        "review_id": ["a", "b"], "decisao_humana": ["", ""],
        "nota_humana": ["", ""], "title": ["TA", "TB"],
    })
    existing = pd.DataFrame({
        "review_id": ["a", "b"],
        "decisao_humana": ["i", np.nan],   # 'b' em branco como NaN
        "nota_humana": [np.nan, ""], "title": ["TA", "TB"],
    })
    merged = merge_preserve(fresh, existing).set_index("review_id")
    assert merged.loc["a", "decisao_humana"] == "i"
    assert merged.loc["a", "nota_humana"] == ""      # NaN → ""
    assert merged.loc["b", "decisao_humana"] == ""   # NaN → ""
