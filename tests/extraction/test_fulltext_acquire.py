# tests/extraction/test_fulltext_acquire.py
from pathlib import Path

import pandas as pd

import numpy as np

from scripts.extraction.fulltext_acquire import assign_ids, download_pdf, MAX_PDF_BYTES, resolve
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


def test_download_pdf_ok_atomic(tmp_path: Path):
    dest = tmp_path / "s-001.pdf"
    status = download_pdf("http://x/p.pdf", dest, get_fn=lambda u: b"%PDF-1.4 ok")
    assert status == "ok"
    assert dest.exists() and dest.read_bytes() == b"%PDF-1.4 ok"
    assert not (tmp_path / "s-001.pdf.part").exists()


def test_download_pdf_failure_leaves_nothing(tmp_path: Path):
    dest = tmp_path / "s-002.pdf"
    status = download_pdf("http://x/p.pdf", dest, get_fn=lambda u: None)
    assert status == "download_falhou"
    assert not dest.exists()
    assert not (tmp_path / "s-002.pdf.part").exists()


def test_download_pdf_oversized_rejected(tmp_path: Path):
    dest = tmp_path / "s-003.pdf"
    big = b"x" * (MAX_PDF_BYTES + 1)
    status = download_pdf("http://x/big.pdf", dest, get_fn=lambda u: big)
    assert status == "oversized"
    assert not dest.exists()
    assert not (tmp_path / "s-003.pdf.part").exists()


def test_http_get_bytes_retries_5xx_not_4xx(monkeypatch):
    import scripts.extraction.fulltext_acquire as fa
    import requests

    # Patch sleep on the Retrying object directly so retries don't actually wait
    monkeypatch.setattr(fa._http_get_bytes.retry, "sleep", lambda *_: None)

    class _Resp:
        def __init__(self, code, content=b""):
            self.status_code = code
            self.content = content
        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.HTTPError(f"{self.status_code}")

    import pytest

    # 5xx: must retry (tenacity stop_after_attempt(3)) and eventually raise HTTPError
    calls = {"n": 0}
    def get_503(url, timeout=0):
        calls["n"] += 1
        return _Resp(503)
    monkeypatch.setattr(fa.requests, "get", get_503)
    with pytest.raises(requests.HTTPError):
        fa._http_get_bytes("http://x/p.pdf")
    assert calls["n"] >= 2  # tenacity retried (stop_after_attempt(3))

    # 404: must NOT retry, return None in exactly 1 call
    calls2 = {"n": 0}
    def get_404(url, timeout=0):
        calls2["n"] += 1
        return _Resp(404)
    monkeypatch.setattr(fa.requests, "get", get_404)
    assert fa._http_get_bytes("http://x/p.pdf") is None
    assert calls2["n"] == 1  # no retry on 4xx


def _dirs(tmp_path):
    m = tmp_path / "manual"; o = tmp_path / "oa"
    m.mkdir(); o.mkdir()
    return m, o


def test_resolve_manual_has_priority(tmp_path):
    m, o = _dirs(tmp_path)
    (m / "s-001.pdf").write_bytes(b"%PDF inst")
    row = pd.Series(_row("10.1/x", "X"))
    r = resolve(row, "s-001", m, o, email="e@e",
                lookup_fn=lambda doi, email: {"pdf_url": "http://x/p.pdf"},
                download_fn=lambda u, d: "ok")
    assert r["text_source"] == "pdf" and r["fonte"] == "manual"
    assert r["status"] == "ok_manual"
    assert r["pdf_path"].endswith("manual/s-001.pdf")


def test_resolve_no_doi(tmp_path):
    m, o = _dirs(tmp_path)
    row = pd.Series(_row("", "X"))
    r = resolve(row, "s-002", m, o, email="e@e",
                lookup_fn=lambda doi, email: None, download_fn=lambda u, d: "ok")
    assert r["text_source"] == "abstract" and r["status"] == "sem_doi"
    assert r["fonte"] == "—" and r["pdf_path"] == ""


def test_resolve_not_oa(tmp_path):
    m, o = _dirs(tmp_path)
    row = pd.Series(_row("10.1/x", "X"))
    r = resolve(row, "s-003", m, o, email="e@e",
                lookup_fn=lambda doi, email: None, download_fn=lambda u, d: "ok")
    assert r["text_source"] == "abstract" and r["status"] == "nao_oa"


def test_resolve_oa_download_ok(tmp_path):
    m, o = _dirs(tmp_path)
    row = pd.Series(_row("10.1/x", "X"))

    def fake_dl(url, dest):
        Path(dest).write_bytes(b"%PDF oa")
        return "ok"

    r = resolve(row, "s-004", m, o, email="e@e",
                lookup_fn=lambda doi, email: {"pdf_url": "http://x/p.pdf"},
                download_fn=fake_dl)
    assert r["text_source"] == "pdf" and r["fonte"] == "unpaywall"
    assert r["status"] == "ok_oa" and r["pdf_path"].endswith("oa/s-004.pdf")


