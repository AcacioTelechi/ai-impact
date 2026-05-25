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
    ]
    p = tmp_path / "06_extraction.csv"
    pd.DataFrame(rows).to_csv(p, index=False, encoding="utf-8")
    return p


def test_filtra_incluidos_extraidos(tmp_path):
    c = load_corpus(_csv(tmp_path))
    assert c.n == 2
    assert c.n_pendentes == 1
    assert c.n_excluidos == 1
    assert set(c.df["elegivel"]) == {"incluir"}
    assert "parse_fail" not in set(c.df["nota_extracao"])


def test_coage_numericos(tmp_path):
    c = load_corpus(_csv(tmp_path))
    assert c.df["score_qualidade"].dtype.kind == "f"
    # vazio vira NaN
    assert c.df["magnitude_normalizada"].isna().sum() == 1
    assert pytest.approx(c.df["magnitude_normalizada"].dropna().iloc[0]) == 0.12
