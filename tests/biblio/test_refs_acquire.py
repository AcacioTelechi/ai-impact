from scripts.biblio.refs_acquire import build_paper_refs


def test_prefers_wos_then_openalex():
    paper_dois = ["10.1/a", "10.2/b"]
    wos_map = {"10.1/a": ["10.9/x", "10.9/y"]}

    def oa_fetch(doi):
        assert doi == "10.2/b"      # só o que não está na WoS
        return ["W1", "W2"]

    def oa_resolve(ids):
        return {"W1": "10.9/x", "W2": "10.7/z"}

    rows, stats = build_paper_refs(paper_dois, wos_map, oa_fetch, oa_resolve)
    assert ("10.1/a", "10.9/x", "wos") in rows
    assert ("10.2/b", "10.9/x", "openalex") in rows
    assert ("10.2/b", "10.7/z", "openalex") in rows
    assert stats["papers_wos"] == 1
    assert stats["papers_openalex"] == 1


def test_counts_papers_without_refs():
    def oa_fetch(doi):
        return []

    def oa_resolve(ids):
        return {}

    rows, stats = build_paper_refs(["10.3/c"], {}, oa_fetch, oa_resolve)
    assert rows == []
    assert stats["papers_sem_refs"] == 1


def test_openalex_fetch_error_tolerated():
    def oa_fetch(doi):
        raise RuntimeError("404 not found")

    def oa_resolve(ids):
        return {}

    rows, stats = build_paper_refs(["10.5/d"], {}, oa_fetch, oa_resolve)
    assert rows == []
    assert stats["papers_oa_erro"] == 1
    assert stats["papers_sem_refs"] == 1
