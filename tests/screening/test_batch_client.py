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


# ---- logging / observability ----


def _fake_submit_all_incluir(requests):
    return {
        r["custom_id"]:
        '{"decisao":"incluir","justificativa":"k","confianca":1.0,"criterio":null}'
        for r in requests
    }


def test_screen_with_model_mock_logs_no_api(capsys):
    screen_with_model(_df(), model="claude-sonnet-4-6", mock=True)
    out = capsys.readouterr().out
    assert "Sonnet 4.6" in out
    assert "modo mock" in out
    assert "sem custo" in out or "sem API" in out


def test_screen_with_model_logs_workload(capsys):
    screen_with_model(_df(), model="claude-sonnet-4-6",
                      submit_fn=_fake_submit_all_incluir)
    out = capsys.readouterr().out
    assert "Sonnet 4.6" in out          # friendly model label
    assert "2 a processar" in out       # pending count
    assert "0 em cache" in out          # cached count


def test_screen_with_model_logs_skip_when_fully_cached(capsys, tmp_path):
    cp = tmp_path / "c.json"
    screen_with_model(_df(), model="claude-haiku-4-5-20251001",
                      cache_path=cp, submit_fn=_fake_submit_all_incluir)
    capsys.readouterr()  # discard first-run output
    screen_with_model(_df(), model="claude-haiku-4-5-20251001",
                      cache_path=cp, submit_fn=_fake_submit_all_incluir)
    out = capsys.readouterr().out
    assert "Haiku 4.5" in out
    assert "0 a processar" in out
    assert "pulando" in out


class _RC:
    succeeded = 2
    errored = 0
    canceled = 0
    expired = 0
    processing = 0


class _BatchesWithCounts:
    def __init__(self): self._reqs = None
    def create(self, requests):
        self._reqs = requests
        return type("B", (), {"id": "msgbatch_obs"})()
    def retrieve(self, _id):
        return type("B", (), {"processing_status": "ended",
                              "request_counts": _RC()})()
    def results(self, _id):
        return [_FakeEntry(r["custom_id"],
                '{"decisao":"incluir","justificativa":"x","confianca":1.0,"criterio":null}')
                for r in self._reqs]


class _ClientWithCounts:
    def __init__(self):
        self.messages = type("M", (), {"batches": _BatchesWithCounts()})()


def test_anthropic_submit_fn_logs_batch_id_and_progress(capsys):
    fn = anthropic_submit_fn("claude-haiku-4-5-20251001",
                             client=_ClientWithCounts(), poll_interval=0)
    fn([{"custom_id": "r1", "params": {}}, {"custom_id": "r2", "params": {}}])
    out = capsys.readouterr().out
    assert "msgbatch_obs" in out      # batch id surfaced
    assert "2/2" in out               # done/total progress
    assert "coletado" in out          # collection summary
    assert "decorrido" in out         # elapsed time


def test_build_requests_default_system_block_unchanged():
    df = _df()
    reqs = build_requests(df, model="claude-sonnet-4-6")
    from scripts.screening.llm.prompt import build_system_block
    assert reqs[0]["params"]["system"] == build_system_block()


def test_build_requests_accepts_injected_system_block():
    df = _df()
    sentinel = [{"type": "text", "text": "ARBITER-X", "cache_control": {"type": "ephemeral"}}]
    reqs = build_requests(df, model="claude-opus-4-7", system_block=sentinel)
    assert reqs[0]["params"]["system"] == sentinel
    assert reqs[1]["params"]["system"] == sentinel


def test_screen_with_model_passes_system_block(tmp_path):
    df = _df()
    seen = {}

    def fake_submit(requests):
        seen["sys"] = requests[0]["params"]["system"]
        return {r["custom_id"]:
                '{"decisao":"incluir","justificativa":"k","confianca":1.0}'
                for r in requests}

    sentinel = [{"type": "text", "text": "ARB", "cache_control": {"type": "ephemeral"}}]
    screen_with_model(df, model="claude-opus-4-7", cache_path=tmp_path / "c.json",
                       submit_fn=fake_submit, system_block=sentinel)
    assert seen["sys"] == sentinel


def test_build_requests_default_user_content_unchanged():
    df = _df()
    from scripts.screening.llm.prompt import build_user_block
    reqs = build_requests(df, model="claude-sonnet-4-6")
    assert reqs[0]["params"]["messages"][0]["content"] == build_user_block(df.iloc[0])


