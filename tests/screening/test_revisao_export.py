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


from pathlib import Path

from scripts.screening import revisao_export


def _screening_csv(tmp_path: Path) -> Path:
    p = tmp_path / "03_screening_ta.csv"
    pd.DataFrame([
        {**_row("incluir", "incluir", "incluir"), "doi": "10.1/bi"},   # both-incluir
        {**_row("excluir", "excluir", "excluir"), "doi": "10.1/be"},   # both-excluir
        {**_row("incluir", "duvida", "incluir"), "doi": "10.1/s1"},    # soft
        {**_row("duvida", "excluir", "incluir"), "doi": "10.1/s2"},    # soft
    ]).to_csv(p, index=False)
    return p


def test_run_creates_sheet_with_only_soft_includes(tmp_path: Path):
    src = _screening_csv(tmp_path)
    sheet = tmp_path / "03_revisao_duvidas.csv"
    revisao_export.run(screening_csv=src, sheet_csv=sheet)
    s = pd.read_csv(sheet, keep_default_na=False)
    assert len(s) == 2  # só os 2 soft
    assert set(s["doi"]) == {"10.1/s1", "10.1/s2"}
    assert (s["decisao_humana"] == "").all()


def test_run_reexport_is_non_destructive(tmp_path: Path):
    src = _screening_csv(tmp_path)
    sheet = tmp_path / "03_revisao_duvidas.csv"
    revisao_export.run(screening_csv=src, sheet_csv=sheet)
    s = pd.read_csv(sheet, keep_default_na=False)
    s.loc[s["doi"] == "10.1/s1", "decisao_humana"] = "e"
    s.loc[s["doi"] == "10.1/s1", "nota_humana"] = "fora do escopo"
    s.to_csv(sheet, index=False)
    # re-export
    revisao_export.run(screening_csv=src, sheet_csv=sheet)
    s2 = pd.read_csv(sheet, keep_default_na=False)
    row = s2[s2["doi"] == "10.1/s1"].iloc[0]
    assert row["decisao_humana"] == "e"
    assert row["nota_humana"] == "fora do escopo"


import json as _json


def test_run_first_export_writes_state_no_backup(tmp_path: Path):
    src = _screening_csv(tmp_path)
    sheet = tmp_path / "03_revisao_duvidas.csv"
    revisao_export.run(screening_csv=src, sheet_csv=sheet)
    assert not list(tmp_path.glob("*.bak-*.csv"))          # nada para backupar
    state = sheet.with_suffix(".state.json")
    assert state.exists()
    assert _json.loads(state.read_text())["decided_review_ids"] == []


def test_run_backup_taken_on_reexport(tmp_path: Path):
    src = _screening_csv(tmp_path)
    sheet = tmp_path / "03_revisao_duvidas.csv"
    revisao_export.run(screening_csv=src, sheet_csv=sheet)
    revisao_export.run(screening_csv=src, sheet_csv=sheet)
    assert len(list(tmp_path.glob("03_revisao_duvidas.bak-*.csv"))) == 1


def test_run_no_warning_on_normal_reexport(tmp_path: Path, capsys):
    src = _screening_csv(tmp_path)
    sheet = tmp_path / "03_revisao_duvidas.csv"
    revisao_export.run(screening_csv=src, sheet_csv=sheet)
    s = pd.read_csv(sheet, keep_default_na=False)
    s.loc[s["doi"] == "10.1/s1", "decisao_humana"] = "e"
    s.to_csv(sheet, index=False)
    capsys.readouterr()
    revisao_export.run(screening_csv=src, sheet_csv=sheet)  # decisão preservada
    out = capsys.readouterr().out
    assert "ATENÇÃO" not in out
    s2 = pd.read_csv(sheet, keep_default_na=False)
    assert (s2["decisao_humana"] == "e").sum() == 1


def test_run_warns_when_decided_row_deleted_and_saved(tmp_path: Path, capsys):
    src = _screening_csv(tmp_path)
    sheet = tmp_path / "03_revisao_duvidas.csv"
    revisao_export.run(screening_csv=src, sheet_csv=sheet)
    s = pd.read_csv(sheet, keep_default_na=False)
    s.loc[s["doi"] == "10.1/s1", "decisao_humana"] = "i"
    s.to_csv(sheet, index=False)
    revisao_export.run(screening_csv=src, sheet_csv=sheet)  # state agora tem s1 decidido
    capsys.readouterr()
    # usuário apaga a linha decidida e salva
    s3 = pd.read_csv(sheet, keep_default_na=False)
    s3 = s3[s3["doi"] != "10.1/s1"]
    s3.to_csv(sheet, index=False)
    revisao_export.run(screening_csv=src, sheet_csv=sheet)
    out = capsys.readouterr().out
    assert "ATENÇÃO" in out
    assert "sumiram" in out
    assert ".bak-" in out


def test_run_no_false_positive_on_corpus_growth(tmp_path: Path, capsys):
    # primeiro corpus com 2 soft (s1,s2); decide s1
    src = _screening_csv(tmp_path)
    sheet = tmp_path / "03_revisao_duvidas.csv"
    revisao_export.run(screening_csv=src, sheet_csv=sheet)
    s = pd.read_csv(sheet, keep_default_na=False)
    s.loc[s["doi"] == "10.1/s1", "decisao_humana"] = "i"
    s.to_csv(sheet, index=False)
    revisao_export.run(screening_csv=src, sheet_csv=sheet)  # state: s1 decidido
    capsys.readouterr()
    # corpus CRESCE: adiciona um novo soft-include s3
    base = pd.read_csv(src, keep_default_na=False)
    grown = pd.concat(
        [base, pd.DataFrame([{**_row("duvida", "duvida", "incluir"), "doi": "10.1/s3"}])],
        ignore_index=True,
    )
    grown.to_csv(src, index=False)
    revisao_export.run(screening_csv=src, sheet_csv=sheet)
    out = capsys.readouterr().out
    assert "ATENÇÃO" not in out   # crescimento NÃO é perda → sem alarme falso
