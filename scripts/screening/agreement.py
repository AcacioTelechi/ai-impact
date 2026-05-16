"""Concordância inter-modelo do screening: κ de Cohen + matriz 3×3 → LaTeX.

Lê 03_screening_ta.csv (colunas decisao_sonnet, decisao_haiku) e gera
text/tables/kappa_screening.tex para o capítulo de metodologia.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import cohen_kappa_score, confusion_matrix

_LABELS = ["incluir", "excluir", "duvida"]


def cohen_kappa(a: list[str], b: list[str]) -> float:
    return float(cohen_kappa_score(a, b, labels=_LABELS))


def run(input: Path, output_table: Path) -> None:
    df = pd.read_csv(input, encoding="utf-8")
    s = df["decisao_sonnet"].astype(str).tolist()
    h = df["decisao_haiku"].astype(str).tolist()
    k = cohen_kappa(s, h)
    n = len(df)
    agree = int((df["decisao_sonnet"] == df["decisao_haiku"]).sum())
    cm = confusion_matrix(s, h, labels=_LABELS)

    rows = []
    for i, lab in enumerate(_LABELS):
        cells = " & ".join(str(int(x)) for x in cm[i])
        rows.append(f"{lab} & {cells} \\\\")
    body = "\n".join(rows)

    tex = (
        "\\begin{table}[ht]\n\\centering\n"
        "\\caption{Concordância inter-modelo no screening "
        f"($\\kappa$ de Cohen = {k:.3f}; "
        f"concordância = {agree}/{n} = {agree / n:.1%})}}\n"
        "\\label{tab:kappa-screening}\n"
        "\\begin{tabular}{lccc}\n\\toprule\n"
        " & \\multicolumn{3}{c}{Haiku 4.5} \\\\\n"
        "Sonnet 4.6 & incluir & excluir & duvida \\\\\n\\midrule\n"
        f"{body}\n"
        "\\bottomrule\n\\end{tabular}\n\\end{table}\n"
    )
    output_table.parent.mkdir(parents=True, exist_ok=True)
    output_table.write_text(tex, encoding="utf-8")
    print(f"κ inter-modelo = {k:.3f}; concordância {agree}/{n}; → {output_table}")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output-table", type=Path, required=True)
    a = p.parse_args(argv)
    run(a.input, a.output_table)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
