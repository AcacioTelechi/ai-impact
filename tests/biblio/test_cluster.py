import networkx as nx
import pandas as pd
from scripts.biblio.cluster import louvain_clusters, top_terms, crosstab


def test_louvain_two_cliques():
    G = nx.Graph()
    nx.add_path(G, ["a", "b", "c", "a"])      # triângulo 1
    nx.add_path(G, ["x", "y", "z", "x"])      # triângulo 2
    part = louvain_clusters(G, seed=1)
    assert part["a"] == part["b"] == part["c"]
    assert part["x"] == part["y"] == part["z"]
    assert part["a"] != part["x"]


def test_top_terms_picks_distinctive():
    titles = ["automation labor markets", "labor automation wages",
              "automation and tasks"]
    terms = top_terms(titles, n=3)
    assert "automation" in terms


def test_crosstab_counts():
    node_cluster = {"10.1/a": 0, "10.2/b": 0, "10.3/c": 1}
    df = pd.DataFrame(
        {"paper_doi": ["10.1/a", "10.2/b", "10.3/c"],
         "pre_pos_chatgpt": ["pre", "pos", "pos"]}
    ).set_index("paper_doi")
    ct = crosstab(node_cluster, df, "pre_pos_chatgpt")
    assert ct.loc[0, "pre"] == 1
    assert ct.loc[0, "pos"] == 1
    assert ct.loc[1, "pos"] == 1
