# tests/extraction/test_extract_llm.py
import base64
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.extraction import extract_llm
from scripts.extraction.extract_llm import build_user_content, parse_extraction, _LLM_FIELDS, fundir, OUTPUT_COLUMNS
from scripts.screening.llm.batch_client import cache_key, custom_id


def _row(**kw):
    base = {"id": "s-001", "review_id": "r1", "doi": "10.1/a", "title": "T",
            "authors": "A, B", "year": 2020, "venue": "AER", "abstract": "Resumo X",
            "text_source": "abstract", "pdf_path": ""}
    base.update(kw)
    return pd.Series(base)


def test_user_content_abstract_is_text_only():
    c = build_user_content(_row(text_source="abstract"))
    assert isinstance(c, list) and len(c) == 1
    assert c[0]["type"] == "text"
    assert "Resumo X" in c[0]["text"] and "T" in c[0]["text"] and "s-001" in c[0]["text"]


def test_user_content_pdf_has_document_block(tmp_path: Path):
    pdf = tmp_path / "s-002.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    c = build_user_content(_row(id="s-002", text_source="pdf", pdf_path=str(pdf)))
    assert isinstance(c, list) and len(c) == 2
    doc = c[0]
    assert doc["type"] == "document"
    assert doc["source"]["type"] == "base64"
    assert doc["source"]["media_type"] == "application/pdf"
    assert base64.b64decode(doc["source"]["data"]) == b"%PDF-1.4 fake"
    assert c[1]["type"] == "text" and "s-002" in c[1]["text"]


def test_user_content_pdf_missing_file_degrades_to_text(tmp_path: Path):
    c = build_user_content(_row(id="s-003", text_source="pdf",
                                pdf_path=str(tmp_path / "naoexiste.pdf")))
    assert len(c) == 1 and c[0]["type"] == "text"
    assert "Resumo X" in c[0]["text"]


def test_user_content_pdf_nan_path_degrades_to_text():
    c = build_user_content(_row(id="s-004", text_source="pdf", pdf_path=np.nan))
    assert len(c) == 1 and c[0]["type"] == "text"
    assert "Resumo X" in c[0]["text"]



def _good_json():
    import json
    ex = {f: "n/a" for f in _LLM_FIELDS}
    ex["tipo_estudo"] = "teórico/modelo"
    return ('{"elegivel":"incluir","motivo_exclusao":"","confianca_extracao":0.8,'
            '"extracao":' + json.dumps(ex, ensure_ascii=False) + "}")


def test_parse_good():
    r = parse_extraction(_good_json())
    assert r["elegivel"] == "incluir"
    assert r["confianca_extracao"] == 0.8
    assert r["extracao"]["tipo_estudo"] == "teórico/modelo"


def test_parse_irrecoverable_is_conservative_incluir():
    r = parse_extraction("desculpe, não consigo")
    assert r["elegivel"] == "incluir"            # falha NUNCA exclui
    assert r["confianca_extracao"] == 0.0
    assert r["extracao"]["sinal_efeito"] == "n/a"
    assert "parse_fail" in r["extracao"]["nota_extracao"]


def test_parse_invalid_elegivel_becomes_incluir():
    r = parse_extraction('{"elegivel":"talvez","motivo_exclusao":"",'
                          '"confianca_extracao":0.5,"extracao":{}}')
    assert r["elegivel"] == "incluir"


def test_parse_clamps_confianca_and_fills_missing():
    r = parse_extraction('{"elegivel":"excluir","motivo_exclusao":"E1",'
                          '"confianca_extracao":9,"extracao":{}}')
    assert r["elegivel"] == "excluir" and r["motivo_exclusao"] == "E1"
    assert r["confianca_extracao"] == 1.0
    assert r["extracao"]["janela"] == "n/a" and r["extracao"]["mec_outros"] == ""


def test_fundir_38_columns_and_block_A_from_corpus():
    row = _row(id="s-009", doi="10.1/z", title="Título Z", authors="X, Y",
               year=2024, venue="JOLE", text_source="pdf")
    parsed = {"elegivel": "incluir", "motivo_exclusao": "",
              "confianca_extracao": 0.7,
              "extracao": {**{f: "n/a" for f in _LLM_FIELDS},
                           "tipo_estudo": "firma/freelancer",
                           "mec_outros": "spillovers"}}
    out = fundir(row, parsed)
    assert list(out.keys()) == OUTPUT_COLUMNS
    assert len(OUTPUT_COLUMNS) == 38  # 34 do schema (inclui revisto_humano) + 4 extras
    # Bloco A bibliográfico do corpus, não do LLM
    assert out["id"] == "s-009" and out["doi"] == "10.1/z"
    assert out["titulo"] == "Título Z" and out["autores"] == "X, Y"
    assert out["ano"] == 2024 and out["periodico"] == "JOLE"
    # B–G do LLM
    assert out["tipo_estudo"] == "firma/freelancer" and out["mec_outros"] == "spillovers"
    # extras
    assert out["elegivel"] == "incluir" and out["text_source"] == "pdf"
    assert out["confianca_extracao"] == 0.7 and out["revisto_humano"] == "False"
    assert out["motivo_exclusao"] == ""


