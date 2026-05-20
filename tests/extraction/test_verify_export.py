"""Testes do verify_export: planilha cega + planilha de auditoria + preservação."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest


def _mk_inputs(tmp_path: Path):
    # corpus tem o lado bibliográfico
    corpus_rows = [
        {"doi": f"d{i}", "title": f"Title {i}", "year": 2024,
         "authors": "X", "venue": "J", "abstract": f"Abs {i}"}
        for i in range(1, 11)
    ]
    corpus = pd.DataFrame(corpus_rows)

    # extraction tem o lado LLM (campos críticos); elegivel em valores reais
    extr_rows = []
    for i in range(1, 11):
        extr_rows.append({
            "id": f"s-{i}", "doi": f"d{i}", "titulo": f"Title {i}",
            "ano": 2024, "elegivel": "incluir" if i <= 8 else "excluir",
            "motivo_exclusao": "" if i <= 8 else "fora do escopo",
            "text_source": "pdf" if i % 2 else "abstract",
            "confianca_extracao": 0.8, "nota_extracao": "",
            "pre_pos_chatgpt": "pos", "janela": "2023-2024",
            "sinal_efeito": "negativo", "tipo_estudo": "empirico",
            "polarizacao": "sim", "score_qualidade": "4",
        })
    extr = pd.DataFrame(extr_rows)

    # amostra inclui 2 exclusões (i=9,10) + 3 inclusões (i=1,2,3)
    from scripts.screening.llm.batch_client import cache_key, custom_id

    def rid(i: int) -> str:
        return custom_id(cache_key(pd.Series({
            "doi": f"d{i}", "title": f"Title {i}", "year": 2024,
        })))

    sample = pd.DataFrame([
        {"review_id": rid(9), "estrato": "excluir", "tipo": "exclusao"},
        {"review_id": rid(10), "estrato": "excluir", "tipo": "exclusao"},
        {"review_id": rid(1), "estrato": "pdf_alta", "tipo": "inclusao"},
        {"review_id": rid(2), "estrato": "abstract_alta", "tipo": "inclusao"},
        {"review_id": rid(3), "estrato": "pdf_alta", "tipo": "inclusao"},
    ])

    cp = tmp_path / "corpus.csv"
    ep = tmp_path / "extr.csv"
    sp = tmp_path / "sample.csv"
    corpus.to_csv(cp, index=False, encoding="utf-8")
    extr.to_csv(ep, index=False, encoding="utf-8")
    sample.to_csv(sp, index=False, encoding="utf-8")
    return cp, ep, sp


def test_planilha_eleg_e_cega(tmp_path):
    from scripts.extraction import verify_export as V
    corpus, extr, sample = _mk_inputs(tmp_path)
    eleg = tmp_path / "eleg.csv"
    aud = tmp_path / "aud.csv"
    V.run(extraction=extr, corpus=corpus, sample=sample,
          sheet_eleg=eleg, sheet_aud=aud)

    df = pd.read_csv(eleg, encoding="utf-8", keep_default_na=False)
    assert len(df) == 5
    assert set(df.columns) == {
        "review_id", "decisao_humana", "nota_humana",
        "year", "title", "authors", "venue", "abstract",
        "text_source", "criterios_ref",
    }
    # Cegueira: nenhuma coluna LLM
    for forbidden in ("elegivel", "motivo_exclusao",
                      "decisao_arbitro", "pre_pos_chatgpt",
                      "sinal_efeito", "score_qualidade"):
        assert forbidden not in df.columns


def test_planilha_aud_so_inclusoes(tmp_path):
    from scripts.extraction import verify_export as V
    corpus, extr, sample = _mk_inputs(tmp_path)
    eleg = tmp_path / "eleg.csv"
    aud = tmp_path / "aud.csv"
    V.run(extraction=extr, corpus=corpus, sample=sample,
          sheet_eleg=eleg, sheet_aud=aud)

    df = pd.read_csv(aud, encoding="utf-8", keep_default_na=False)
    assert len(df) == 3  # apenas as 3 inclusões
    # Cabeçalho + 6 campos × 3 colunas + nota
    for campo in ("pre_pos_chatgpt", "janela", "sinal_efeito",
                  "tipo_estudo", "polarizacao", "score_qualidade"):
        assert f"{campo}_llm" in df.columns
        assert f"{campo}_auditoria" in df.columns
        assert f"{campo}_correto" in df.columns
    assert "nota_auditoria" in df.columns
    # Valores LLM presentes (não-vazios)
    assert (df["pre_pos_chatgpt_llm"] == "pos").all()


def test_merge_preserva_input_humano(tmp_path):
    """Segunda rodada preserva decisao_humana e auditoria preenchidas."""
    from scripts.extraction import verify_export as V
    corpus, extr, sample = _mk_inputs(tmp_path)
    eleg = tmp_path / "eleg.csv"
    aud = tmp_path / "aud.csv"
    V.run(extraction=extr, corpus=corpus, sample=sample,
          sheet_eleg=eleg, sheet_aud=aud)

    # Humano preenche 1 linha em cada
    df_e = pd.read_csv(eleg, encoding="utf-8", keep_default_na=False)
    df_e.loc[0, "decisao_humana"] = "incluir"
    df_e.loc[0, "nota_humana"] = "comentário"
    df_e.to_csv(eleg, index=False, encoding="utf-8")
    df_a = pd.read_csv(aud, encoding="utf-8", keep_default_na=False)
    df_a.loc[0, "pre_pos_chatgpt_auditoria"] = "ok"
    df_a.loc[0, "sinal_efeito_auditoria"] = "erro"
    df_a.loc[0, "sinal_efeito_correto"] = "positivo"
    df_a.to_csv(aud, index=False, encoding="utf-8")

    V.run(extraction=extr, corpus=corpus, sample=sample,
          sheet_eleg=eleg, sheet_aud=aud)

    df_e2 = pd.read_csv(eleg, encoding="utf-8", keep_default_na=False)
    df_a2 = pd.read_csv(aud, encoding="utf-8", keep_default_na=False)
    # eleg: ambas colunas preservadas
    rid_e = df_e.loc[0, "review_id"]
    row_e2 = df_e2.loc[df_e2["review_id"] == rid_e].iloc[0]
    assert row_e2["decisao_humana"] == "incluir"
    assert row_e2["nota_humana"] == "comentário"
    # aud: três colunas preservadas
    rid_a = df_a.loc[0, "review_id"]
    row_a2 = df_a2.loc[df_a2["review_id"] == rid_a].iloc[0]
    assert row_a2["pre_pos_chatgpt_auditoria"] == "ok"
    assert row_a2["sinal_efeito_auditoria"] == "erro"
    assert row_a2["sinal_efeito_correto"] == "positivo"


def test_backup_criado_em_re_export(tmp_path):
    from scripts.extraction import verify_export as V
    corpus, extr, sample = _mk_inputs(tmp_path)
    eleg = tmp_path / "eleg.csv"
    aud = tmp_path / "aud.csv"
    V.run(extraction=extr, corpus=corpus, sample=sample,
          sheet_eleg=eleg, sheet_aud=aud)
    V.run(extraction=extr, corpus=corpus, sample=sample,
          sheet_eleg=eleg, sheet_aud=aud)
    backups_e = list(tmp_path.glob("eleg.bak-*.csv"))
    backups_a = list(tmp_path.glob("aud.bak-*.csv"))
    assert backups_e and backups_a


def test_aborta_em_review_id_duplicado(tmp_path):
    """Se a planilha prévia tem review_id duplicado, levanta ValueError listando."""
    from scripts.extraction import verify_export as V
    corpus, extr, sample = _mk_inputs(tmp_path)
    eleg = tmp_path / "eleg.csv"
    aud = tmp_path / "aud.csv"
    V.run(extraction=extr, corpus=corpus, sample=sample,
          sheet_eleg=eleg, sheet_aud=aud)
    df_e = pd.read_csv(eleg, encoding="utf-8", keep_default_na=False)
    # Simula edição que duplicou um review_id (acidente comum no LibreOffice).
    dup = df_e.iloc[[0]].copy()
    df_e2 = pd.concat([df_e, dup], ignore_index=True)
    df_e2.to_csv(eleg, index=False, encoding="utf-8")
    with pytest.raises(ValueError, match="review_id duplicado"):
        V.run(extraction=extr, corpus=corpus, sample=sample,
              sheet_eleg=eleg, sheet_aud=aud)


def test_warning_quando_decisao_humana_some(tmp_path, capsys):
    """Se uma decisao registrada no .state.json sumir da planilha, avisa."""
    from scripts.extraction import verify_export as V
    corpus, extr, sample = _mk_inputs(tmp_path)
    eleg = tmp_path / "eleg.csv"
    aud = tmp_path / "aud.csv"
    V.run(extraction=extr, corpus=corpus, sample=sample,
          sheet_eleg=eleg, sheet_aud=aud)
    # Humano preenche 1 decisao na eleg.
    df_e = pd.read_csv(eleg, encoding="utf-8", keep_default_na=False)
    df_e.loc[0, "decisao_humana"] = "incluir"
    df_e.to_csv(eleg, index=False, encoding="utf-8")
    # Re-export para que .state.json registre a decisão.
    V.run(extraction=extr, corpus=corpus, sample=sample,
          sheet_eleg=eleg, sheet_aud=aud)
    # Humano apaga a decisão acidentalmente.
    df_e = pd.read_csv(eleg, encoding="utf-8", keep_default_na=False)
    df_e.loc[0, "decisao_humana"] = ""
    df_e.to_csv(eleg, index=False, encoding="utf-8")
    # Re-export deve avisar.
    V.run(extraction=extr, corpus=corpus, sample=sample,
          sheet_eleg=eleg, sheet_aud=aud)
    out = capsys.readouterr().out
    assert "ATENÇÃO" in out
    assert "elegibilidade" in out
