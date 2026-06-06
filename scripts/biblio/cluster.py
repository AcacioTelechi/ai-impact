"""Clusterização (Louvain) e caracterização dos clusters (Plano 6).

Louvain nativo do networkx (ponderado, seed fixo p/ reprodutibilidade). Para o
acoplamento, cruza clusters com atributos do corpus (pré/pós, polarização etc.)
via crosstab; rótulos de cluster vêm de termos TF-IDF dos títulos.
"""
from __future__ import annotations

import networkx as nx
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer


def louvain_clusters(G: nx.Graph, seed: int = 42) -> dict:
    comms = nx.community.louvain_communities(G, weight="weight", seed=seed)
    return {node: idx for idx, comm in enumerate(comms) for node in comm}


def top_terms(titles, n: int = 8) -> list[str]:
    docs = [t for t in titles if t and t.strip()]
    if not docs:
        return []
    vec = TfidfVectorizer(stop_words="english", min_df=1, ngram_range=(1, 1))
    X = vec.fit_transform(docs)
    scores = X.mean(axis=0).A1
    terms = vec.get_feature_names_out()
    order = scores.argsort()[::-1][:n]
    return [terms[i] for i in order]


def crosstab(node_cluster: dict, df: pd.DataFrame, col: str) -> pd.DataFrame:
    clusters, vals = [], []
    for node, cl in node_cluster.items():
        if node in df.index:
            clusters.append(cl)
            vals.append(df.loc[node, col])
    return pd.crosstab(pd.Series(clusters, name="cluster"),
                       pd.Series(vals, name=col))
