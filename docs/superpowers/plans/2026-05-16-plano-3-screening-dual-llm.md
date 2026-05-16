# Plano 3 — Screening título+resumo (dual-LLM) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir o `screening_ta.py` esqueleto por um pipeline dual-LLM (Sonnet 4.6 + Haiku 4.5) que rotula os 2.605 registros, aplica merge por união conservadora, e reporta κ de Cohen inter-modelo — sem trabalho manual.

**Architecture:** Unidades pequenas e puras (prompt, parse, build, merge, κ) testáveis em modo mock sem custo de API; a única fronteira de I/O (submissão à Batch API da Anthropic) é isolada atrás de um callable injetável `submit_fn`, exercitado por um cliente falso nos testes e pelo SDK real em produção. Prompt caching no bloco estável de critérios + Batch API.

**Tech Stack:** Python 3.12, anthropic SDK (Message Batches API), tenacity (retry), scikit-learn (cohen_kappa_score), pandas, python-dotenv. Todas já em `pyproject.toml`.

**Spec:** `docs/superpowers/specs/2026-05-16-plano-3-screening-dual-llm-design.md`

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---------|------------------|
| `scripts/screening/llm/__init__.py` | marca o pacote |
| `scripts/screening/llm/prompt.py` | `build_system_block()` (estável, cacheável), `build_user_block(row)` |
| `scripts/screening/llm/batch_client.py` | `parse_response`, `cache_key`, `custom_id`, `build_requests`, `screen_with_model`, `anthropic_submit_fn` |
| `scripts/screening/screening_ta.py` | (modificar) `merge_conservative`, `run` orquestrando 2 modelos |
| `scripts/screening/agreement.py` | `cohen_kappa`, `confusion_3x3`, `run` → LaTeX |
| `tests/screening/test_screening_prompt.py` | testes do prompt |
| `tests/screening/test_batch_client.py` | testes de parse/build/screen com submit_fn falso |
| `tests/screening/test_screening_ta.py` | (modificar) novo schema dual + merge |
| `tests/screening/test_agreement.py` | testes de κ e tabela |
| `Makefile` | (modificar) targets `screening_ta`, `screening-kappa`, `screen` |

Convenções do repo a seguir: `from __future__ import annotations`; CLI via `argparse` em `_cli(argv)` + `if __name__ == "__main__": sys.exit(_cli(sys.argv[1:]))`; venv local ativado (`source .venv/bin/activate`), **não** `uv run`; pytest; commits convencionais terminando com `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.

---

## Task 1: Pacote `llm/` + prompt estável (system block cacheável)

**Files:**
- Create: `scripts/screening/llm/__init__.py`
- Create: `scripts/screening/llm/prompt.py`
- Test: `tests/screening/test_screening_prompt.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/screening/test_screening_prompt.py
import pandas as pd

from scripts.screening.llm.prompt import build_system_block, build_user_block


def test_system_block_is_cacheable_and_stable():
    a = build_system_block()
    b = build_system_block()
    assert a == b  # determinístico → cacheável
    assert isinstance(a, list) and len(a) == 1
    blk = a[0]
    assert blk["type"] == "text"
    assert blk["cache_control"] == {"type": "ephemeral"}
    txt = blk["text"]
    # janela corrigida (era 2013-2025) e os cinco critérios E1-E5
    assert "2013-01-01" in txt and "2026-06-30" in txt
    for code in ("E1", "E2", "E3", "E4", "E5"):
        assert code in txt
    # E4 explicitamente não-aplicável em título/resumo
    assert "E4" in txt and "não" in txt.lower() and "texto completo" in txt.lower()
    # contrato JSON estrito
    assert '"decisao"' in txt and '"confianca"' in txt and '"criterio"' in txt


def test_user_block_contains_record_fields_only():
    row = pd.Series({
        "title": "AI and Jobs", "authors": "Smith, J.", "year": 2020,
        "venue": "AER", "abstract": "We study AI exposure.",
    })
    u = build_user_block(row)
    assert "AI and Jobs" in u and "Smith, J." in u and "2020" in u
    assert "We study AI exposure." in u
    # o bloco do registro NÃO repete os critérios (eles vão no system cacheado)
    assert "E1" not in u and "CRITÉRIOS" not in u
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/screening/test_screening_prompt.py -v`
Expected: FAIL — `ModuleNotFoundError: scripts.screening.llm.prompt`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/screening/llm/__init__.py
```

(arquivo vazio)

