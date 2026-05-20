"""Testes do verify_ingest: κ + acurácia + erros."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


def _setup(tmp_path: Path, human=None, audit=None):
    """human: dict review_id→decisao; audit: dict (rid, campo) → ok/erro."""
    from scripts.screening.llm.batch_client import cache_key, custom_id

    def rid(i: int) -> str:
        return custom_id(cache_key(pd.Series({
            "doi": f"d{i}", "title": f"T{i}", "year": 2024,
        })))

    extr_rows = []
    for i in range(1, 11):
        extr_rows.append({
            "id": f"s-{i}", "doi": f"d{i}", "titulo": f"T{i}", "ano": 2024,
            "elegivel": "incluir" if i <= 8 else "excluir",
            "motivo_exclusao": "" if i <= 8 else "x",
            "text_source": "pdf", "confianca_extracao": 0.9,
            "nota_extracao": "",
            "pre_pos_chatgpt": "pos", "janela": "2024",
            "sinal_efeito": "neg", "tipo_estudo": "emp",
            "polarizacao": "sim", "score_qualidade": "4",
        })
    extr_p = tmp_path / "extr.csv"
    pd.DataFrame(extr_rows).to_csv(extr_p, index=False, encoding="utf-8")

    eleg_rows = []
    for i in range(1, 11):
        eleg_rows.append({
            "review_id": rid(i),
            "decisao_humana": (human or {}).get(rid(i), ""),
            "nota_humana": "", "year": 2024, "title": f"T{i}",
            "authors": "", "venue": "", "abstract": "",
            "text_source": "pdf", "criterios_ref": "x",
        })
    eleg_p = tmp_path / "eleg.csv"
    pd.DataFrame(eleg_rows).to_csv(eleg_p, index=False, encoding="utf-8")

    campos = ("pre_pos_chatgpt", "janela", "sinal_efeito",
              "tipo_estudo", "polarizacao", "score_qualidade")
    aud_rows = []
    for i in range(1, 9):  # só inclusões
        r = {"review_id": rid(i), "year": 2024, "title": f"T{i}",
             "doi": f"d{i}", "text_source": "pdf"}
        for c in campos:
            r[f"{c}_llm"] = "x"
            r[f"{c}_auditoria"] = (audit or {}).get((rid(i), c), "")
            r[f"{c}_correto"] = ""
        r["nota_auditoria"] = ""
        aud_rows.append(r)
    aud_p = tmp_path / "aud.csv"
    pd.DataFrame(aud_rows).to_csv(aud_p, index=False, encoding="utf-8")

    return extr_p, eleg_p, aud_p, rid


def test_kappa_um_quando_humano_concorda(tmp_path):
    from scripts.extraction import verify_ingest as V
    _, _, _, rid = _setup(tmp_path)
    # Humano = LLM em todos: inc para 1..8, exc para 9..10
    human = {rid(i): ("incluir" if i <= 8 else "excluir") for i in range(1, 11)}
    audit = {(rid(i), c): "ok"
             for i in range(1, 9)
             for c in ("pre_pos_chatgpt", "janela", "sinal_efeito",
                       "tipo_estudo", "polarizacao", "score_qualidade")}
    extr_p, eleg_p, aud_p, _ = _setup(tmp_path, human=human, audit=audit)
    kappa_t = tmp_path / "k.tex"
    acur_t = tmp_path / "a.tex"
    ann = tmp_path / "ann.csv"
    V.run(extraction=extr_p, sheet_eleg=eleg_p, sheet_aud=aud_p,
          kappa_table=kappa_t, acuracia_table=acur_t, annotated=ann)
    txt = kappa_t.read_text(encoding="utf-8")
    assert "1.000" in txt  # κ = 1


def test_kappa_negativo_quando_humano_discorda(tmp_path):
    from scripts.extraction import verify_ingest as V
    _, _, _, rid = _setup(tmp_path)
    # Humano inverte 100%: exc para 1..8, inc para 9..10
    human = {rid(i): ("excluir" if i <= 8 else "incluir") for i in range(1, 11)}
    audit = {(rid(i), c): "ok"
             for i in range(1, 9)
             for c in ("pre_pos_chatgpt", "janela", "sinal_efeito",
                       "tipo_estudo", "polarizacao", "score_qualidade")}
    extr_p, eleg_p, aud_p, _ = _setup(tmp_path, human=human, audit=audit)
    kappa_t = tmp_path / "k.tex"
    acur_t = tmp_path / "a.tex"
    ann = tmp_path / "ann.csv"
    V.run(extraction=extr_p, sheet_eleg=eleg_p, sheet_aud=aud_p,
          kappa_table=kappa_t, acuracia_table=acur_t, annotated=ann)
    txt = kappa_t.read_text(encoding="utf-8")
    # κ < 0 (com sinal negativo no LaTeX)
    assert "-" in txt or "$-$" in txt


def test_aborta_pendencias_eleg(tmp_path):
    from scripts.extraction import verify_ingest as V
    # decisao_humana vazia em algumas
    human = {}  # tudo vazio
    audit = {(_id, c): "ok" for _id, c in []}
    extr_p, eleg_p, aud_p, _ = _setup(tmp_path, human=human, audit=audit)
    with pytest.raises(ValueError, match="decisao_humana"):
        V.run(extraction=extr_p, sheet_eleg=eleg_p, sheet_aud=aud_p,
              kappa_table=tmp_path / "k.tex",
              acuracia_table=tmp_path / "a.tex",
              annotated=tmp_path / "ann.csv")


def test_aborta_pendencias_aud(tmp_path):
    from scripts.extraction import verify_ingest as V
    _, _, _, rid = _setup(tmp_path)
    human = {rid(i): ("incluir" if i <= 8 else "excluir") for i in range(1, 11)}
    # Auditoria parcial: só metade dos campos
    audit = {(rid(i), "pre_pos_chatgpt"): "ok" for i in range(1, 9)}
    extr_p, eleg_p, aud_p, _ = _setup(tmp_path, human=human, audit=audit)
    with pytest.raises(ValueError, match="auditoria"):
        V.run(extraction=extr_p, sheet_eleg=eleg_p, sheet_aud=aud_p,
              kappa_table=tmp_path / "k.tex",
              acuracia_table=tmp_path / "a.tex",
              annotated=tmp_path / "ann.csv")


def test_acuracia_por_campo(tmp_path):
    """sinal_efeito tem 4 ok + 4 erro → acurácia 0.500; pre_pos tem 8 ok → 1.000."""
    from scripts.extraction import verify_ingest as V
    _, _, _, rid = _setup(tmp_path)
    human = {rid(i): ("incluir" if i <= 8 else "excluir") for i in range(1, 11)}
    audit = {}
    for i in range(1, 9):
        for c in ("pre_pos_chatgpt", "janela", "tipo_estudo",
                  "polarizacao", "score_qualidade"):
            audit[(rid(i), c)] = "ok"
        audit[(rid(i), "sinal_efeito")] = "ok" if i <= 4 else "erro"
    extr_p, eleg_p, aud_p, _ = _setup(tmp_path, human=human, audit=audit)
    acur_t = tmp_path / "a.tex"
    V.run(extraction=extr_p, sheet_eleg=eleg_p, sheet_aud=aud_p,
          kappa_table=tmp_path / "k.tex",
          acuracia_table=acur_t, annotated=tmp_path / "ann.csv")
    txt = acur_t.read_text(encoding="utf-8")
    assert "50.0\\%" in txt  # sinal_efeito
    assert "100.0\\%" in txt  # pre_pos_chatgpt
