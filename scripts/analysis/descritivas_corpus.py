"""Pipeline step (analysis): generate descriptive figures of the corpus."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

matplotlib.use("Agg")  # headless


def _fig_anos(df: pd.DataFrame, output: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    counts = df["ano"].value_counts().sort_index()
    ax.bar(counts.index, counts.values, color="steelblue")
    ax.set_xlabel("Ano de publicação")
    ax.set_ylabel("Número de estudos")
    ax.set_title("Distribuição do corpus por ano")
    fig.tight_layout()
    fig.savefig(output, format="pdf")
    plt.close(fig)


def _fig_janelas(df: pd.DataFrame, output: Path) -> None:
    fig, ax = plt.subplots(figsize=(6, 4))
    counts = df["janela"].value_counts().reindex(["2013-2017", "2018-2022", "2022-2025"]).fillna(0)
    ax.bar(counts.index, counts.values, color=["#cccccc", "#888888", "#444444"])
    ax.set_ylabel("Número de estudos")
    ax.set_title("Corpus por janela temporal")
    fig.tight_layout()
    fig.savefig(output, format="pdf")
    plt.close(fig)


def _fig_tipo_estudo(df: pd.DataFrame, output: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 4))
    counts = df["tipo_estudo"].value_counts()
    ax.barh(counts.index, counts.values, color="seagreen")
    ax.set_xlabel("Número de estudos")
    ax.set_title("Tipos de estudo no corpus")
    fig.tight_layout()
    fig.savefig(output, format="pdf")
    plt.close(fig)


def run(input: Path, output_dir: Path) -> None:
    df = pd.read_csv(input, encoding="utf-8")
    output_dir.mkdir(parents=True, exist_ok=True)
    _fig_anos(df, output_dir / "corpus_anos.pdf")
    _fig_janelas(df, output_dir / "corpus_janelas.pdf")
    _fig_tipo_estudo(df, output_dir / "corpus_tipo_estudo.pdf")
    print(f"Wrote 3 figures to {output_dir}")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args(argv)
    run(args.input, args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