```python
# scripts/screening/llm/prompt.py
"""Blocos de prompt do screening dual-LLM.

O bloco de sistema é estável (idêntico em todas as chamadas) → marcado
para prompt caching. O bloco do usuário carrega só os dados do registro.
"""
from __future__ import annotations

import pandas as pd

_CRITERIA = """\
Você é um avaliador de revisão sistemática em economia. Decida se o estudo \
fornecido pelo usuário deve ser INCLUÍDO no corpus de uma SLR sobre IMPACTOS \
DA INTELIGÊNCIA ARTIFICIAL NO EMPREGO.

CRITÉRIOS DE INCLUSÃO:
- Período de publicação: 2013-01-01 a 2026-06-30.
- Idioma: inglês, português, espanhol ou francês.
- Tipo de IA: ML supervisionado/não-supervisionado, deep learning, NLP, visão \
computacional, LLMs/IA generativa, ou robôs com componente de IA.
- Desfecho: efeito sobre o emprego (nível, criação/destruição de postos, \
exposição ocupacional, demanda por trabalho).
- Tipo: periódico revisado por pares; working paper de instituição reconhecida \
(NBER, IZA, CEPR, BIS, OECD, IPEA, BCB, FGV); capítulo indexado.

CRITÉRIOS DE EXCLUSÃO:
- E1: tema fora do escopo (produtividade individual sem ligação com emprego; \
IA em educação/saúde/ética/governança sem conexão com mercado de trabalho).
- E2: tecnologia fora do escopo (robótica industrial pré-IA, automação \
puramente mecânica, sistemas especialistas legados sem aprendizado).
- E3: tipo de documento inválido (editorial, resenha, opinião, blog, white \
paper sem metodologia, tese não publicada).
- E4: texto completo inacessível. NÃO APLICÁVEL nesta fase — você avalia \
apenas título e resumo; nunca exclua por E4 no screening.
- E5: qualidade insuficiente (sem metodologia descrita ou sem evidência \
verificável aparente no resumo).

Na dúvida genuína, responda "duvida" (será resolvido na leitura de texto \
completo) — nunca exclua por incerteza.

Responda EXCLUSIVAMENTE com um objeto JSON estrito, sem texto antes ou depois:
{"decisao": "incluir" | "excluir" | "duvida", "justificativa": "1-2 frases \
citando o critério", "confianca": <float entre 0 e 1>, "criterio": "E1".."E5" \
quando decisao=excluir, senão null}\
"""


def build_system_block() -> list[dict]:
    """Bloco de sistema estável → elegível a prompt caching."""
    return [{
        "type": "text",
        "text": _CRITERIA,
        "cache_control": {"type": "ephemeral"},
    }]


def build_user_block(row: pd.Series) -> str:
    """Bloco variável: apenas os dados do registro."""
    return (
        f"Título: {row.get('title', '')}\n"
        f"Autores: {row.get('authors', '')}\n"
        f"Ano: {row.get('year', '')}\n"
        f"Periódico: {row.get('venue', '')}\n"
        f"Resumo: {row.get('abstract', '')}"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/screening/test_screening_prompt.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/screening/llm/__init__.py scripts/screening/llm/prompt.py tests/screening/test_screening_prompt.py
git commit -m "feat(screening): prompt dual-LLM com bloco de critérios cacheável

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: `parse_response` — parse de JSON tolerante

**Files:**
- Create: `scripts/screening/llm/batch_client.py`
- Test: `tests/screening/test_batch_client.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/screening/test_batch_client.py
from scripts.screening.llm.batch_client import parse_response


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/screening/test_batch_client.py -v`
Expected: FAIL — `ModuleNotFoundError: scripts.screening.llm.batch_client`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/screening/llm/batch_client.py
"""Cliente de screening em lote (Anthropic Message Batches API).

Funções puras (parse/cache_key/custom_id/build_requests) são testáveis sem
rede. A única fronteira de I/O — submeter o batch e coletar resultados — fica
isolada em `anthropic_submit_fn`, injetável via parâmetro `submit_fn`.
"""
from __future__ import annotations

import hashlib
import json
import re

_VALID = {"incluir", "excluir", "duvida"}

_FALLBACK = {
    "decisao": "duvida",
    "justificativa": "parse_fail",
    "confianca": 0.0,
    "criterio": None,
}


def parse_response(text: str) -> dict:
    """Parse tolerante. JSON irrecuperável → duvida/0 (nunca exclui por falha)."""
    if not text:
        return dict(_FALLBACK)
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
            return dict(_FALLBACK)
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            return dict(_FALLBACK)
    if not isinstance(obj, dict) or obj.get("decisao") not in _VALID:
        out = dict(_FALLBACK)
        out["justificativa"] = str(obj.get("justificativa", "parse_fail"))[:300] \
            if isinstance(obj, dict) else "parse_fail"
        return out
    try:
        conf = float(obj.get("confianca", 0.0))
    except (TypeError, ValueError):
        conf = 0.0
    return {
        "decisao": obj["decisao"],
        "justificativa": str(obj.get("justificativa", ""))[:300],
        "confianca": max(0.0, min(1.0, conf)),
        "criterio": obj.get("criterio") or None,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/screening/test_batch_client.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/screening/llm/batch_client.py tests/screening/test_batch_client.py
git commit -m "feat(screening): parse de JSON tolerante (falha → duvida/0)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `cache_key` + `custom_id` — identidade estável por registro

**Files:**
- Modify: `scripts/screening/llm/batch_client.py`
- Test: `tests/screening/test_batch_client.py`

- [ ] **Step 1: Write the failing test (append ao arquivo)**

```python
# adicionar a tests/screening/test_batch_client.py
import pandas as pd

