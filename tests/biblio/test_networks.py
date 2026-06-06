from scripts.biblio.networks import build_coupling, build_cocitation


PR = {
    "p1": {"a", "b", "c"},
    "p2": {"a", "b", "d"},      # compartilha a,b com p1 (2)
    "p3": {"a"},                # compartilha só a com p1/p2 (1)
}


def test_coupling_edge_weight_and_filter():
    G = build_coupling(PR, min_shared=2)
    assert G.has_edge("p1", "p2")
    assert G["p1"]["p2"]["weight"] == 2
    assert not G.has_edge("p1", "p3")   # só 1 compartilhada, filtrada
    assert abs(G["p1"]["p2"]["cosine"] - 2 / (3 ** 0.5 * 3 ** 0.5)) < 1e-9


def test_cocitation_threshold_and_weight():
    # 'a' citada por p1,p2,p3 (3); 'b' por p1,p2 (2)
    G = build_cocitation(PR, k=3, top_n=300)
    assert "a" in G.nodes          # citada por >=3
    assert "b" not in G.nodes      # citada por 2 < k
    # com k=2: a&b co-citadas por p1,p2 → weight 2
    G2 = build_cocitation(PR, k=2, top_n=300)
    assert G2["a"]["b"]["weight"] == 2
