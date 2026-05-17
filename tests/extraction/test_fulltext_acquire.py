# tests/extraction/test_fulltext_acquire.py
import pandas as pd

from scripts.extraction.fulltext_acquire import assign_ids
from scripts.screening.llm.batch_client import cache_key, custom_id


def _row(doi, title, year=2020):
    return {"source": "wos", "doi": doi, "title": title, "authors": "A, B",
            "year": year, "abstract": "abs", "venue": "V", "language": "en"}


def test_assign_ids_deterministic_and_stable_under_reorder():
    df1 = pd.DataFrame([_row("10.1/c", "C"), _row("10.1/a", "A"), _row("10.1/b", "B")])
    df2 = df1.iloc[::-1].reset_index(drop=True)  # ordem invertida
    a1 = assign_ids(df1)
    a2 = assign_ids(df2)
    m1 = dict(zip(a1["doi"], a1["id"]))
    m2 = dict(zip(a2["doi"], a2["id"]))
    assert m1 == m2
    assert sorted(a1["id"]) == ["s-001", "s-002", "s-003"]
    assert a1["id"].is_unique
    r0 = a1.iloc[0]
    assert r0["review_id"] == custom_id(cache_key(r0))


def test_assign_ids_width_scales_to_corpus():
    df = pd.DataFrame([_row(f"10.1/{i}", f"T{i}") for i in range(12)])
    a = assign_ids(df)
    assert set(a["id"]) == {f"s-{i:03d}" for i in range(1, 13)}
