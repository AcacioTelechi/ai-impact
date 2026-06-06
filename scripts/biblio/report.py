"""Saídas exploratórias da linha bibliométrica (Plano 6) em reports/biblio/.

Lê os GraphML gerados, clusteriza, e produz: figura de cada rede (cor=cluster),
perfis de cluster (.csv) e um RESUMO.md. Para o acoplamento, cruza clusters com
pré/pós e polarização (join no 06_extraction.csv). Não unit-testado (I/O visual).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
import networkx as nx
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from scripts.biblio.cluster import crosstab, louvain_clusters, top_terms  # noqa: E402
from scripts.biblio.dois import norm_doi  # noqa: E402


def _draw(G: nx.Graph, part: dict, title: str, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 7))
    if G.number_of_nodes():
        pos = nx.spring_layout(G, weight="weight", seed=42)
        colors = [part.get(n, 0) for n in G.nodes]
        nx.draw_networkx_nodes(G, pos, node_size=40, node_color=colors,
                               cmap="tab20", ax=ax)
        nx.draw_networkx_edges(G, pos, alpha=0.15, ax=ax)
    ax.set_title(title)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)


def _corpus_indexed(extraction: Path) -> pd.DataFrame:
    df = pd.read_csv(extraction, encoding="utf-8", dtype=str).fillna("")
    df = df[df["elegivel"] == "incluir"].copy()
    df["paper_doi"] = [norm_doi(d) for d in df["doi"]]
    return df[df["paper_doi"] != ""].set_index("paper_doi")


def _coupling_report(graphml: Path, corpus: pd.DataFrame, out_dir: Path) -> str:
    G = nx.read_graphml(graphml)
    part = louvain_clusters(G)
    n_clusters = len(set(part.values()))
    rows = []
    for cl in sorted(set(part.values())):
        members = [n for n, c in part.items() if c == cl]
        titles = [corpus.loc[n, "titulo"] for n in members if n in corpus.index]
        rows.append({"cluster": cl, "n_papers": len(members),
                     "termos": ", ".join(top_terms(titles, 8))})
    pd.DataFrame(rows).to_csv(out_dir / "clusters_acoplamento.csv", index=False)
    _draw(G, part, "Acoplamento bibliográfico (cor = cluster)",
          out_dir / "coupling.png")
    lines = [f"## Acoplamento: {n_clusters} clusters, {G.number_of_nodes()} papers\n"]
    for col in ("pre_pos_chatgpt", "polarizacao"):
        if col in corpus.columns:
            ct = crosstab(part, corpus, col)
            lines.append(f"\n### cluster × {col}\n\n```\n{ct.to_string()}\n```\n")
    return "\n".join(lines)


def _cocitation_report(graphml: Path, out_dir: Path) -> str:
    G = nx.read_graphml(graphml)
    part = louvain_clusters(G)
    n_clusters = len(set(part.values()))
    wdeg = dict(G.degree(weight="weight"))
    rows = []
    for cl in sorted(set(part.values())):
        members = sorted([n for n, c in part.items() if c == cl],
                         key=lambda n: wdeg.get(n, 0), reverse=True)
        rows.append({"cluster": cl, "n_refs": len(members),
                     "refs_centrais": ", ".join(members[:5])})
    pd.DataFrame(rows).to_csv(out_dir / "clusters_cocitacao.csv", index=False)
    _draw(G, part, "Co-citação da base intelectual (cor = cluster)",
          out_dir / "cocitation.png")
    return f"## Co-citação: {n_clusters} clusters, {G.number_of_nodes()} refs\n"


def run(net_dir: Path, extraction: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    corpus = _corpus_indexed(extraction)
    md = ["# Plano 6 — Resumo exploratório (acoplamento + co-citação)\n",
          "> Exploratório/descritivo; cobertura híbrida WoS+OpenAlex; refs sem DOI fora.\n"]
    md.append(_coupling_report(net_dir / "coupling.graphml", corpus, out_dir))
    md.append(_cocitation_report(net_dir / "cocitation.graphml", out_dir))
    (out_dir / "RESUMO.md").write_text("\n".join(md), encoding="utf-8")
    print(f"Relatório: {out_dir}/RESUMO.md + figuras + clusters_*.csv")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--net-dir", type=Path, required=True)
    p.add_argument("--extraction", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    a = p.parse_args(argv)
    run(a.net_dir, a.extraction, a.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