def test_build_requests_injected_user_content_fn():
    df = _df()
    sentinel = [{"type": "text", "text": "EXTRACT-DOC"}]
    reqs = build_requests(df, model="claude-sonnet-4-6",
                          user_content_fn=lambda r: sentinel)
    assert reqs[0]["params"]["messages"][0]["content"] == sentinel


def test_screen_with_model_injected_parse_and_content(tmp_path):
    df = _df()
    seen = {}

    def fake_submit(requests):
        seen["content"] = requests[0]["params"]["messages"][0]["content"]
        return {r["custom_id"]: '{"x":1}' for r in requests}

    def parse_fn(raw):
        return {"parsed": raw, "ok": True}

    res = screen_with_model(
        df, model="claude-sonnet-4-6", cache_path=tmp_path / "c.json",
        submit_fn=fake_submit, user_content_fn=lambda r: [{"type": "text", "text": "Z"}],
        parse_fn=parse_fn)
    assert seen["content"] == [{"type": "text", "text": "Z"}]
    assert res[0] == {"parsed": '{"x":1}', "ok": True}


def test_build_requests_default_max_tokens_is_400():
    df = _df()
    reqs = build_requests(df, model="claude-sonnet-4-6")
    assert reqs[0]["params"]["max_tokens"] == 400


def test_screen_with_model_threads_max_tokens(tmp_path):
    df = _df()
    seen = {}
    def fake_submit(requests):
        seen["mt"] = requests[0]["params"]["max_tokens"]
        return {r["custom_id"]: '{"x":1}' for r in requests}
    screen_with_model(df, model="m", cache_path=tmp_path/"c.json",
                       submit_fn=fake_submit, parse_fn=lambda raw: {"r": raw},
                       max_tokens=4096)
    assert seen["mt"] == 4096


def test_errored_none_nao_cacheia_e_reprocessa(tmp_path):
    from scripts.screening.llm import batch_client as BC
    df = pd.DataFrame([
        {"doi": "10.1/a", "title": "A", "year": 2020, "abstract": "x"},
        {"doi": "10.1/b", "title": "B", "year": 2021, "abstract": "y"},
    ])
    cache = tmp_path / "c.json"
    calls = []

    def submit_ok_none(reqs):
        calls.append([r["custom_id"] for r in reqs])
        out = {}
        for i, r in enumerate(reqs):
            out[r["custom_id"]] = (
                '{"decisao":"incluir","confianca":0.9}' if i == 0 else None
            )
        return out

    res1 = BC.screen_with_model(df, model="claude-haiku-4-5-20251001",
                                cache_path=cache, submit_fn=submit_ok_none)
    assert res1[0]["decisao"] == "incluir"
    res2 = BC.screen_with_model(df, model="claude-haiku-4-5-20251001",
                                cache_path=cache, submit_fn=submit_ok_none)
    assert len(calls) == 2
    assert len(calls[1]) == 1  # só o pendente (o errored) reenviado
    assert res2[0]["decisao"] == "incluir"          # veio do cache (run 1)
    assert res2[1]["decisao"] == "incluir"          # row b é index 0 na 2ª chamada → JSON válido, não None


def test_resposta_vazia_cacheia_fallback_terminal(tmp_path):
    from scripts.screening.llm import batch_client as BC
    df = pd.DataFrame([{"doi": "10.1/z", "title": "Z", "year": 2022,
                        "abstract": "w"}])
    cache = tmp_path / "c.json"
    calls = []

    def submit_empty(reqs):
        calls.append(1)
        return {r["custom_id"]: "" for r in reqs}

    r1 = BC.screen_with_model(df, model="claude-haiku-4-5-20251001",
                              cache_path=cache, submit_fn=submit_empty)
    assert r1[0]["justificativa"] == "parse_fail"
    BC.screen_with_model(df, model="claude-haiku-4-5-20251001",
                         cache_path=cache, submit_fn=submit_empty)
    assert len(calls) == 1


def test_regressao_mock_str_inalterado(tmp_path):
    from scripts.screening.llm import batch_client as BC
    df = pd.DataFrame([{"doi": "10.1/r", "title": "R", "year": 2019,
                        "abstract": "v"}])
    cache = tmp_path / "c.json"

    def submit_str(reqs):
        return {r["custom_id"]: '{"decisao":"excluir","confianca":0.7,'
                                '"criterio":"C1"}' for r in reqs}

    out = BC.screen_with_model(df, model="claude-haiku-4-5-20251001",
                               cache_path=cache, submit_fn=submit_str)
    assert out[0]["decisao"] == "excluir"
    assert out[0]["criterio"] == "C1"
    assert abs(out[0]["confianca"] - 0.7) < 1e-9