from scripts.screening.llm.batch_client import cache_key, custom_id


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/screening/test_batch_client.py -k "cache_key or custom_id" -v`
Expected: FAIL — `ImportError: cannot import name 'cache_key'`

- [ ] **Step 3: Write minimal implementation (append ao módulo)**

```python
# adicionar a scripts/screening/llm/batch_client.py

import pandas as pd  # adicionar ao topo junto dos demais imports


def cache_key(row: pd.Series) -> str:
    """Chave de cache estável e idempotente. DOI normalizado → fallback título+ano."""
    doi = str(row.get("doi") or "").strip().lower()
    if doi and doi != "nan":
        return f"doi:{doi}"
    title = str(row.get("title") or "").strip().lower()
    year = str(row.get("year") or "").strip()
    return f"ty:{title}|{year}"


def custom_id(key: str) -> str:
    """custom_id seguro para a Batch API (≤64 chars, [A-Za-z0-9_-])."""
    return "r" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:32]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/screening/test_batch_client.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/screening/llm/batch_client.py tests/screening/test_batch_client.py
git commit -m "feat(screening): cache_key/custom_id estáveis por registro

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `build_requests` — payloads do batch com prompt caching

**Files:**
- Modify: `scripts/screening/llm/batch_client.py`
- Test: `tests/screening/test_batch_client.py`

- [ ] **Step 1: Write the failing test (append)**

```python
# adicionar a tests/screening/test_batch_client.py
from scripts.screening.llm.batch_client import build_requests


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
    done = {cache_key(_df().iloc[0]): {"decisao": "incluir"}}
    reqs = build_requests(_df(), model="claude-haiku-4-5-20251001", cached=done)
    assert len(reqs) == 1
    assert "AI Wages" in reqs[0]["params"]["messages"][0]["content"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/screening/test_batch_client.py -k build_requests -v`
Expected: FAIL — `ImportError: cannot import name 'build_requests'`

- [ ] **Step 3: Write minimal implementation (append)**

