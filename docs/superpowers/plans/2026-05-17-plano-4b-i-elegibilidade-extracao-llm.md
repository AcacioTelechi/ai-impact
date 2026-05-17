# Plano 4b-i — Elegibilidade + extração por LLM — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Para os 852 estudos, uma passada combinada por Sonnet 4.6 que decide elegibilidade (E1–E5) e extrai os 33 campos do schema (PDF nativo nos 134, abstract nos 718), produzindo `06_extraction.csv` (38 colunas = 34 do schema + 4 extras; `revisto_humano` já está nos 34).

**Architecture:** Estende `batch_client` com dois pontos de injeção opcionais retrocompatíveis (`user_content_fn` p/ bloco *document* PDF, `parse_fn` p/ o parser de extração) — reusando Batch API + prompt caching + cache + logging + retry. Novo `extract_llm.py` orquestra; novo prompt estável de extração; `validate.py` reusado como sanity.

**Tech Stack:** Python 3.12, pandas, anthropic Batch API (já integrado), pytest. Sem deps novas (PDF→base64 via stdlib `base64`).

**Spec:** `docs/superpowers/specs/2026-05-17-plano-4b-i-elegibilidade-extracao-llm-design.md`

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `scripts/screening/llm/batch_client.py` | (modificar) `build_requests`/`screen_with_model` **+** `user_content_fn` e `parse_fn` opcionais (default = comportamento atual) |
| `scripts/extraction/llm_extract_prompt.py` | **novo:** `build_extract_system_block()` |
| `scripts/extraction/extract_llm.py` | **novo:** `build_user_content`, `parse_extraction`, `fundir`, `run`, `_cli` |
| `tests/screening/test_batch_client.py` | (modificar) testes de retrocompat + injeção |
| `tests/extraction/test_llm_extract_prompt.py` | **novo** |
| `tests/extraction/test_extract_llm.py` | **novo** |
| `Makefile` | (modificar) alvo `extract-llm` |
| `protocols/slr_protocol.md` | (modificar) nota interina §8 |

Fatos de reúso (não modificar): `screen_with_model(df, model, *, cache_path=None, submit_fn=None, mock=False, system_block=None)` retorna `[parse(raw) por linha, ordem do df]`, cache por `custom_id(cache_key(row))`; `build_requests(df, model, cached=None, system_block=None)` monta `messages=[{"role":"user","content": build_user_block(row)}]`; `cache_key`/`custom_id` em `batch_client`; `SCHEMA_COLUMNS` (34, blocos A–G) em `scripts/extraction/extract.py`; `validate.py::run(path)`. Colunas `03_incluidos_final.csv`: `source,doi,title,authors,year,abstract,venue,language,...`. Colunas `04_fulltext_manifest.csv`: `id,review_id,doi,title,text_source,fonte,pdf_path,status`.

Convenções: `from __future__ import annotations`; `_cli(argv)` + `if __name__ == "__main__": sys.exit(_cli(sys.argv[1:]))`; `print`; venv local (não `uv run`); pytest TDD; commits convencionais terminando com `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.

> **Nota de arquitetura (derivada do spec):** o spec pede reusar `screen_with_model` para produzir o JSON de extração. `screen_with_model` hoje fixa `parse_response` (parser de *screening*: decisao/justificativa/confianca/criterio) — usá-lo cru corromperia a extração. Logo a fidelidade ao spec exige tornar o parser injetável (`parse_fn`), além do `user_content_fn` que o spec já cita. Ambos são extensões aditivas retrocompatíveis (default = comportamento atual). O modo `mock=True` do `screen_with_model` usa `_mock_judge` (shape de screening) — a extração **nunca** usa `mock=True`; usa sempre `submit_fn` (default `anthropic_submit_fn` em produção; fake nos testes/dry-run).

---

## Task 1: `batch_client` — `user_content_fn` + `parse_fn` injetáveis (retrocompat)

**Files:**
- Modify: `scripts/screening/llm/batch_client.py`
- Test: `tests/screening/test_batch_client.py`

- [ ] **Step 1: Append these tests to the EXISTING tests/screening/test_batch_client.py** (keep all existing tests; `_df()` and `screen_with_model`/`build_requests` already imported in that file):

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/screening/test_batch_client.py -k "user_content or injected_parse" -v`
Expected: FAIL — `TypeError: ... unexpected keyword argument 'user_content_fn'`

