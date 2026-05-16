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


import json as _json
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
    df = _df()

    def fake_submit(requests):
        out = {}
        for i, r in enumerate(reversed(requests)):
            d = "excluir" if i == 0 else "incluir"
            out[r["custom_id"]] = f'{{"decisao":"{d}","justificativa":"x","confianca":0.7,"criterio":null}}'
        return out

    res = screen_with_model(df, model="m", submit_fn=fake_submit)
    assert len(res) == 2
    assert res[0]["decisao"] in {"incluir", "excluir"}