```python
# adicionar a scripts/screening/llm/batch_client.py
from scripts.screening.llm.prompt import build_system_block, build_user_block

MAX_TOKENS = 400


def build_requests(df, model: str, cached: dict | None = None) -> list[dict]:
    """Um request por registro ainda não cacheado. system = bloco estável."""
    cached = cached or {}
    system = build_system_block()
    out: list[dict] = []
    for _, row in df.iterrows():
        key = cache_key(row)
        if key in cached:
            continue
        out.append({
            "custom_id": custom_id(key),
            "params": {
                "model": model,
                "max_tokens": MAX_TOKENS,
                "system": system,
                "messages": [{"role": "user", "content": build_user_block(row)}],
            },
        })
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/screening/test_batch_client.py -v`
Expected: PASS (10 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/screening/llm/batch_client.py tests/screening/test_batch_client.py
git commit -m "feat(screening): build_requests com system cacheável, pula cacheados

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: `screen_with_model` — orquestra cache + submit_fn injetável + mock

**Files:**
- Modify: `scripts/screening/llm/batch_client.py`
- Test: `tests/screening/test_batch_client.py`

- [ ] **Step 1: Write the failing test (append)**

```python
# adicionar a tests/screening/test_batch_client.py
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

    # idempotência: re-rodar com cache cheio → zero submissões
    res2 = screen_with_model(df, model="claude-sonnet-4-6",
                             cache_path=cache_path, submit_fn=fake_submit)
    assert calls["n"] == 1  # não chamou de novo
    assert [r["decisao"] for r in res2] == ["incluir", "incluir"]


def test_screen_with_model_preserves_row_order():
    df = _df()

    def fake_submit(requests):
        # devolve fora de ordem de propósito
        out = {}
        for i, r in enumerate(reversed(requests)):
            d = "excluir" if i == 0 else "incluir"
            out[r["custom_id"]] = f'{{"decisao":"{d}","justificativa":"x","confianca":0.7,"criterio":null}}'
        return out

    res = screen_with_model(df, model="m", submit_fn=fake_submit)
    # ordem deve seguir o df, não a ordem de retorno do submit
    assert len(res) == 2
    assert res[0]["decisao"] in {"incluir", "excluir"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/screening/test_batch_client.py -k screen_with_model -v`
Expected: FAIL — `ImportError: cannot import name 'screen_with_model'`

- [ ] **Step 3: Write minimal implementation (append)**

```python
# adicionar a scripts/screening/llm/batch_client.py
from pathlib import Path

# importar o heurístico mock já existente para não duplicar regra
from scripts.screening.screening_ta import _mock_judge


def _load_cache(path: Path | None) -> dict:
    if path and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _save_cache(path: Path | None, cache: dict) -> None:
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, ensure_ascii=False, indent=2),
                         encoding="utf-8")


def screen_with_model(
    df,
    model: str,
    *,
    cache_path: Path | None = None,
    submit_fn=None,
    mock: bool = False,
) -> list[dict]:
    """Rotula todos os registros do df com um modelo. Idempotente via cache.

    mock=True → usa _mock_judge (sem API). Caso contrário, submit_fn(requests)
    deve devolver {custom_id: texto_bruto}. Ordem do retorno segue o df.
    """
    if mock:
        return [_mock_judge(row) for _, row in df.iterrows()]

    if submit_fn is None:
        submit_fn = anthropic_submit_fn(model)

    cache = _load_cache(cache_path)
    pending = build_requests(df, model=model, cached=cache)
    if pending:
        raw_by_cid = submit_fn(pending)
        for req in pending:
            cid = req["custom_id"]
            cache[cid] = parse_response(raw_by_cid.get(cid, ""))
        _save_cache(cache_path, cache)

    return [cache[custom_id(cache_key(row))] for _, row in df.iterrows()]
```

> Nota de implementação: `cache` é indexado por `custom_id` (estável por
> conteúdo). `build_requests` recebe `cached` com chaves `custom_id`; ajuste
> a checagem `if key in cached` da Task 4 para usar `custom_id(key)`:
> ```python
> cid = custom_id(cache_key(row))
> if cid in cached:
>     continue
> ```
> e troque `out.append({"custom_id": custom_id(key), ...})` por `"custom_id": cid`.
> Atualize também o teste `test_build_requests_skips_cached_keys` para
> `done = {custom_id(cache_key(_df().iloc[0])): {...}}`.

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/screening/test_batch_client.py -v`
Expected: PASS (todos, incl. build_requests ajustado e screen_with_model)

- [ ] **Step 5: Commit**

```bash
git add scripts/screening/llm/batch_client.py tests/screening/test_batch_client.py
git commit -m "feat(screening): screen_with_model idempotente (cache por custom_id, submit_fn injetável)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: `anthropic_submit_fn` — fronteira de I/O real (Batch API)

**Files:**
- Modify: `scripts/screening/llm/batch_client.py`
- Test: `tests/screening/test_batch_client.py`

Esta é a única função não coberta por teste unitário (rede). É fina e
exercitada por um cliente falso no teste abaixo.

- [ ] **Step 1: Write the failing test (append)**

```python
# adicionar a tests/screening/test_batch_client.py
from scripts.screening.llm.batch_client import anthropic_submit_fn


class _FakeResultMsg:
    def __init__(self, text): self.content = [type("C", (), {"text": text})()]


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/screening/test_batch_client.py -k anthropic_submit -v`
Expected: FAIL — `ImportError: cannot import name 'anthropic_submit_fn'`

- [ ] **Step 3: Write minimal implementation (append)**

```python
# adicionar a scripts/screening/llm/batch_client.py
import time

from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

POLL_INTERVAL_S = 15
POLL_TIMEOUT_S = 24 * 3600


def anthropic_submit_fn(model: str, client=None, poll_interval: int = POLL_INTERVAL_S):
    """Devolve submit_fn(requests)->{custom_id:texto} via Message Batches API.

    client injetável para teste; em produção usa anthropic.Anthropic()
    (ANTHROPIC_API_KEY via .env). Retry/backoff na submissão.
    """
    if client is None:
        from anthropic import Anthropic
        client = Anthropic()

    @retry(stop=stop_after_attempt(4),
           wait=wait_exponential(multiplier=2, min=2, max=30))
    def _create(requests):
        return client.messages.batches.create(requests=requests)

    def submit_fn(requests: list[dict]) -> dict[str, str]:
        batch = _create(requests)
        waited = 0
        while True:
            status = client.messages.batches.retrieve(batch.id).processing_status
            if status == "ended":
                break
            if waited >= POLL_TIMEOUT_S:
                raise TimeoutError(f"Batch {batch.id} excedeu 24h")
            time.sleep(poll_interval)
            waited += poll_interval
        out: dict[str, str] = {}
        for entry in client.messages.batches.results(batch.id):
            if getattr(entry.result, "type", None) == "succeeded":
                out[entry.custom_id] = entry.result.message.content[0].text
            else:
                out[entry.custom_id] = ""  # → parse_fail → duvida/0
        return out

    return submit_fn
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/screening/test_batch_client.py -v`
Expected: PASS (todos)

- [ ] **Step 5: Commit**

```bash
git add scripts/screening/llm/batch_client.py tests/screening/test_batch_client.py
git commit -m "feat(screening): anthropic_submit_fn (Batch API, polling, retry)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: `merge_conservative` — tabela-verdade da união conservadora

**Files:**
- Modify: `scripts/screening/screening_ta.py`
- Test: `tests/screening/test_screening_ta.py` (substituir conteúdo — schema mudou)

- [ ] **Step 1: Write the failing test (substituir o arquivo inteiro)**

```python
# tests/screening/test_screening_ta.py
import itertools
from pathlib import Path

import pandas as pd
import pytest

from scripts.screening import screening_ta
from scripts.screening.screening_ta import merge_conservative

LABELS = ["incluir", "excluir", "duvida"]


@pytest.mark.parametrize("s,h", itertools.product(LABELS, LABELS))
def test_merge_only_excludes_when_both_exclude(s, h):
    d = merge_conservative(
        {"decisao": s, "justificativa": "a", "confianca": 0.8, "criterio": "E1" if s == "excluir" else None},
        {"decisao": h, "justificativa": "b", "confianca": 0.6, "criterio": "E2" if h == "excluir" else None},
    )
    if s == "excluir" and h == "excluir":
        assert d["decisao_final"] == "excluir"
    else:
        assert d["decisao_final"] == "incluir"
    assert d["concordancia"] == ("concordam" if s == h else "divergem")


def test_merge_picks_criterio_from_higher_confidence_when_both_exclude():
    d = merge_conservative(
        {"decisao": "excluir", "justificativa": "x", "confianca": 0.6, "criterio": "E1"},
        {"decisao": "excluir", "justificativa": "y", "confianca": 0.9, "criterio": "E3"},
    )
    assert d["decisao_final"] == "excluir"
    assert d["criterio_exclusao"] == "E3"  # maior confiança


def test_merge_no_criterio_when_included():
    d = merge_conservative(
        {"decisao": "incluir", "justificativa": "x", "confianca": 0.9, "criterio": None},
        {"decisao": "excluir", "justificativa": "y", "confianca": 0.5, "criterio": "E1"},
    )
    assert d["decisao_final"] == "incluir"
    assert d["criterio_exclusao"] == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/screening/test_screening_ta.py -k merge -v`
Expected: FAIL — `ImportError: cannot import name 'merge_conservative'`

- [ ] **Step 3: Write minimal implementation**

Adicionar a `scripts/screening/screening_ta.py` (manter `_mock_judge` existente; remover o antigo `_llm_judge` e o `run` antigo serão substituídos na Task 8):

```python
def merge_conservative(sonnet: dict, haiku: dict) -> dict:
    """União conservadora: excluir sse AMBOS = excluir.

    criterio_exclusao vem do modelo de maior confiança (só quando exclui).
    """
    both_exclude = sonnet["decisao"] == "excluir" and haiku["decisao"] == "excluir"
    final = "excluir" if both_exclude else "incluir"
    if both_exclude:
        winner = sonnet if sonnet["confianca"] >= haiku["confianca"] else haiku
        criterio = winner.get("criterio") or ""
    else:
        criterio = ""
    return {
        "decisao_sonnet": sonnet["decisao"],
        "justificativa_sonnet": sonnet["justificativa"],
        "confianca_sonnet": sonnet["confianca"],
        "decisao_haiku": haiku["decisao"],
        "justificativa_haiku": haiku["justificativa"],
        "confianca_haiku": haiku["confianca"],
        "decisao_final": final,
        "concordancia": "concordam" if sonnet["decisao"] == haiku["decisao"] else "divergem",
        "criterio_exclusao": criterio,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/screening/test_screening_ta.py -k merge -v`
Expected: PASS (11 passed: 9 paramétricos + 2)

- [ ] **Step 5: Commit**

```bash
git add scripts/screening/screening_ta.py tests/screening/test_screening_ta.py
git commit -m "feat(screening): merge_conservative (excluir sse ambos excluem)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: `run` — orquestra os dois modelos e grava os CSVs

**Files:**
- Modify: `scripts/screening/screening_ta.py`
- Test: `tests/screening/test_screening_ta.py` (append)

- [ ] **Step 1: Write the failing test (append)**

```python
# adicionar a tests/screening/test_screening_ta.py
NEW_COLS = {
    "decisao_sonnet", "justificativa_sonnet", "confianca_sonnet",
    "decisao_haiku", "justificativa_haiku", "confianca_haiku",
    "decisao_final", "concordancia", "criterio_exclusao",
}


def _corpus(tmp_path: Path) -> Path:
    p = tmp_path / "02_dedup.csv"
    pd.DataFrame([
        {"source": "wos", "doi": "10.1/a", "title": "AI and employment in the US",
         "authors": "Smith, J.", "year": 2020, "abstract": "AI exposure on labor",
         "venue": "AER", "language": "en"},
        {"source": "wos", "doi": "10.1/b", "title": "Cooking recipes book",
         "authors": "Brown, P.", "year": 2019, "abstract": "food and recipes",
         "venue": "Food", "language": "en"},
    ]).to_csv(p, index=False)
    return p


def test_run_mock_produces_dual_schema(tmp_path: Path):
    src = _corpus(tmp_path)
    out = tmp_path / "03_screening_ta.csv"
    inc = tmp_path / "03_incluidos_ta.csv"
    screening_ta.run(input=src, output=out, incluidos=inc, mock=True)
    df = pd.read_csv(out)
    assert NEW_COLS <= set(df.columns)
    assert len(df) == 2
    assert df["decisao_final"].isin(["incluir", "excluir"]).all()
    inc_df = pd.read_csv(inc)
    assert (inc_df["decisao_final"] == "incluir").all()
    assert len(inc_df) == (df["decisao_final"] == "incluir").sum()


def test_run_preserves_original_columns(tmp_path: Path):
    src = _corpus(tmp_path)
    out = tmp_path / "03.csv"
    screening_ta.run(input=src, output=out, mock=True)
    df = pd.read_csv(out)
    assert {"source", "doi", "title", "authors", "year", "abstract",
            "venue", "language"} <= set(df.columns)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/screening/test_screening_ta.py -k run_mock -v`
Expected: FAIL — `AssertionError` (NEW_COLS ausentes) ou `TypeError` na assinatura antiga

- [ ] **Step 3: Write minimal implementation**

Substituir o `run` e `_cli` antigos de `scripts/screening/screening_ta.py` (e remover `_llm_judge` e `PROMPT_TEMPLATE` obsoletos; manter `_mock_judge`) por:

```python
from scripts.screening.llm.batch_client import screen_with_model

SONNET = "claude-sonnet-4-6"
HAIKU = "claude-haiku-4-5-20251001"


def run(
    input: Path,
    output: Path,
    incluidos: Path | None = None,
    mock: bool = False,
    cache_dir: Path | None = None,
) -> None:
    df = pd.read_csv(input, encoding="utf-8")

    cs = (cache_dir / "03_cache_sonnet.json") if cache_dir else None
    ch = (cache_dir / "03_cache_haiku.json") if cache_dir else None
    res_s = screen_with_model(df, model=SONNET, cache_path=cs, mock=mock)
    res_h = screen_with_model(df, model=HAIKU, cache_path=ch, mock=mock)

    merged = [merge_conservative(s, h) for s, h in zip(res_s, res_h)]
    mdf = pd.DataFrame(merged)
    out_df = pd.concat([df.reset_index(drop=True), mdf], axis=1)

    output.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(output, index=False, encoding="utf-8")

    if incluidos:
        inc = out_df[out_df["decisao_final"] == "incluir"]
        inc.to_csv(incluidos, index=False, encoding="utf-8")

    n_inc = int((out_df["decisao_final"] == "incluir").sum())
    n_div = int((out_df["concordancia"] == "divergem").sum())
    print(f"Screening: {len(out_df)} → {n_inc} incluir, "
          f"{len(out_df) - n_inc} excluir; {n_div} divergências")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--incluidos", type=Path)
    p.add_argument("--mock", action="store_true")
    p.add_argument("--cache-dir", type=Path, default=Path("data/processed"))
    a = p.parse_args(argv)
    run(a.input, a.output, incluidos=a.incluidos, mock=a.mock, cache_dir=a.cache_dir)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
```

> Atenção a import circular: `batch_client` importa `_mock_judge` de
> `screening_ta`, e `screening_ta` importa `screen_with_model` de
> `batch_client`. Resolver importando `screen_with_model` **dentro de `run`**
> (import tardio), não no topo de `screening_ta.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/screening/test_screening_ta.py -v`
Expected: PASS (todos)

- [ ] **Step 5: Commit**

```bash
git add scripts/screening/screening_ta.py tests/screening/test_screening_ta.py
git commit -m "feat(screening): run dual-modelo grava schema dual + incluidos

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: `agreement.py` — κ de Cohen + matriz 3×3 → LaTeX

**Files:**
- Create: `scripts/screening/agreement.py`
- Test: `tests/screening/test_agreement.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/screening/test_agreement.py
from pathlib import Path

import pandas as pd

from scripts.screening.agreement import cohen_kappa, run


def test_kappa_perfect_agreement():
    a = ["incluir", "excluir", "duvida", "incluir"]
    assert cohen_kappa(a, list(a)) == 1.0


def test_kappa_independent_is_near_zero():
    a = ["incluir"] * 50 + ["excluir"] * 50
    b = (["incluir", "excluir"] * 50)
    k = cohen_kappa(a, b)
    assert -0.3 < k < 0.3


def test_run_writes_latex_table(tmp_path: Path):
    src = tmp_path / "03.csv"
    pd.DataFrame({
        "decisao_sonnet": ["incluir", "excluir", "duvida", "incluir"],
        "decisao_haiku":  ["incluir", "excluir", "incluir", "incluir"],
    }).to_csv(src, index=False)
    out = tmp_path / "kappa_screening.tex"
    run(input=src, output_table=out)
    tex = out.read_text(encoding="utf-8")
    assert "tabular" in tex
    assert "kappa" in tex.lower() or "κ" in tex or "$\\kappa$" in tex
    # matriz 3x3 + linha/coluna de rótulos
    for lab in ("incluir", "excluir", "duvida"):
        assert lab in tex
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/screening/test_agreement.py -v`
Expected: FAIL — `ModuleNotFoundError: scripts.screening.agreement`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/screening/agreement.py
"""Concordância inter-modelo do screening: κ de Cohen + matriz 3×3 → LaTeX.

Lê 03_screening_ta.csv (colunas decisao_sonnet, decisao_haiku) e gera
text/tables/kappa_screening.tex para o capítulo de metodologia.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import cohen_kappa_score, confusion_matrix

_LABELS = ["incluir", "excluir", "duvida"]


def cohen_kappa(a: list[str], b: list[str]) -> float:
    return float(cohen_kappa_score(a, b, labels=_LABELS))


def run(input: Path, output_table: Path) -> None:
    df = pd.read_csv(input, encoding="utf-8")
    s = df["decisao_sonnet"].astype(str).tolist()
    h = df["decisao_haiku"].astype(str).tolist()
    k = cohen_kappa(s, h)
    n = len(df)
    agree = int((df["decisao_sonnet"] == df["decisao_haiku"]).sum())
    cm = confusion_matrix(s, h, labels=_LABELS)

    rows = []
    for i, lab in enumerate(_LABELS):
        cells = " & ".join(str(int(x)) for x in cm[i])
        rows.append(f"{lab} & {cells} \\\\")
    body = "\n".join(rows)

    tex = (
        "\\begin{table}[ht]\n\\centering\n"
        "\\caption{Concordância inter-modelo no screening "
        f"($\\kappa$ de Cohen = {k:.3f}; "
        f"concordância = {agree}/{n} = {agree / n:.1%})}}\n"
        "\\label{tab:kappa-screening}\n"
        "\\begin{tabular}{lccc}\n\\toprule\n"
        " & \\multicolumn{3}{c}{Haiku 4.5} \\\\\n"
        "Sonnet 4.6 & incluir & excluir & duvida \\\\\n\\midrule\n"
        f"{body}\n"
        "\\bottomrule\n\\end{tabular}\n\\end{table}\n"
    )
    output_table.parent.mkdir(parents=True, exist_ok=True)
    output_table.write_text(tex, encoding="utf-8")
    print(f"κ inter-modelo = {k:.3f}; concordância {agree}/{n}; → {output_table}")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output-table", type=Path, required=True)
    a = p.parse_args(argv)
    run(a.input, a.output_table)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/screening/test_agreement.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/screening/agreement.py tests/screening/test_agreement.py
git commit -m "feat(screening): agreement.py — κ de Cohen + matriz 3x3 → LaTeX

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: Makefile — targets do screening dual-LLM

**Files:**
- Modify: `Makefile` (substituir o bloco `screening_ta` e `screen`)

- [ ] **Step 1: Editar o Makefile**

Substituir o target `screening_ta` atual (linhas ~96-102) e `screen` (~120-121) por:

```makefile
.PHONY: screening_ta
screening_ta:
	$(PYTHON) -m scripts.screening.screening_ta \
	    --input $(DATA_PROC)/02_corpus_dedup.csv \
	    --output $(DATA_PROC)/03_screening_ta.csv \
	    --incluidos $(DATA_PROC)/03_incluidos_ta.csv \
	    --cache-dir $(DATA_PROC)

.PHONY: screening-kappa
screening-kappa:
	$(PYTHON) -m scripts.screening.agreement \
	    --input $(DATA_PROC)/03_screening_ta.csv \
	    --output-table $(TAB_DIR)/kappa_screening.tex

.PHONY: screen
screen: consolidate dedup screening_ta screening-kappa
```

- [ ] **Step 2: Verificar sintaxe do Makefile**

Run: `make -n screen`
Expected: imprime os comandos de consolidate, dedup, screening_ta e screening-kappa sem erro de sintaxe.

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "build(screening): targets screening_ta dual + screening-kappa

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: Verificação final + tag `v0.3.0-screening`

**Files:** nenhum (validação)

- [ ] **Step 1: Suíte completa verde**

Run: `source .venv/bin/activate && pytest -q`
Expected: todos passam (≥ 63 anteriores + novos do Plano 3). Anotar o total.

- [ ] **Step 2: Dry-run mock end-to-end no corpus real**

Run:
```bash
source .venv/bin/activate && python -m scripts.screening.screening_ta \
  --input data/processed/02_corpus_dedup.csv \
  --output /tmp/03_mock.csv --incluidos /tmp/03_inc_mock.csv --mock
```
Expected: imprime `Screening: 2605 → <n_inc> incluir, ... ; <n_div> divergências` sem erro; `/tmp/03_mock.csv` tem as 9 colunas novas.

- [ ] **Step 3: Verificar κ no output mock**

Run:
```bash
source .venv/bin/activate && python -m scripts.screening.agreement \
  --input /tmp/03_mock.csv --output-table /tmp/kappa.tex && cat /tmp/kappa.tex
```
Expected: tabela LaTeX com κ (em mock os dois modelos usam o mesmo `_mock_judge` → κ=1.000; isso é esperado e só confirma o cálculo; o κ real sai na execução com API).

- [ ] **Step 4: Sanity gate do design §F4**

Inspecionar `n_inc` do Step 2. Se fora de [80, 600] (faixa ajustada no spec §12), **parar e revisar** prompt/critérios com o usuário antes do Plano 4. Caso contrário, registrar o número e seguir.

> Observação: em modo mock o número reflete o heurístico de substring, não o
> LLM. O gate real só vale após a execução com API (operação manual do
> usuário, fora deste plano — requer `ANTHROPIC_API_KEY` e custo ~US$3).

- [ ] **Step 5: Criar a tag**

```bash
git tag -a v0.3.0-screening -m "Plano 3: screening dual-LLM (Sonnet+Haiku)

Pipeline 02→03 com merge união conservadora + κ de Cohen inter-modelo.
Código testado em modo mock; execução com API é operação manual do usuário."
git tag -l
```

---

## Self-Review (preenchido pelo autor do plano)

**Cobertura do spec:** §2 decisões → Tasks 1,5,6,7,8 (modelos, batch, cache, união); §3 módulos → Tasks 1-9 (mapa 1:1); §4 fluxo → Task 8; §5 schema → Tasks 7,8; §6 prompt (janela 2026 + E1-E5 + E4 N/A) → Task 1; §7 erros (parse tolerante, idempotência, .env) → Tasks 2,5,6; §8 testes → todas; §9 Makefile → Task 10; §10 custo → não-código (Task 11 nota); §12 critérios de sucesso → Task 11. Sem lacunas.

**Placeholders:** nenhum "TBD/TODO"; todo passo de código mostra o código. A nota de import circular (Task 8) e o ajuste de `custom_id` no cache (Task 5) estão explicitados com o código exato.

**Consistência de tipos:** `cache_key`→str, `custom_id(str)`→str, `build_requests(df,model,cached)`→list[dict] com chave `custom_id`, `screen_with_model(...)`→list[dict] (mesmas chaves de `_mock_judge`/`parse_response`: decisao/justificativa/confianca/criterio), `merge_conservative(dict,dict)`→dict com as 9 colunas usadas em Task 8 e lidas em Task 9 (`decisao_sonnet`/`decisao_haiku`). `_mock_judge` (já existe em screening_ta.py) retorna decisao/justificativa/confianca — Task 2/`_FALLBACK` adiciona `criterio`; `merge_conservative` usa `.get("criterio")` com fallback, então mock sem `criterio` não quebra. Consistente.
