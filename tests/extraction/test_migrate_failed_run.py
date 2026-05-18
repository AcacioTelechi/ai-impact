import json
import types

import pandas as pd

from scripts.extraction import migrate_failed_run as M


def _fake_client(entries):
    def mk(cid, kind, msg=""):
        r = types.SimpleNamespace()
        r.custom_id = cid
        if kind == "succeeded":
            r.result = types.SimpleNamespace(type="succeeded")
        else:
            inner = types.SimpleNamespace(message=msg)
            r.result = types.SimpleNamespace(
                type="errored",
                error=types.SimpleNamespace(error=inner))
        return r

    class C:
        class messages:
            class batches:
                @staticmethod
                def results(_bid):
                    return [mk(*e) for e in entries]
    return C()


def _setup(tmp_path):
    cache = {"rCRED": {"x": 1}, "rPDFBAD": {"x": 2},
             "rOK": {"x": 3}, "rGENUINO": {"x": 4}}
    cp = tmp_path / "cache.json"
    cp.write_text(json.dumps(cache), encoding="utf-8")
    man = pd.DataFrame([
        {"id": "s-1", "review_id": "rCRED", "doi": "d1", "title": "t1",
         "text_source": "abstract", "fonte": "—", "pdf_path": "",
         "status": "nao_oa"},
        {"id": "s-2", "review_id": "rPDFBAD", "doi": "d2", "title": "t2",
         "text_source": "pdf", "fonte": "oa", "pdf_path": "/x.pdf",
         "status": "oa"},
        {"id": "s-3", "review_id": "rOK", "doi": "d3", "title": "t3",
         "text_source": "pdf", "fonte": "oa", "pdf_path": "/y.pdf",
         "status": "oa"},
    ])
    mp = tmp_path / "man.csv"
    man.to_csv(mp, index=False)
    return cp, mp


def test_classify():
    assert M.classify("Your credit balance is too low") == "credito"
    assert M.classify("The PDF specified is password protected.") == "pdf_protegido"
    assert M.classify("The PDF specified was not valid.") == "pdf_invalido"
    assert M.classify("weird") == "outro"


def test_dry_run_nao_altera(tmp_path):
    cp, mp = _setup(tmp_path)
    before_c = cp.read_text(); before_m = mp.read_text()
    cli = _fake_client([
        ("rCRED", "errored", "Your credit balance is too low"),
        ("rPDFBAD", "errored", "The PDF specified was not valid."),
        ("rGENUINO", "succeeded"),
    ])
    rep = M.run(cli, "b", cp, mp, dry_run=True)
    assert cp.read_text() == before_c
    assert mp.read_text() == before_m
    assert rep["cache_removed"] == 2
    assert rep["manifest_changed"] == 1
    assert rep["pdf_before"] == 2 and rep["pdf_after"] == 1


def test_apply_e_idempotente(tmp_path):
    cp, mp = _setup(tmp_path)
    entries = [
        ("rCRED", "errored", "Your credit balance is too low"),
        ("rPDFBAD", "errored", "The PDF specified was not valid."),
        ("rGENUINO", "succeeded"),
    ]
    M.run(_fake_client(entries), "b", cp, mp, dry_run=False)
    cache = json.loads(cp.read_text())
    assert "rCRED" not in cache and "rPDFBAD" not in cache
    assert "rOK" in cache and "rGENUINO" in cache
    man = pd.read_csv(mp, keep_default_na=False)
    row = man[man["review_id"] == "rPDFBAD"].iloc[0]
    assert row["text_source"] == "abstract" and row["status"] == "pdf_invalido"
    rep2 = M.run(_fake_client(entries), "b", cp, mp, dry_run=False)
    assert rep2["cache_removed"] == 0 and rep2["manifest_changed"] == 0
