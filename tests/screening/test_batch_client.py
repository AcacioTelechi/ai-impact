import re

import pandas as pd

from scripts.screening.llm.batch_client import build_requests, cache_key, custom_id, parse_response


def test_parse_clean_json():
    r = parse_response('{"decisao":"incluir","justificativa":"ok","confianca":0.9,"criterio":null}')
    assert r["decisao"] == "incluir"
    assert r["confianca"] == 0.9
    assert r["criterio"] is None


def test_parse_strips_json_fences():
    raw = '```json\n{"decisao":"excluir","justificativa":"E1","confianca":0.8,"criterio":"E1"}\n```'
    r = parse_response(raw)
    assert r["decisao"] == "excluir"
    assert r["criterio"] == "E1"


def test_parse_extracts_object_from_surrounding_text():
    raw = 'Claro! Aqui está:\n{"decisao":"duvida","justificativa":"x","confianca":0.5,"criterio":null} Espero ajudar.'
    r = parse_response(raw)
    assert r["decisao"] == "duvida"


def test_parse_irrecoverable_returns_duvida_zero():
    r = parse_response("desculpe, não consigo responder")
    assert r["decisao"] == "duvida"
    assert r["confianca"] == 0.0
    assert r["justificativa"] == "parse_fail"
    assert r["criterio"] is None


def test_parse_invalid_decisao_value_becomes_duvida():
    r = parse_response('{"decisao":"talvez","justificativa":"x","confianca":0.7,"criterio":null}')
    assert r["decisao"] == "duvida"


def test_cache_key_prefers_doi():
    row = pd.Series({"doi": "10.1/X", "title": "T", "year": 2020})
    assert cache_key(row) == "doi:10.1/x"


def test_cache_key_falls_back_to_title_year():
    row = pd.Series({"doi": "", "title": "  AI and Jobs ", "year": 2020})
    assert cache_key(row) == "ty:ai and jobs|2020"


def test_custom_id_is_safe_and_deterministic():
    k = "doi:10.1/abc"
    a, b = custom_id(k), custom_id(k)
    assert a == b
    assert re.fullmatch(r"[A-Za-z0-9_-]{1,64}", a)


def _df():
    return pd.DataFrame([
        {"doi": "10.1/a", "title": "AI Jobs", "authors": "S, J", "year": 2020,
         "venue": "AER", "abstract": "abs a"},
        {"doi": "10.1/b", "title": "AI Wages", "authors": "B, P", "year": 2021,
         "venue": "JOLE", "abstract": "abs b"},
    ])


