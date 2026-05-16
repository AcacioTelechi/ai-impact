from pathlib import Path

import pandas as pd

from scripts.screening.agreement import cohen_kappa, run


def test_kappa_perfect_agreement():
    a = ["incluir", "excluir", "duvida", "incluir"]
    assert cohen_kappa(a, list(a)) == 1.0


def test_kappa_independent_is_near_zero():
    a = ["incluir"] * 50 + ["excluir"] * 50
    b = (["incluir", "excluir"] * 50)
    k = cohen_kappa(a, b)
    assert -0.3 < k < 0.3


def test_run_writes_latex_table(tmp_path: Path):
    src = tmp_path / "03.csv"
    pd.DataFrame({
        "decisao_sonnet": ["incluir", "excluir", "duvida", "incluir"],
        "decisao_haiku":  ["incluir", "excluir", "incluir", "incluir"],
    }).to_csv(src, index=False)
    out = tmp_path / "kappa_screening.tex"
    run(input=src, output_table=out)
    tex = out.read_text(encoding="utf-8")
    assert "tabular" in tex
    assert "kappa" in tex.lower() or "κ" in tex or "$\\kappa$" in tex
    for lab in ("incluir", "excluir", "duvida"):
        assert lab in tex
    assert r"\%" in tex  # percent MUST be LaTeX-escaped (bare % is a comment)
    assert tex.count("{") == tex.count("}")  # brace balance (caption not eaten)


def test_run_handles_empty_input(tmp_path):
    src = tmp_path / "empty.csv"
    pd.DataFrame({"decisao_sonnet": [], "decisao_haiku": []}).to_csv(src, index=False)
    out = tmp_path / "k.tex"
    run(input=src, output_table=out)
    tex = out.read_text(encoding="utf-8")
    assert "tabular" in tex
    assert tex.count("{") == tex.count("}")