- [ ] **Step 3: Modify scripts/screening/llm/batch_client.py.**

(a) `build_requests` — signature + content selection. Current header is:
```python
def build_requests(df, model: str, cached: dict | None = None,
                   system_block: list[dict] | None = None) -> list[dict]:
```
Replace it (and the content line) so it reads:
```python
def build_requests(df, model: str, cached: dict | None = None,
                   system_block: list[dict] | None = None,
                   user_content_fn=None) -> list[dict]:
    """Um request por registro ainda não cacheado. system = bloco estável
    (screening por default; injetável p/ árbitro via system_block).
    user_content_fn(row)->str|list injetável (default: build_user_block)."""
    cached = cached or {}
    system = system_block if system_block is not None else build_system_block()
    content_fn = user_content_fn if user_content_fn is not None else build_user_block
    out: list[dict] = []
    for _, row in df.iterrows():
        cid = custom_id(cache_key(row))
        if cid in cached:
            continue
        out.append({
            "custom_id": cid,
            "params": {
                "model": model,
                "max_tokens": MAX_TOKENS,
                "system": system,
                "messages": [{"role": "user", "content": content_fn(row)}],
            },
        })
    return out
```
(Only the signature, the docstring, the `content_fn = ...` line, and `content_fn(row)` change; the rest of the loop is identical.)

(b) `screen_with_model` — add two keyword-only params and thread them. Current signature ends with `system_block: list[dict] | None = None,`. Add after it:
```python
    user_content_fn=None,
    parse_fn=None,
```
Inside `screen_with_model`, find the line:
```python
    pending = build_requests(df, model=model, cached=cache, system_block=system_block)
```
Replace with:
```python
    pending = build_requests(df, model=model, cached=cache,
                             system_block=system_block,
                             user_content_fn=user_content_fn)
```
And find the parse line (inside `if pending:` loop):
```python
            cache[cid] = parse_response(raw_by_cid.get(cid, ""))
```
Replace with:
```python
            cache[cid] = (parse_fn or parse_response)(raw_by_cid.get(cid, ""))
```
Change NOTHING else (mock path, logging, retorno, cache load/save unchanged).

- [ ] **Step 4: Run tests**

Run: `source .venv/bin/activate && pytest tests/screening/test_batch_client.py -v` → all pass (every existing test green — `user_content_fn=None`/`parse_fn=None` defaults preserve behavior — plus 3 new).
Full suite `source .venv/bin/activate && pytest -q` (was 171; +3 = 174). Report actual.

- [ ] **Step 5: Commit**

```bash
git add scripts/screening/llm/batch_client.py tests/screening/test_batch_client.py
git commit -m "feat(4b-i): user_content_fn + parse_fn injetáveis no batch_client (retrocompat)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: `build_extract_system_block` — prompt estável de extração

**Files:**
- Create: `scripts/extraction/llm_extract_prompt.py`
- Test: `tests/extraction/test_llm_extract_prompt.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/extraction/test_llm_extract_prompt.py
from scripts.extraction.llm_extract_prompt import build_extract_system_block


def test_extract_block_cacheable_stable():
    a = build_extract_system_block()
    b = build_extract_system_block()
    assert a == b
    assert isinstance(a, list) and len(a) == 1
    blk = a[0]
    assert blk["type"] == "text" and blk["cache_control"] == {"type": "ephemeral"}
    t = blk["text"]
    for code in ("E1", "E2", "E3", "E4", "E5"):
        assert code in t
    # nomes de campos representativos dos blocos B–G
    for f in ("janela", "pre_pos_chatgpt", "tipo_estudo", "metodo_empirico",
              "mec_deslocamento", "sinal_efeito", "score_qualidade",
              "limitacoes_declaradas", "nota_extracao"):
        assert f in t
    # rubrica 1–5 e contrato JSON estrito + instrução abstract-only
    assert "1" in t and "5" in t
    assert '"elegivel"' in t and '"extracao"' in t and '"confianca_extracao"' in t
    assert "n/a" in t.lower()
    assert "não inven" in t.lower()  # "não invente/inventar"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/extraction/test_llm_extract_prompt.py -v`
