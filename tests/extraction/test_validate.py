from pathlib import Path

import pandas as pd

from scripts.extraction import validate


def _row(**overrides) -> dict:
    base = {
        "id": "s-001", "ano": 2020, "janela": "2018-2022", "pre_pos_chatgpt": "pre",
        "sinal_efeito": "negativo", "mec_deslocamento": "sim",
        "mec_reinstalacao": "nao", "score_qualidade": 4,
    }
    base.update(overrides)
    return base


def test_validate_detects_inconsistent_window(tmp_path: Path) -> None:
    df = pd.DataFrame([_row(ano=2024, janela="2018-2022")])
    out = tmp_path / "out.csv"
    df.to_csv(out, index=False)
    issues = validate.run(out)
    assert any(i["rule"] == "year_window_mismatch" for i in issues)


def test_validate_detects_pre_pos_inconsistency(tmp_path: Path) -> None:
    df = pd.DataFrame([_row(ano=2024, janela="2022-2025", pre_pos_chatgpt="pre")])
    out = tmp_path / "out.csv"
    df.to_csv(out, index=False)
    issues = validate.run(out)
    assert any(i["rule"] == "pre_pos_chatgpt_inconsistent" for i in issues)


def test_validate_passes_clean_row(tmp_path: Path) -> None:
    df = pd.DataFrame([_row()])
    out = tmp_path / "out.csv"
    df.to_csv(out, index=False)
    issues = validate.run(out)
    assert issues == []