def test_build_requests_one_per_row_with_cached_system():
    reqs = build_requests(_df(), model="claude-sonnet-4-6")
    assert len(reqs) == 2
    r0 = reqs[0]
    assert r0["custom_id"] == custom_id(cache_key(_df().iloc[0]))
    p = r0["params"]
    assert p["model"] == "claude-sonnet-4-6"
    assert p["max_tokens"] == 400
    # system é o bloco cacheável estável (idêntico entre requests)
    assert p["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert reqs[0]["params"]["system"] == reqs[1]["params"]["system"]
    # user block carrega os dados do registro
    assert "AI Jobs" in p["messages"][0]["content"]


def test_build_requests_skips_cached_keys():
    done = {custom_id(cache_key(_df().iloc[0])): {"decisao": "incluir"}}
    reqs = build_requests(_df(), model="claude-haiku-4-5-20251001", cached=done)
    assert len(reqs) == 1
    assert "AI Wages" in reqs[0]["params"]["messages"][0]["content"]


from pathlib import Path

from scripts.screening.llm.batch_client import screen_with_model


def test_screen_with_model_mock_labels_every_row():
    df = _df()
    res = screen_with_model(df, model="claude-haiku-4-5-20251001", mock=True)
    assert len(res) == len(df)
    assert all(r["decisao"] in {"incluir", "excluir", "duvida"} for r in res)


def test_screen_with_model_uses_submit_fn_and_caches(tmp_path: Path):
    df = _df()
    calls = {"n": 0}

    def fake_submit(requests):
        calls["n"] += 1
        return {
            r["custom_id"]:
            '{"decisao":"incluir","justificativa":"ok","confianca":0.9,"criterio":null}'
            for r in requests
        }

    cache_path = tmp_path / "cache.json"
    res1 = screen_with_model(df, model="claude-sonnet-4-6",
                             cache_path=cache_path, submit_fn=fake_submit)
    assert len(res1) == 2 and all(r["decisao"] == "incluir" for r in res1)
    assert calls["n"] == 1
    assert cache_path.exists()

    res2 = screen_with_model(df, model="claude-sonnet-4-6",
                             cache_path=cache_path, submit_fn=fake_submit)
    assert calls["n"] == 1  # cache cheio → não chamou de novo
    assert [r["decisao"] for r in res2] == ["incluir", "incluir"]


def test_screen_with_model_preserves_row_order():
    df = _df()  # row0: doi 10.1/a "AI Jobs"; row1: doi 10.1/b "AI Wages"
    # Map each custom_id to a DISTINCT decisao tied to that row, and return
    # the dict in REVERSED insertion order to prove ordering is by df, not by
    # submit_fn return order.
    cid0 = custom_id(cache_key(df.iloc[0]))
    cid1 = custom_id(cache_key(df.iloc[1]))

    def fake_submit(requests):
        mapping = {
            cid0: '{"decisao":"incluir","justificativa":"row0","confianca":0.9,"criterio":null}',
            cid1: '{"decisao":"excluir","justificativa":"row1","confianca":0.8,"criterio":"E1"}',
        }
        # return reversed so a naive implementation would mis-order
        return {k: mapping[k] for k in reversed(list(mapping))}

    res = screen_with_model(df, model="m", submit_fn=fake_submit)
    assert len(res) == 2
    # result[0] MUST be row0's decision, result[1] MUST be row1's — by df order
    assert res[0]["decisao"] == "incluir" and res[0]["justificativa"] == "row0"
    assert res[1]["decisao"] == "excluir" and res[1]["justificativa"] == "row1"


from scripts.screening.llm.batch_client import anthropic_submit_fn


class _FakeResultMsg:
    def __init__(self, text):
        self.content = [type("C", (), {"text": text, "type": "text"})()]


class _FakeResult:
    def __init__(self, text): self.type = "succeeded"; self.message = _FakeResultMsg(text)


class _FakeEntry:
    def __init__(self, cid, text): self.custom_id = cid; self.result = _FakeResult(text)


class _FakeBatches:
    def __init__(self): self._reqs = None
    def create(self, requests):
        self._reqs = requests
        return type("B", (), {"id": "batch_x"})()
    def retrieve(self, _id):
        return type("B", (), {"processing_status": "ended"})()
    def results(self, _id):
        return [_FakeEntry(r["custom_id"], '{"decisao":"incluir","justificativa":"k","confianca":1.0,"criterio":null}')
                for r in self._reqs]


class _FakeClient:
    def __init__(self): self.messages = type("M", (), {"batches": _FakeBatches()})()


def test_anthropic_submit_fn_with_fake_client():
    fn = anthropic_submit_fn("claude-sonnet-4-6", client=_FakeClient(), poll_interval=0)
    reqs = [{"custom_id": "rABC", "params": {"model": "m", "max_tokens": 1,
             "system": [], "messages": [{"role": "user", "content": "x"}]}}]
    out = fn(reqs)
    assert out["rABC"].startswith('{"decisao":"incluir"')


def test_anthropic_submit_fn_times_out_even_with_zero_poll_interval(monkeypatch):
    import scripts.screening.llm.batch_client as bc

    class _NeverEnds:
        def create(self, requests): return type("B", (), {"id": "b"})()
        def retrieve(self, _id): return type("B", (), {"processing_status": "in_progress"})()
        def results(self, _id): return []

    class _C:
        def __init__(self): self.messages = type("M", (), {"batches": _NeverEnds()})()

    # POLL_TIMEOUT_S=0 → deadline already passed → must raise immediately, not loop forever
    monkeypatch.setattr(bc, "POLL_TIMEOUT_S", 0)
    fn = bc.anthropic_submit_fn("m", client=_C(), poll_interval=0)
    import pytest
    with pytest.raises(TimeoutError):
        fn([{"custom_id": "r1", "params": {}}])
