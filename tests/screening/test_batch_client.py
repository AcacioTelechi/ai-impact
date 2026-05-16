import re

import pandas as pd

from scripts.screening.llm.batch_client import cache_key, custom_id, parse_response


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
