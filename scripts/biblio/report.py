"""Saídas exploratórias da linha bibliométrica (Plano 6) em reports/biblio/.

Em vez de "hairballs" ilegíveis, gera gráficos-resumo: para o acoplamento,
barras empilhadas cluster × pré/pós e cluster × polarização (só clusters
substantivos, rotulados por termos-título); para a co-citação, as top
referências de cada cluster rotuladas por autor-ano (das strings WoS). Os
.graphml (produzidos por networks.py) seguem disponíveis para o Gephi.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import matplotlib
import networkx as nx
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from scripts.biblio.cluster import crosstab, louvain_clusters, top_terms  # noqa: E402
from scripts.biblio.dois import norm_doi  # noqa: E402
from scripts.biblio.wos_refs import parse_wos_ref_labels  # noqa: E402

_POLAR_ORDER = ["baixa-quali em risco", "ambos", "alta-quali em risco", "neutro"]
_PREPOS_ORDER = ["pre", "pos"]


def substantive(part: dict, min_size: int = 10) -> list[int]:
    sizes = Counter(part.values())
    return sorted([c for c, n in sizes.items() if n >= min_size])


def _corpus_indexed(extraction: Path) -> pd.DataFrame:
    df = pd.read_csv(extraction, encoding="utf-8", dtype=str).fillna("")
    df = df[df["elegivel"] == "incluir"].copy()
    df["paper_doi"] = [norm_doi(d) for d in df["doi"]]
    return df[df["paper_doi"] != ""].set_index("paper_doi")


def _cluster_labels(part: dict, corpus: pd.DataFrame, clusters: list[int]) -> dict:
    labels = {}
    for cl in clusters:
        members = [n for n, c in part.items() if c == cl]
        titles = [corpus.loc[n, "titulo"] for n in members if n in corpus.index]
        labels[cl] = f"C{cl} ({len(members)}): " + ", ".join(top_terms(titles, 3))
    return labels


def _stacked_barh(ct: pd.DataFrame, row_labels: dict, order, title: str,
                  out: Path) -> None:
    cols = [c for c in order if c in ct.columns] + \
           [c for c in ct.columns if c not in order]
    ct = ct.reindex(columns=cols).fillna(0)
    fig, ax = plt.subplots(figsize=(10, max(3, 0.7 * len(ct) + 1.5)))
    left = [0.0] * len(ct)
    ys = range(len(ct))
    for col in ct.columns:
        vals = ct[col].tolist()
        ax.barh(list(ys), vals, left=left, label=str(col))
        left = [a + b for a, b in zip(left, vals)]
    ax.set_yticks(list(ys))
    ax.set_yticklabels([row_labels.get(i, f"C{i}") for i in ct.index], fontsize=9)
    ax.set_xlabel("nº de estudos")
    ax.set_title(title)
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def _coupling_charts(graphml: Path, corpus: pd.DataFrame, out_dir: Path) -> str:
    G_full = nx.read_graphml(graphml)
    nonisolated = [n for n, d in G_full.degree() if d > 0]
    n_isolated = G_full.number_of_nodes() - len(nonisolated)
    G = G_full.subgraph(nonisolated).copy()
    part = louvain_clusters(G)
    keep = substantive(part, min_size=10)
    labels = _cluster_labels(part, corpus, keep)

    pd.DataFrame(
        [{"cluster": cl, "n_papers": sum(1 for v in part.values() if v == cl),
          "termos": ", ".join(top_terms(
              [corpus.loc[n, "titulo"] for n, c in part.items()
               if c == cl and n in corpus.index], 8))}
         for cl in sorted(set(part.values()))]
    ).to_csv(out_dir / "clusters_acoplamento.csv", index=False)

    out_lines = [f"## Acoplamento: {len(set(part.values()))} clusters em "
                 f"{G.number_of_nodes()} papers conectados "
                 f"({n_isolated} isolados omitidos); "
                 f"{len(keep)} clusters substantivos (n>=10)\n"]
    for col, order, fname, titulo in (
        ("pre_pos_chatgpt", _PREPOS_ORDER, "coupling_prepos.png",
         "Acoplamento: clusters × período (pré/pós-ChatGPT)"),
        ("polarizacao", _POLAR_ORDER, "coupling_polarizacao.png",
         "Acoplamento: clusters × polarização"),
    ):
        if col not in corpus.columns:
            continue
        ct = crosstab(part, corpus, col)
        ct = ct.reindex(index=keep).fillna(0)
        _stacked_barh(ct, labels, order, titulo, out_dir / fname)
        out_lines.append(f"\n### cluster × {col}  →  `{fname}`\n\n"
                         f"```\n{ct.to_string()}\n```\n")
    return "\n".join(out_lines)


def _cocitation_charts(graphml: Path, ref_labels: dict, out_dir: Path,
                       per_cluster: int = 8) -> str:
    G = nx.read_graphml(graphml)
    part = louvain_clusters(G)
    clusters = sorted(set(part.values()))
    wdeg = dict(G.degree(weight="weight"))

    rows = []
    for cl in clusters:
        members = sorted([n for n, c in part.items() if c == cl],
                         key=lambda n: wdeg.get(n, 0), reverse=True)
        rows.append({"cluster": cl, "n_refs": len(members),
                     "refs_centrais": ", ".join(
                         f"{ref_labels.get(m, m)}" for m in members[:5])})
    pd.DataFrame(rows).to_csv(out_dir / "clusters_cocitacao.csv", index=False)

    fig, axes = plt.subplots(len(clusters), 1,
                             figsize=(10, 2.4 * len(clusters)))
    if len(clusters) == 1:
        axes = [axes]
    for ax, cl in zip(axes, clusters):
        members = sorted([n for n, c in part.items() if c == cl],
                         key=lambda n: wdeg.get(n, 0), reverse=True)[:per_cluster]
        vals = [wdeg.get(n, 0) for n in members][::-1]
        labs = [ref_labels.get(n, n) for n in members][::-1]
        ax.barh(range(len(members)), vals, color=f"C{cl % 10}")
        ax.set_yticks(range(len(members)))
        ax.set_yticklabels(labs, fontsize=8)
        ax.set_title(f"Co-citação — cluster {cl} (top refs por grau ponderado)",
                     fontsize=9)
    fig.tight_layout()
    fig.savefig(out_dir / "cocitation_top_refs.png", dpi=150)
    plt.close(fig)
    return (f"## Co-citação: {len(clusters)} clusters, {G.number_of_nodes()} "
            f"refs  →  `cocitation_top_refs.png`\n")


def run(net_dir: Path, extraction: Path, wos_dir: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    corpus = _corpus_indexed(extraction)
    ref_labels = parse_wos_ref_labels(sorted(Path(wos_dir).glob("*.bib")))
    md = ["# Plano 6 — Resumo exploratório (acoplamento + co-citação)\n",
          "> Exploratório/descritivo; cobertura híbrida WoS+OpenAlex; refs sem "
          "DOI fora. Figuras-resumo legíveis; redes completas em *.graphml "
          "(abrir no Gephi).\n"]
    md.append(_coupling_charts(net_dir / "coupling.graphml", corpus, out_dir))
    md.append(_cocitation_charts(net_dir / "cocitation.graphml", ref_labels, out_dir))
    (out_dir / "RESUMO.md").write_text("\n".join(md), encoding="utf-8")
    print(f"Relatório: {out_dir}/RESUMO.md + coupling_*.png + "
          f"cocitation_top_refs.png + clusters_*.csv")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--net-dir", type=Path, required=True)
    p.add_argument("--extraction", type=Path, required=True)
    p.add_argument("--wos-dir", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    a = p.parse_args(argv)
    run(a.net_dir, a.extraction, a.wos_dir, a.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
