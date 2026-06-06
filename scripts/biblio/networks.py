"""Construção das redes bibliométricas (Plano 6).

A partir do par paper_doi→ref_doi (08_paper_refs.csv): acoplamento
bibliográfico (nós = papers, peso = refs compartilhadas) e co-citação (nós =
refs citadas por >=k papers, peso = co-ocorrência em listas de referência).
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from itertools import combinations
from math import sqrt
from pathlib import Path

import networkx as nx
import pandas as pd


def load_paper_refs(csv: Path) -> dict[str, set[str]]:
    df = pd.read_csv(csv, encoding="utf-8", dtype=str).fillna("")
    out: dict[str, set[str]] = defaultdict(set)
    for paper, ref in zip(df["paper_doi"], df["ref_doi"]):
        if paper and ref:
            out[paper].add(ref)
    return dict(out)


def build_coupling(paper_refs, min_shared: int = 2) -> nx.Graph:
    # índice ref → papers que a citam; pares de papers que compartilham ref
    ref_to_papers: dict[str, list[str]] = defaultdict(list)
    for paper, refs in paper_refs.items():
        for r in refs:
            ref_to_papers[r].append(paper)
    shared: dict[tuple[str, str], int] = defaultdict(int)
    for papers in ref_to_papers.values():
        for u, v in combinations(sorted(set(papers)), 2):
            shared[(u, v)] += 1
    G = nx.Graph()
    G.add_nodes_from(paper_refs.keys())
    for (u, v), w in shared.items():
        if w >= min_shared:
            cos = w / sqrt(len(paper_refs[u]) * len(paper_refs[v]))
            G.add_edge(u, v, weight=w, cosine=cos)
    return G


def build_cocitation(paper_refs, k: int = 3, top_n: int = 300) -> nx.Graph:
    ref_count: dict[str, int] = defaultdict(int)
    for refs in paper_refs.values():
        for r in refs:
            ref_count[r] += 1
    keep = {r for r, c in ref_count.items() if c >= k}
    co: dict[tuple[str, str], int] = defaultdict(int)
    for refs in paper_refs.values():
        kept = sorted(refs & keep)
        for a, b in combinations(kept, 2):
            co[(a, b)] += 1
    G = nx.Graph()
    G.add_nodes_from(keep)
    for (a, b), w in co.items():
        G.add_edge(a, b, weight=w)
    if G.number_of_nodes() > top_n:
        wdeg = dict(G.degree(weight="weight"))
        top = sorted(wdeg, key=wdeg.get, reverse=True)[:top_n]
        G = G.subgraph(top).copy()
    return G


def run(refs_csv: Path, out_dir: Path, k: int, top_n: int, min_shared: int) -> None:
    paper_refs = load_paper_refs(refs_csv)
    out_dir.mkdir(parents=True, exist_ok=True)
    Gc = build_coupling(paper_refs, min_shared=min_shared)
    Gx = build_cocitation(paper_refs, k=k, top_n=top_n)
    nx.write_graphml(Gc, out_dir / "coupling.graphml")
    nx.write_graphml(Gx, out_dir / "cocitation.graphml")
    print(f"Acoplamento: {Gc.number_of_nodes()} nós, {Gc.number_of_edges()} arestas")
    print(f"Co-citação:  {Gx.number_of_nodes()} nós, {Gx.number_of_edges()} arestas")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--refs", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--k", type=int, default=3)
    p.add_argument("--top-n", type=int, default=300)
    p.add_argument("--min-shared", type=int, default=2)
    a = p.parse_args(argv)
    run(a.refs, a.out_dir, a.k, a.top_n, a.min_shared)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