Expected: FAIL — `ModuleNotFoundError: scripts.extraction.llm_extract_prompt`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/extraction/llm_extract_prompt.py
"""Bloco de sistema estável (cacheável) da extração LLM do Plano 4b-i.

Critérios de elegibilidade (E1–E5), esquema dos 33 campos com enums,
rubrica de qualidade 1–5, instrução abstract-only e contrato JSON estrito.
Ver docs/superpowers/specs/2026-05-17-plano-4b-i-elegibilidade-extracao-llm-design.md
"""
from __future__ import annotations

_TEXT = """\
Você é um extrator de revisão sistemática em economia. Para o estudo fornecido \
(PDF de texto completo OU apenas o resumo), decida ELEGIBILIDADE e, se elegível, \
extraia os campos abaixo.

ELEGIBILIDADE — exclua marcando o código quando:
- E1: tema fora do escopo (sem ligação com emprego/mercado de trabalho).
- E2: tecnologia fora do escopo (sem componente de IA/ML; automação mecânica).
- E3: tipo de documento inválido (editorial, opinião, blog, sem metodologia).
- E4: não é estudo (errata, índice, material suplementar isolado).
- E5: qualidade insuficiente (sem método/evidência verificável).
Na incerteza genuína de elegibilidade, prefira INCLUIR.

EXTRAÇÃO — preencha cada campo com os valores permitidos:
- janela: 2013-2017 | 2018-2022 | 2022-2025
- pre_pos_chatgpt: pre | pos   (pivô 2022-11-30)
- tecnologia_focada: automação | ML/preditiva | deep learning | IA generativa/LLMs | robôs+IA | geral
- tipo_estudo: exposição ocupacional | evidência macro/setorial | firma/freelancer | teórico/modelo | survey/revisão
- metodo_empirico: OLS | DiD | IV | RDD | evento-estudo | estrutural | ML | descritivo | modelo teórico | n/a
- unidade_analise: ocupação | indústria | firma | indivíduo | país | região | múltipla
- fonte_dados: texto curto
- mec_deslocamento, mec_reinstalacao, mec_complementaridade, mec_demanda_agregada: sim | não | n/a
- mec_outros: texto livre
- sinal_efeito: negativo | positivo | nulo | ambíguo | n/a
- magnitude_reportada: texto livre; magnitude_normalizada: float ou vazio
- ocupacoes_afetadas: texto curto
- polarizacao: alta-quali em risco | baixa-quali em risco | ambos | neutro | n/a
- horizonte: curto prazo | médio | longo | projeção
- tipo_pub: journal | working paper | book chapter
- pais_estudo: país-foco ou 'multipais'; periodo_dados: e.g. 2010-2019
- score_qualidade (1–5, rubrica): 5=top-5/identificação causal crível+robustez+replicável; \
4=bom periódico/WP forte, identificação razoável; 3=WP de instituição reconhecida/descritivo \
bem feito; 2=identificação fraca, sem robustez; 1=sem revisão/preliminar. Reflete RIGOR, \
não direção do achado.
- limitacoes_declaradas: texto curto; replicavel: sim | parcial | não | n/a; \
revisado_por_pares: sim | não
- mec_outros/nota_extracao/citacoes_chave: texto livre (citacoes_chave: vazio aqui)

IMPORTANTE: se a fonte for apenas o RESUMO e um campo não for sustentável pelo \
texto disponível, responda "n/a" (enums) ou vazio (texto). NÃO invente dados \
ausentes. Quando elegivel="excluir", devolva os campos de extração como "n/a"/vazio.

Responda EXCLUSIVAMENTE com um objeto JSON estrito, sem texto antes/depois:
{"elegivel": "incluir" | "excluir",
 "motivo_exclusao": "E1".."E5" | "",
 "confianca_extracao": <float 0-1>,
 "extracao": {"tipo_pub": ..., "pais_estudo": ..., "periodo_dados": ...,
   "janela": ..., "pre_pos_chatgpt": ..., "tecnologia_focada": ...,
   "tipo_estudo": ..., "metodo_empirico": ..., "unidade_analise": ..., "fonte_dados": ...,
   "mec_deslocamento": ..., "mec_reinstalacao": ..., "mec_complementaridade": ...,
   "mec_demanda_agregada": ..., "mec_outros": ...,
   "sinal_efeito": ..., "magnitude_reportada": ..., "magnitude_normalizada": ...,
   "ocupacoes_afetadas": ..., "polarizacao": ..., "horizonte": ...,
   "score_qualidade": ..., "limitacoes_declaradas": ..., "replicavel": ...,
   "revisado_por_pares": ..., "nota_extracao": ..., "citacoes_chave": ""}}\
"""


