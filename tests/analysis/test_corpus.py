from pathlib import Path

import pandas as pd
import pytest

from scripts.analysis.corpus import load_corpus


def _csv(tmp_path: Path) -> Path:
    rows = [
        # incluir + extraído de verdade  -> entra
        {"elegivel": "incluir", "nota_extracao": "ok", "score_qualidade": "4",
         "magnitude_normalizada": "0.12", "pre_pos_chatgpt": "pos"},
        {"elegivel": "incluir", "nota_extracao": "", "score_qualidade": "3",
         "magnitude_normalizada": "", "pre_pos_chatgpt": "pre"},
        # incluir mas parse_fail -> fora (pendente)
        {"elegivel": "incluir", "nota_extracao": "parse_fail", "score_qualidade": "",
         "magnitude_normalizada": "", "pre_pos_chatgpt": "pos"},
        # excluir -> fora
        {"elegivel": "excluir", "nota_extracao": "ok", "score_qualidade": "2",
         "magnitude_normalizada": "", "pre_pos_chatgpt": "pre"},
        # excluir E parse_fail -> conta como excluído, NÃO como pendente
        {"elegivel": "excluir", "nota_extracao": "parse_fail", "score_qualidade": "",
         "magnitude_normalizada": "", "pre_pos_chatgpt": "pos"},
    ]
    p = tmp_path / "06_extraction.csv"
    pd.DataFrame(rows).to_csv(p, index=False, encoding="utf-8")
    return p


def test_filtra_incluidos_extraidos(tmp_path):
    c = load_corpus(_csv(tmp_path))
    assert c.n == 2
    assert c.n_pendentes == 1
    assert c.n_excluidos == 2
    assert set(c.df["elegivel"]) == {"incluir"}
    assert "parse_fail" not in set(c.df["nota_extracao"])


def test_coage_numericos(tmp_path):
    c = load_corpus(_csv(tmp_path))
    assert c.df["score_qualidade"].dtype.kind == "f"
    # vazio vira NaN
    assert c.df["magnitude_normalizada"].isna().sum() == 1
    assert pytest.approx(c.df["magnitude_normalizada"].dropna().iloc[0]) == 0.12


def test_normaliza_horizonte(tmp_path):
    rows = [
        {"elegivel": "incluir", "nota_extracao": "ok", "horizonte": "médio",
         "score_qualidade": "3", "magnitude_normalizada": ""},
        {"elegivel": "incluir", "nota_extracao": "ok", "horizonte": "longo",
         "score_qualidade": "3", "magnitude_normalizada": ""},
        {"elegivel": "incluir", "nota_extracao": "ok", "horizonte": "curto prazo",
         "score_qualidade": "3", "magnitude_normalizada": ""},
    ]
    p = tmp_path / "06_extraction.csv"
    pd.DataFrame(rows).to_csv(p, index=False, encoding="utf-8")
    h = set(load_corpus(p).df["horizonte"])
    assert h == {"médio prazo", "longo prazo", "curto prazo"}


def test_periodo_deterministico_pelo_ano(tmp_path):
    """Período/janela vêm do ano de publicação; o valor do LLM fica em *_llm."""
    base = {"elegivel": "incluir", "nota_extracao": "ok", "score_qualidade": "3",
            "magnitude_normalizada": ""}
    rows = [
        {**base, "ano": "2017", "pre_pos_chatgpt": "pre", "janela": "2013-2017"},
        {**base, "ano": "2022", "pre_pos_chatgpt": "pos", "janela": "2022-2026"},
        # publicado em 2025 com dados antigos: o LLM disse "pre"; a publicação é pós
        {**base, "ano": "2025", "pre_pos_chatgpt": "pre", "janela": "2013-2017"},
    ]
    p = tmp_path / "06_extraction.csv"
    pd.DataFrame(rows).to_csv(p, index=False, encoding="utf-8")
    df = load_corpus(p).df
    assert list(df["pre_pos_chatgpt"]) == ["pre", "pre", "pos"]
    assert list(df["janela"]) == ["2013-2017", "2018-2022", "2022-2026"]
    assert list(df["pre_pos_chatgpt_llm"]) == ["pre", "pos", "pre"]
    assert list(df["janela_llm"]) == ["2013-2017", "2022-2026", "2013-2017"]