def test_fundir_excluded_keeps_metadata_and_na_fields():
    row = _row(id="s-010", text_source="abstract")
    parsed = {"elegivel": "excluir", "motivo_exclusao": "E1",
              "confianca_extracao": 0.9, "extracao": {f: "n/a" for f in _LLM_FIELDS}}
    out = fundir(row, parsed)
    assert out["elegivel"] == "excluir" and out["motivo_exclusao"] == "E1"
    assert out["id"] == "s-010" and out["titulo"] == "T"   # A ainda do corpus
    assert out["sinal_efeito"] == "n/a"
    assert out["revisto_humano"] == "False"
    assert out["confianca_extracao"] == 0.9


def test_run_e2e_mock(tmp_path, capsys):
    corpus = tmp_path / "03.csv"
    pd.DataFrame([
        {"source": "wos", "doi": "10.1/a", "title": "A", "authors": "S, J",
         "year": 2020, "abstract": "Resumo A", "venue": "AER", "language": "en"},
        {"source": "wos", "doi": "10.1/b", "title": "B", "authors": "B, P",
         "year": 2024, "abstract": "Resumo B", "venue": "JOLE", "language": "en"},
    ]).to_csv(corpus, index=False)
    cdf = pd.read_csv(corpus)
    rids = [custom_id(cache_key(r)) for _, r in cdf.iterrows()]
    man = tmp_path / "04.csv"
    pd.DataFrame({"id": ["s-001", "s-002"], "review_id": rids,
                  "doi": cdf["doi"], "title": cdf["title"],
                  "text_source": ["abstract", "abstract"],
                  "fonte": ["—", "—"], "pdf_path": ["", ""],
                  "status": ["nao_oa", "nao_oa"]}).to_csv(man, index=False)

    def fake_submit(requests):
        return {r["custom_id"]:
                ('{"elegivel":"incluir","motivo_exclusao":"",'
                 '"confianca_extracao":0.6,"extracao":{"tipo_estudo":"survey/revisão"}}')
                for r in requests}

    out = tmp_path / "06_extraction.csv"
    extract_llm.run(corpus=corpus, manifest=man, output=out,
                    cache=tmp_path / "06c.json", submit_fn=fake_submit)
    df = pd.read_csv(out, keep_default_na=False)
    assert len(df) == 2
    assert list(df.columns) == OUTPUT_COLUMNS
    assert (df["elegivel"] == "incluir").all()
    assert set(df["id"]) == {"s-001", "s-002"}
    assert (df["tipo_estudo"] == "survey/revisão").all()
    assert (df["revisto_humano"].astype(str) == "False").all()
    assert "Extração:" in capsys.readouterr().out


def test_run_asserts_on_length_mismatch(tmp_path, monkeypatch):
    import pytest
    import scripts.extraction.extract_llm as M
    corpus = tmp_path / "c.csv"
    pd.DataFrame([{"source": "wos", "doi": "10.1/a", "title": "A", "authors": "S",
                   "year": 2020, "abstract": "x", "venue": "AER", "language": "en"}]).to_csv(corpus, index=False)
    cdf = pd.read_csv(corpus)
    rid = custom_id(cache_key(cdf.iloc[0]))
    man = tmp_path / "m.csv"
    pd.DataFrame({"id": ["s-001"], "review_id": [rid], "doi": ["10.1/a"], "title": ["A"],
                  "text_source": ["abstract"], "fonte": ["—"], "pdf_path": [""],
                  "status": ["nao_oa"]}).to_csv(man, index=False)
    monkeypatch.setattr(M, "screen_with_model", lambda *a, **k: [])  # 0 != 1
    with pytest.raises(AssertionError, match="truncaria"):
        M.run(corpus=corpus, manifest=man, output=tmp_path / "o.csv",
              cache=tmp_path / "k.json", submit_fn=lambda r: {})