def build_extract_system_block() -> list[dict]:
    """Bloco de sistema estável → elegível a prompt caching."""
    return [{"type": "text", "text": _TEXT, "cache_control": {"type": "ephemeral"}}]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/extraction/test_llm_extract_prompt.py -v`
Expected: PASS (1). Full suite `pytest -q` (174 + 1 = 175). Report actual.

- [ ] **Step 5: Commit**

```bash
git add scripts/extraction/llm_extract_prompt.py tests/extraction/test_llm_extract_prompt.py
git commit -m "feat(4b-i): build_extract_system_block — schema+E1-E5+rubrica, cacheável

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `extract_llm.build_user_content` — PDF doc-block | abstract texto

**Files:**
- Create: `scripts/extraction/extract_llm.py`
- Test: `tests/extraction/test_extract_llm.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/extraction/test_extract_llm.py
import base64
from pathlib import Path

import pandas as pd

from scripts.extraction.extract_llm import build_user_content


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
    assert "Resumo X" in c[0]["text"]  # cai para abstract+metadados
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/extraction/test_extract_llm.py -v`
Expected: FAIL — `ModuleNotFoundError: scripts.extraction.extract_llm`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/extraction/extract_llm.py
"""Plano 4b-i: elegibilidade + extração por LLM (Sonnet 4.6), 1 passada
combinada, PDF nativo onde houver / abstract no resto.

Ver docs/superpowers/specs/2026-05-17-plano-4b-i-elegibilidade-extracao-llm-design.md
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

import pandas as pd

from scripts.extraction.extract import SCHEMA_COLUMNS
from scripts.extraction.llm_extract_prompt import build_extract_system_block
from scripts.screening.llm.batch_client import (
    cache_key, custom_id, screen_with_model,
)

MODEL = "claude-sonnet-4-6"

# Bloco A bibliográfico vem do join (não do LLM); o LLM devolve B–G + A-conteúdo.
_A_BIBLIO = ["id", "doi", "titulo", "autores", "ano", "periodico"]
_LLM_FIELDS = [c for c in SCHEMA_COLUMNS if c not in _A_BIBLIO and c != "revisto_humano"]


def _meta_text(row) -> str:
    return (
        f"id: {row.get('id','')}\nTítulo: {row.get('title','')}\n"
        f"Autores: {row.get('authors','')}\nAno: {row.get('year','')}\n"
        f"Periódico: {row.get('venue','')}\nResumo: {row.get('abstract','')}"
    )


def build_user_content(row):
    """document-block do PDF quando text_source=pdf e arquivo existe; senão
    texto (abstract+metadados). Sempre retorna list[dict]."""
    if row.get("text_source") == "pdf":
        p = Path(str(row.get("pdf_path") or ""))
        if p.is_file():
            data = base64.standard_b64encode(p.read_bytes()).decode("ascii")
            return [
                {"type": "document",
                 "source": {"type": "base64",
                            "media_type": "application/pdf", "data": data}},
                {"type": "text",
                 "text": "Extraia conforme as instruções do sistema.\n"
                         + _meta_text(row)},
            ]
    return [{"type": "text",
             "text": "Fonte: apenas resumo. Extraia conforme as instruções "
                     "do sistema (use n/a/vazio onde o resumo não sustentar).\n"
                     + _meta_text(row)}]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/extraction/test_extract_llm.py -v`
Expected: PASS (3). Full suite `pytest -q` (175 + 3 = 178). Report actual.

- [ ] **Step 5: Commit**

```bash
git add scripts/extraction/extract_llm.py tests/extraction/test_extract_llm.py
git commit -m "feat(4b-i): build_user_content — PDF doc-block | abstract texto

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `extract_llm.parse_extraction` — parser tolerante

**Files:**
- Modify: `scripts/extraction/extract_llm.py`
- Test: `tests/extraction/test_extract_llm.py`

- [ ] **Step 1: Append these tests** (keep existing):

```python
# adicionar a tests/extraction/test_extract_llm.py
from scripts.extraction.extract_llm import parse_extraction


def _good_json():
    ex = {f: "n/a" for f in
          ["tipo_pub","pais_estudo","periodo_dados","janela","pre_pos_chatgpt",
           "tecnologia_focada","tipo_estudo","metodo_empirico","unidade_analise",
           "fonte_dados","mec_deslocamento","mec_reinstalacao","mec_complementaridade",
           "mec_demanda_agregada","mec_outros","sinal_efeito","magnitude_reportada",
           "magnitude_normalizada","ocupacoes_afetadas","polarizacao","horizonte",
           "score_qualidade","limitacoes_declaradas","replicavel","revisado_por_pares",
           "nota_extracao","citacoes_chave"]}
    ex["tipo_estudo"] = "teórico/modelo"
    return ('{"elegivel":"incluir","motivo_exclusao":"","confianca_extracao":0.8,'
            '"extracao":' + __import__("json").dumps(ex, ensure_ascii=False) + "}")


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
    # todos os campos do LLM presentes, faltantes → n/a
    assert r["extracao"]["janela"] == "n/a" and r["extracao"]["mec_outros"] == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/extraction/test_extract_llm.py -k parse -v`
Expected: FAIL — `ImportError: cannot import name 'parse_extraction'`

- [ ] **Step 3: Append implementation to scripts/extraction/extract_llm.py**

```python
import re

_TEXT_FIELDS = {"mec_outros", "fonte_dados", "magnitude_reportada",
                "magnitude_normalizada", "ocupacoes_afetadas",
                "limitacoes_declaradas", "nota_extracao", "citacoes_chave",
                "pais_estudo", "periodo_dados"}


def _empty_extracao(nota: str = "") -> dict:
    d = {}
    for f in _LLM_FIELDS:
        d[f] = "" if f in _TEXT_FIELDS else "n/a"
    d["nota_extracao"] = nota
    return d


def parse_extraction(text: str) -> dict:
    """Tolerante. Falha irrecuperável → elegivel=incluir (conservador, nunca
    exclui por falha técnica), confianca=0, extração n/a, nota parse_fail."""
    fallback = {"elegivel": "incluir", "motivo_exclusao": "",
                "confianca_extracao": 0.0,
                "extracao": _empty_extracao("parse_fail")}
    if not text:
        return fallback
    s = text.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s.lstrip().lower().startswith("json"):
            s = s.lstrip()[4:]
        s = s.strip()
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", s, re.DOTALL)
        if not m:
            return fallback
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            return fallback
    if not isinstance(obj, dict):
        return fallback

    elegivel = obj.get("elegivel")
    if elegivel not in ("incluir", "excluir"):
        elegivel = "incluir"  # conservador
    try:
        conf = float(obj.get("confianca_extracao", 0.0))
    except (TypeError, ValueError):
        conf = 0.0
    conf = max(0.0, min(1.0, conf))

    raw_ex = obj.get("extracao") if isinstance(obj.get("extracao"), dict) else {}
    ex = _empty_extracao()
    for f in _LLM_FIELDS:
        if f in raw_ex and raw_ex[f] not in (None, ""):
            ex[f] = str(raw_ex[f])
    return {
        "elegivel": elegivel,
        "motivo_exclusao": str(obj.get("motivo_exclusao") or ""),
        "confianca_extracao": conf,
        "extracao": ex,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/extraction/test_extract_llm.py -v`
Expected: PASS (3 + 4 = 7). Full suite `pytest -q` (178 + 4 = 182). Report actual.

- [ ] **Step 5: Commit**

```bash
git add scripts/extraction/extract_llm.py tests/extraction/test_extract_llm.py
git commit -m "feat(4b-i): parse_extraction — tolerante, falha→incluir conservador

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: `extract_llm.fundir` — linha de 38 colunas

**Files:**
- Modify: `scripts/extraction/extract_llm.py`
- Test: `tests/extraction/test_extract_llm.py`

- [ ] **Step 1: Append these tests** (keep existing):

```python
# adicionar a tests/extraction/test_extract_llm.py
from scripts.extraction.extract_llm import fundir, OUTPUT_COLUMNS


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/extraction/test_extract_llm.py -k fundir -v`
Expected: FAIL — `ImportError: cannot import name 'fundir'`

- [ ] **Step 3: Append implementation to scripts/extraction/extract_llm.py**

```python
# 34 do schema (já inclui revisto_humano, bloco G) + 4 extras = 38
OUTPUT_COLUMNS = SCHEMA_COLUMNS + [
    "elegivel", "motivo_exclusao", "text_source", "confianca_extracao",
]


def fundir(row, parsed: dict) -> dict:
    """Monta a linha de OUTPUT_COLUMNS: bloco A bibliográfico do corpus/join,
    B–G + A-conteúdo do LLM, + elegivel/motivo/text_source/confianca;
    revisto_humano=False (o 4b-ii marca True no que verificar)."""
    ex = parsed.get("extracao", {})
    out: dict = {}
    for col in SCHEMA_COLUMNS:
        out[col] = ex.get(col, "")
    # Bloco A bibliográfico — determinístico do corpus (não do LLM)
    out["id"] = row.get("id", "")
    out["doi"] = str(row.get("doi") or "")
    out["titulo"] = str(row.get("title") or "")
    out["autores"] = str(row.get("authors") or "")
    out["ano"] = row.get("year", "")
    out["periodico"] = str(row.get("venue") or "")
    out["revisto_humano"] = "False"
    out["elegivel"] = parsed.get("elegivel", "incluir")
    out["motivo_exclusao"] = parsed.get("motivo_exclusao", "")
    out["text_source"] = row.get("text_source", "")
    out["confianca_extracao"] = parsed.get("confianca_extracao", 0.0)
    return {c: out.get(c, "") for c in OUTPUT_COLUMNS}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/extraction/test_extract_llm.py -v`
Expected: PASS (7 + 2 = 9). Full suite `pytest -q` (182 + 2 = 184). Report actual.

- [ ] **Step 5: Commit**

```bash
git add scripts/extraction/extract_llm.py tests/extraction/test_extract_llm.py
git commit -m "feat(4b-i): fundir — 38 colunas, bloco A do corpus, revisto_humano=False

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: `extract_llm.run` + `_cli` — orquestração

**Files:**
- Modify: `scripts/extraction/extract_llm.py`
- Test: `tests/extraction/test_extract_llm.py`

- [ ] **Step 1: Append this test** (keep existing):

```python
# adicionar a tests/extraction/test_extract_llm.py
from scripts.extraction import extract_llm


def test_run_e2e_mock(tmp_path, capsys):
    corpus = tmp_path / "03.csv"
    pd.DataFrame([
        {"source": "wos", "doi": "10.1/a", "title": "A", "authors": "S, J",
         "year": 2020, "abstract": "Resumo A", "venue": "AER", "language": "en"},
        {"source": "wos", "doi": "10.1/b", "title": "B", "authors": "B, P",
         "year": 2024, "abstract": "Resumo B", "venue": "JOLE", "language": "en"},
    ]).to_csv(corpus, index=False)
    # manifesto com review_id derivado igual ao do extract_llm
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/extraction/test_extract_llm.py -k run_e2e -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'run'`

- [ ] **Step 3: Append implementation to scripts/extraction/extract_llm.py**

```python
def run(corpus: Path, manifest: Path, output: Path, cache: Path,
        submit_fn=None) -> None:
    cdf = pd.read_csv(corpus, encoding="utf-8", keep_default_na=False)
    mdf = pd.read_csv(manifest, encoding="utf-8", keep_default_na=False)
    cdf["review_id"] = [custom_id(cache_key(r)) for _, r in cdf.iterrows()]
    m = mdf[["id", "review_id", "text_source", "pdf_path"]]
    df = cdf.merge(m, on="review_id", how="inner")

    res = screen_with_model(
        df, model=MODEL, cache_path=cache, submit_fn=submit_fn,
        system_block=build_extract_system_block(),
        user_content_fn=build_user_content, parse_fn=parse_extraction,
    )
    rows = [fundir(r, parsed) for (_, r), parsed in zip(df.iterrows(), res)]
    odf = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    output.parent.mkdir(parents=True, exist_ok=True)
    odf.to_csv(output, index=False, encoding="utf-8")

    n = len(odf)
    n_inc = int((odf["elegivel"] == "incluir").sum())
    n_pdf = int((odf["text_source"] == "pdf").sum())
    print(f"Extração: {n} processados | {n_inc} elegíveis | "
          f"{n - n_inc} excluídos | {n_pdf} via PDF — modelo {MODEL}")
    print(f"  → {output}")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Plano 4b-i: elegibilidade+extração LLM.")
    p.add_argument("--corpus", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--cache", type=Path, default=Path("data/processed/06_cache_extract.json"))
    a = p.parse_args(argv)
    run(corpus=a.corpus, manifest=a.manifest, output=a.output, cache=a.cache)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
```

- [ ] **Step 4: Run tests**

Run: `source .venv/bin/activate && pytest tests/extraction/test_extract_llm.py -v` → PASS (9 + 1 = 10).
Full suite `source .venv/bin/activate && pytest -q` (184 + 1 = 185). Report actual.
`source .venv/bin/activate && python -c "import scripts.extraction.extract_llm; print('ok')"` → ok.

- [ ] **Step 5: Commit**

```bash
git add scripts/extraction/extract_llm.py tests/extraction/test_extract_llm.py
git commit -m "feat(4b-i): run + CLI — join corpus/manifesto, Sonnet, 06_extraction.csv

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Makefile — alvo `extract-llm`

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: Editar o Makefile**

Adicionar APÓS o alvo `fulltext-acquire` e ANTES de `fetch`. TABs, não espaços. `$(PYTHON)`/`$(DATA_PROC)` existem.

```makefile
.PHONY: extract-llm
extract-llm:
	$(PYTHON) -m scripts.extraction.extract_llm \
	    --corpus $(DATA_PROC)/03_incluidos_final.csv \
	    --manifest $(DATA_PROC)/04_fulltext_manifest.csv \
	    --output $(DATA_PROC)/06_extraction.csv \
	    --cache $(DATA_PROC)/06_cache_extract.json
```

Não adicionar a `screen`/`all`. Não modificar outro alvo.

- [ ] **Step 2: Verificar**

Run: `make -n extract-llm` — imprime o comando com 4 flags, sem erro. `make -n screen` inalterado.

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "build(4b-i): alvo extract-llm (fora de screen/all)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Protocolo §8 nota interina + verificação final + tag

**Files:**
- Modify: `protocols/slr_protocol.md`

- [ ] **Step 1: Editar `protocols/slr_protocol.md`**

Localizar `## 8. Extração de dados`. Acrescentar ao final dessa seção o parágrafo:

```markdown

**Nota interina (2026-05-17, Plano 4b-i):** a decisão de elegibilidade (texto
completo) e a extração dos 33 campos foram operacionalizadas por LLM (Claude
Sonnet 4.6, uma passada combinada; PDF nativo onde houver OA, resumo no
restante — cobertura full-text 15,7%). A verificação humana amostral
(elegibilidade + campos críticos, κ humano×LLM) e a emenda formal do desvio
em relação à leitura/extração 100% manual (§7/§8/§11, versão → 1.2) são
descritas e declaradas no Plano 4b-ii.
```

- [ ] **Step 2: Verificar e commitar**

Run: `grep -n "Nota interina (2026-05-17, Plano 4b-i)\|Sonnet 4.6, uma passada" protocols/slr_protocol.md`
Expected: mostra o parágrafo em §8.

```bash
git add protocols/slr_protocol.md
git commit -m "docs(protocol): §8 — nota interina extração por LLM (4b-i)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 3: Suíte verde + dry-run no corpus real (fake submit, sem rede/API)**

Run: `source .venv/bin/activate && pytest -q` — todos verdes (≥171 prévios + novos). Anotar total.

Run:
```bash
source .venv/bin/activate && python -c "
from pathlib import Path
import pandas as pd
from scripts.extraction import extract_llm as E
def fake(reqs):
    return {r['custom_id']: '{\"elegivel\":\"incluir\",\"motivo_exclusao\":\"\",\"confianca_extracao\":0.5,\"extracao\":{\"tipo_estudo\":\"survey/revisão\"}}' for r in reqs}
E.run(corpus=Path('data/processed/03_incluidos_final.csv'),
      manifest=Path('data/processed/04_fulltext_manifest.csv'),
      output=Path('/tmp/06_extraction.csv'), cache=Path('/tmp/06c.json'), submit_fn=fake)
d=pd.read_csv('/tmp/06_extraction.csv', keep_default_na=False)
print('linhas:', len(d), '(esperado 852)')
print('colunas:', len(d.columns), '(esperado 38)')
print('text_source:', d['text_source'].value_counts().to_dict())
print('ids:', d['id'].iloc[0], '..', d['id'].iloc[-1], 'únicos:', bool(d['id'].is_unique))
from scripts.extraction import validate
import io, contextlib
issues = validate.run(Path('/tmp/06_extraction.csv'))
print('validate issues estruturais:', len(issues))
"
```
Expected: 852 linhas, 38 colunas, text_source {abstract:718, pdf:134}, ids s-001..s-852 únicos, `validate.run` roda sem exceção (issues = lista, pode ser 0 ou >0 por causa do mock uniforme — o importante é não estourar exceção estrutural).

- [ ] **Step 4: Tag**

```bash
git tag -a v0.7.0-extracao -m "Plano 4b-i: elegibilidade + extração por LLM

Sonnet 4.6, 1 passada combinada (PDF nativo 134 / abstract 718).
06_extraction.csv 38 colunas; batch_client estendido retrocompatível
(user_content_fn/parse_fn). Verificação humana + κ + emenda formal: 4b-ii.
Execução real (~US\$3-8) é operação manual do usuário."
git tag -l | tail -3
```

---

## Self-Review (autor do plano)

**Cobertura do spec:** §1 decisões (1 passada/Sonnet/híbrido/abstract-best-effort/elegibilidade) → Tasks 2,3,4,5,6; §2 desvio + nota interina → Task 8; §3 arquitetura (batch_client retrocompat + prompt + extract_llm + validate reuse) → Tasks 1,2,3,4,5,6; §4 fluxo (join review_id, screen_with_model com 3 injeções) → Task 6; §5 contrato/parse conservador → Tasks 2,4; §6 schema 38 col + bloco A do corpus → Task 5; §7 robustez (idempotência via cache do screen_with_model; parse_fail conservador; sem rede nos testes) → Tasks 1,4,6; §8 testes → todas; §9 Makefile/§8 protocolo/validate → Tasks 7,8; §10 YAGNI (verificação/PRISMA/emenda formal = 4b-ii; não tocar validate/extract/fetch) → respeitado; §11 sucesso → Task 8. Sem lacunas. A injeção de `parse_fn` (não citada literalmente no spec mas exigida pela fidelidade ao reúso de `screen_with_model`) está documentada na Nota de arquitetura.

**Placeholders:** nenhum "TBD/TODO"; todo passo mostra código completo; comandos com saída esperada. O `_LLM_FIELDS`/`_A_BIBLIO` derivam de `SCHEMA_COLUMNS` (não hardcode divergente).

**Consistência de tipos:** `build_extract_system_block()->list[dict]` (T2) injetado como `system_block`; `build_user_content(row)->list[dict]` (T3) injetado como `user_content_fn`; `parse_extraction(text)->dict` com chaves `elegivel/motivo_exclusao/confianca_extracao/extracao` (T4) injetado como `parse_fn`; `screen_with_model(...)->list[dict]` (T1, retrocompat) consumido por `run` (T6), pareado com `df.iterrows()` por ordem (screen_with_model retorna na ordem do df — verificado nos planos anteriores); `fundir(row, parsed)->dict` com exatamente `OUTPUT_COLUMNS` (T5) consumido por `run` (T6) via `pd.DataFrame(rows, columns=OUTPUT_COLUMNS)`.

**Correção aritmética aplicada (consistência):** o spec §6 dizia 38 = 33 + 5, mas `revisto_humano` JÁ pertence a `SCHEMA_COLUMNS` (bloco G), então os extras reais são **4** (`elegivel, motivo_exclusao, text_source, confianca_extracao`) e o total correto é **37**. Todo o plano (Task 5/6/8, Goal, título, commit, dry-run) foi ajustado para 37; `OUTPUT_COLUMNS = SCHEMA_COLUMNS + 4 extras`; `fundir` seta `revisto_humano` (que já está no schema, sem duplicar). A regra metodológica do spec (bloco A bibliográfico do corpus; B–G + A-conteúdo do LLM; `revisto_humano=False`) é preservada — só o número mudou. O spec foi corrigido junto.