def test_resolve_oa_download_failure(tmp_path):
    m, o = _dirs(tmp_path)
    row = pd.Series(_row("10.1/x", "X"))
    r = resolve(row, "s-005", m, o, email="e@e",
                lookup_fn=lambda doi, email: {"pdf_url": "u"},
                download_fn=lambda u, d: "download_falhou")
    assert r["text_source"] == "abstract" and r["status"] == "download_falhou"


def test_resolve_oa_oversized(tmp_path):
    m, o = _dirs(tmp_path)
    row = pd.Series(_row("10.1/x", "X"))
    r = resolve(row, "s-006", m, o, email="e@e",
                lookup_fn=lambda doi, email: {"pdf_url": "u"},
                download_fn=lambda u, d: "oversized")
    assert r["text_source"] == "abstract" and r["status"] == "oversized"


def test_resolve_idempotent_existing_oa(tmp_path):
    m, o = _dirs(tmp_path)
    (o / "s-007.pdf").write_bytes(b"%PDF cached")
    row = pd.Series(_row("10.1/x", "X"))
    calls = {"n": 0}

    def dl(u, d):
        calls["n"] += 1
        return "ok"

    r = resolve(row, "s-007", m, o, email="e@e",
                lookup_fn=lambda doi, email: {"pdf_url": "u"}, download_fn=dl)
    assert r["status"] == "ok_oa" and r["fonte"] == "unpaywall"
    assert calls["n"] == 0  # já em disco → não re-baixa


def test_resolve_nan_doi_routes_to_sem_doi(tmp_path):
    m, o = _dirs(tmp_path)
    row = pd.Series({**_row("X", "T"), "doi": np.nan})  # doi NaN (default read_csv)
    calls = {"n": 0}
    def lk(doi, email):
        calls["n"] += 1
        return {"pdf_url": "u"}
    r = resolve(row, "s-009", m, o, email="e@e", lookup_fn=lk,
                download_fn=lambda u, d: "ok")
    assert r["status"] == "sem_doi" and r["text_source"] == "abstract"
    assert calls["n"] == 0  # NaN doi NÃO dispara Unpaywall


from scripts.extraction import fulltext_acquire


def test_run_writes_manifest_and_coverage(tmp_path, capsys):
    src = tmp_path / "03_incluidos_final.csv"
    pd.DataFrame([
        _row("10.1/a", "A"), _row("10.1/b", "B"), _row("", "C"),
    ]).to_csv(src, index=False)
    m, o = _dirs(tmp_path)
    manifest = tmp_path / "04_fulltext_manifest.csv"

    def lookup(doi, email):
        return {"pdf_url": "u"} if doi == "10.1/a" else None

    def dl(url, dest):
        Path(dest).write_bytes(b"%PDF")
        return "ok"

    fulltext_acquire.run(input=src, manifest=manifest, email="e@e",
                         manual_dir=m, oa_dir=o, lookup_fn=lookup, download_fn=dl)
    mf = pd.read_csv(manifest, keep_default_na=False)
    assert len(mf) == 3
    assert set(mf.columns) == {"id", "review_id", "doi", "title",
                               "text_source", "fonte", "pdf_path", "status"}
    assert (mf["id"].str.match(r"s-\d{3}")).all()
    assert (mf["text_source"] == "pdf").sum() == 1
    assert (mf["text_source"] == "abstract").sum() == 2
    out = capsys.readouterr().out
    assert "Aquisição:" in out and "de 3" in out


def test_run_idempotent_and_incorporates_dropin(tmp_path, capsys):
    src = tmp_path / "c.csv"
    pd.DataFrame([_row("10.1/a", "A")]).to_csv(src, index=False)
    m, o = _dirs(tmp_path)
    manifest = tmp_path / "mf.csv"
    calls = {"n": 0}

    def lookup(doi, email):
        return None  # sem OA

    def dl(url, dest):
        calls["n"] += 1
        return "ok"

    fulltext_acquire.run(input=src, manifest=manifest, email="e@e",
                         manual_dir=m, oa_dir=o, lookup_fn=lookup, download_fn=dl)
    mf1 = pd.read_csv(manifest, keep_default_na=False)
    sid = mf1.iloc[0]["id"]
    assert mf1.iloc[0]["text_source"] == "abstract"
    (m / f"{sid}.pdf").write_bytes(b"%PDF inst")
    fulltext_acquire.run(input=src, manifest=manifest, email="e@e",
                         manual_dir=m, oa_dir=o, lookup_fn=lookup, download_fn=dl)
    mf2 = pd.read_csv(manifest, keep_default_na=False)
    assert mf2.iloc[0]["text_source"] == "pdf"
    assert mf2.iloc[0]["fonte"] == "manual"
    assert calls["n"] == 0
