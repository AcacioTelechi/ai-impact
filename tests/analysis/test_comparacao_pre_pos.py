from pathlib import Path

import pandas as pd

from scripts.analysis import comparacao_pre_pos


def _sample() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"pre_pos_chatgpt": "pre", "sinal_efeito": "negativo", "polarizacao": "baixa-quali em risco",
             "tecnologia_focada": "automação", "tipo_estudo": "exposição ocupacional"},
            {"pre_pos_chatgpt": "pre", "sinal_efeito": "negativo", "polarizacao": "baixa-quali em risco",
             "tecnologia_focada": "ML/preditiva", "tipo_estudo": "evidência macro/setorial"},
            {"pre_pos_chatgpt": "pos", "sinal_efeito": "ambíguo", "polarizacao": "alta-quali em risco",
             "tecnologia_focada": "IA generativa/LLMs", "tipo_estudo": "exposição ocupacional"},
            {"pre_pos_chatgpt": "pos", "sinal_efeito": "positivo", "polarizacao": "alta-quali em risco",
             "tecnologia_focada": "IA generativa/LLMs", "tipo_estudo": "firma/freelancer"},
        ]
    )


def test_comparacao_writes_latex_table(tmp_path: Path) -> None:
    df = _sample()
    ext = tmp_path / "ext.csv"
    df.to_csv(ext, index=False)
    out_tex = tmp_path / "comparacao.tex"
    comparacao_pre_pos.run(input=ext, output_table=out_tex)
    txt = out_tex.read_text()
    assert "\\begin{tabular}" in txt
    assert "Pré" in txt or "pre" in txt
    assert "Pós" in txt or "pos" in txt


def test_comparacao_counts_are_correct(tmp_path: Path) -> None:
    df = _sample()
    ext = tmp_path / "ext.csv"
    df.to_csv(ext, index=False)
    result = comparacao_pre_pos.compute(df)
    assert result["n_pre"] == 2
    assert result["n_pos"] == 2
    # both pre rows have sinal negativo, polarizacao baixa-quali
    assert result["pre"]["sinal_efeito"]["negativo"] == 2
