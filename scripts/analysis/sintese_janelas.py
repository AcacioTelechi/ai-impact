"""Cap 05 — síntese por janela temporal (Plano 5).

Figura: % de estudos invocando cada mecanismo Acemoglu-Restrepo nas 3 janelas.
Tabela: tecnologia dominante, tipo modal, sinal/polarização predominantes e
% de cada mecanismo, por janela.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from scripts.analysis.corpus import load_corpus  # noqa: E402
from scripts.analysis.stats import _classificados  # noqa: E402
from scripts.analysis.texkit import (  # noqa: E402
    CANON,
    MECANISMOS,
    escape,
    fmt_pct,
    tabela_booktabs,
)

JANELAS = CANON["janela"]


def _pct_mec_por_janela(df: pd.DataFrame, mec: str) -> dict[str, float]:
    out = {}
    for jan in JANELAS:
        sub = _classificados(df[df["janela"] == jan][mec])
        n = len(sub)
        out[jan] = (int((sub.str.lower() == "sim").sum()) / n) if n else 0.0
    return out


def _modal(df: pd.DataFrame, jan: str, col: str) -> str:
    classif = _classificados(df[df["janela"] == jan][col])
    if classif.empty:
        return "—"
    return str(classif.value_counts().idxmax())


def _fig_mecanismos(df: pd.DataFrame, output: Path) -> None:
    import numpy as np

    x = np.arange(len(JANELAS))
    largura = 0.2
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for i, (mec, rotulo) in enumerate(MECANISMOS.items()):
        pcts = [_pct_mec_por_janela(df, mec)[j] * 100 for j in JANELAS]
        ax.bar(x + (i - 1.5) * largura, pcts, largura, label=rotulo)
    ax.set_xticks(x)
    ax.set_xticklabels(JANELAS)
    ax.set_ylabel("% dos estudos da janela")
    ax.set_title("Mecanismos teóricos invocados por janela")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(output, format="pdf")
    plt.close(fig)


def _tabela(df: pd.DataFrame) -> str:
    n_por_jan = {j: int((df["janela"] == j).sum()) for j in JANELAS}
    header = ["Dimensão"] + [f"{j} (n={n_por_jan[j]})" for j in JANELAS]
    rows: list[list[str]] = []
    rows.append(["Tecnologia dominante"] + [escape(_modal(df, j, "tecnologia_focada")) for j in JANELAS])
    rows.append(["Tipo de estudo modal"] + [escape(_modal(df, j, "tipo_estudo")) for j in JANELAS])
    rows.append(["Sinal predominante"] + [escape(_modal(df, j, "sinal_efeito")) for j in JANELAS])
    rows.append(["Polarização predominante"] + [escape(_modal(df, j, "polarizacao")) for j in JANELAS])
    for mec, rotulo in MECANISMOS.items():
        pj = _pct_mec_por_janela(df, mec)
        rows.append([f"% {rotulo}"] + [fmt_pct(pj[j]) for j in JANELAS])
    return tabela_booktabs(
        "l" + "c" * len(JANELAS),
        header,
        rows,
        notas=["Proporções de mecanismo sobre os estudos que classificaram a dimensão (n/a fora)."],
    )


def run(input: Path, output_table: Path, output_fig: Path) -> None:
    df = load_corpus(input).df
    output_table.parent.mkdir(parents=True, exist_ok=True)
    output_fig.parent.mkdir(parents=True, exist_ok=True)
    _fig_mecanismos(df, output_fig)
    output_table.write_text(_tabela(df), encoding="utf-8")
    print(f"Cap 05: tabela {output_table} + figura {output_fig}")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output-table", type=Path, required=True)
    p.add_argument("--output-fig", type=Path, required=True)
    args = p.parse_args(argv)
    run(args.input, args.output_table, args.output_fig)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
