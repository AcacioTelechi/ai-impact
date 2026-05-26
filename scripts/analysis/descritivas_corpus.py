"""Cap 04 — descritivas do corpus de análise (Plano 5).

4 figuras (anos, janelas, tipo de estudo, tecnologia) + 1 tabela de atributos
estruturais. Tudo sobre os incluídos-e-extraídos (corpus.load_corpus).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")  # headless — antes de pyplot
import matplotlib.pyplot as plt  # noqa: E402

from scripts.analysis.corpus import load_corpus  # noqa: E402
from scripts.analysis.texkit import CANON, escape, fmt_pct, tabela_booktabs  # noqa: E402


def _fig_anos(df: pd.DataFrame, output: Path) -> None:
    anos = pd.to_numeric(df["ano"], errors="coerce").dropna().astype(int)
    counts = anos.value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(counts.index, counts.values, color="steelblue")
    ax.set_xlabel("Ano de publicação")
    ax.set_ylabel("Número de estudos")
    ax.set_title("Distribuição do corpus por ano")
    fig.tight_layout()
    fig.savefig(output, format="pdf")
    plt.close(fig)


def _fig_categorica(df: pd.DataFrame, col: str, titulo: str, output: Path,
                    horizontal: bool = False) -> None:
    ordem = CANON.get(col, sorted(df[col].dropna().unique().tolist()))
    counts = df[col].value_counts().reindex(ordem).fillna(0)
    fig, ax = plt.subplots(figsize=(7, 4))
    if horizontal:
        ax.barh(counts.index, counts.values, color="seagreen")
        ax.set_xlabel("Número de estudos")
    else:
        ax.bar(counts.index, counts.values, color="#555555")
        ax.set_ylabel("Número de estudos")
        plt.xticks(rotation=20, ha="right")
    ax.set_title(titulo)
    fig.tight_layout()
    fig.savefig(output, format="pdf")
    plt.close(fig)


def _linha_freq(rotulo: str, n: int, total: int) -> list[str]:
    pct = (n / total) if total else 0.0
    return [escape(rotulo), str(n), fmt_pct(pct)]


def _tabela_estrutural(df: pd.DataFrame, total: int) -> str:
    rows: list[list[str]] = []
    for col in ("tipo_pub", "revisado_por_pares", "metodo_empirico"):
        vals = df[col].fillna("").astype(str).str.strip()
        for cat in CANON[col]:
            n = int((vals == cat).sum())
            if n:
                rows.append(_linha_freq(f"{col}: {cat}", n, total))
        n_na = int((vals == "").sum())
        if n_na:
            rows.append(_linha_freq(f"{col}: (não especificado)", n_na, total))
    top_pais = df["pais_estudo"].fillna("").astype(str).str.strip()
    top_pais = top_pais[top_pais != ""].value_counts().head(5)
    for pais, n in top_pais.items():
        rows.append(_linha_freq(f"país: {pais}", int(n), total))
    return tabela_booktabs(
        "lrr",
        ["Atributo", "n", r"\%"],
        rows,
        notas=[f"Corpus de análise: N={total} estudos incluídos e extraídos. "
               "Percentuais sobre N."],
    )


def run(input: Path, output_dir: Path, output_table: Path) -> None:
    corpus = load_corpus(input)
    df = corpus.df
    output_dir.mkdir(parents=True, exist_ok=True)
    output_table.parent.mkdir(parents=True, exist_ok=True)
    _fig_anos(df, output_dir / "corpus_anos.pdf")
    _fig_categorica(df, "janela", "Corpus por janela temporal",
                    output_dir / "corpus_janelas.pdf")
    _fig_categorica(df, "tipo_estudo", "Tipos de estudo no corpus",
                    output_dir / "corpus_tipo_estudo.pdf", horizontal=True)
    _fig_categorica(df, "tecnologia_focada", "Tecnologia de IA focada",
                    output_dir / "corpus_tecnologia.pdf", horizontal=True)
    output_table.write_text(_tabela_estrutural(df, corpus.n), encoding="utf-8")
    print(f"Cap 04: 4 figuras em {output_dir} + tabela {output_table} (N={corpus.n})")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--output-table", type=Path, required=True)
    args = p.parse_args(argv)
    run(args.input, args.output_dir, args.output_table)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
