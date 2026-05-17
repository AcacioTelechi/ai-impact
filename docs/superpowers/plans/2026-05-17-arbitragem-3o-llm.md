# Arbitragem por 3º LLM — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolver os 865 soft-includes do screening dual-LLM com um 3º LLM árbitro independente (Opus 4.7, cego, binário), produzindo o corpus final para o Plano 4 — substituindo a revisão humana.

**Architecture:** Reúso máximo. Um prompt árbitro estrito novo; `build_requests`/`screen_with_model` ganham um parâmetro opcional `system_block` (default = comportamento atual, zero quebra); um script `arbitragem.py` orquestra seleção (reusa `soft_includes`), arbitragem (reusa `screen_with_model` com Opus + Batch API + cache + logging), fusão e tabela κ (reusa `cohen_kappa`).

**Tech Stack:** Python 3.12, pandas, anthropic Batch API (já integrado), scikit-learn (via `agreement.cohen_kappa`), pytest. Sem dependências novas.

**Spec:** `docs/superpowers/specs/2026-05-17-arbitragem-3o-llm-design.md`

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `scripts/screening/llm/prompt.py` | **+** `build_arbiter_system_block()` (critérios reusados, contrato estrito sem "duvida") |
| `scripts/screening/llm/batch_client.py` | `build_requests`/`screen_with_model` **+** param opcional `system_block`; `_MODEL_LABELS` **+** Opus |
| `scripts/screening/arbitragem.py` | **novo:** `fundir`, `kappa_table`, `run`, `_cli` |
| `tests/screening/test_arbitragem.py` | **novo:** testes de fundir/kappa/run |
| `tests/screening/test_screening_prompt.py` | **+** testes de `build_arbiter_system_block` |
| `tests/screening/test_batch_client.py` | **+** testes do param `system_block` |
| `Makefile` | **+** alvo `arbitragem` |
| `protocols/slr_protocol.md` | §7 reescrito, §11 +item, versão 1.0→1.1 |

Convenções: `from __future__ import annotations`; `_cli(argv)` + `if __name__ == "__main__": sys.exit(_cli(sys.argv[1:]))`; `print` p/ feedback; venv local ativado (`source .venv/bin/activate`), **não** `uv run`; pytest TDD; commits convencionais terminando com `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.

Constantes/fatos: modelo árbitro = `"claude-opus-4-7"`. Schema `03_screening_ta.csv` (17 cols): `source,doi,title,authors,year,abstract,venue,language` + `decisao_sonnet,justificativa_sonnet,confianca_sonnet,decisao_haiku,justificativa_haiku,confianca_haiku,decisao_final,concordancia,criterio_exclusao`. `review_id = custom_id(cache_key(row))` (de `scripts.screening.llm.batch_client`). `soft_includes(df)` vem de `scripts.screening.revisao_export`. `cohen_kappa(a,b)` vem de `scripts.screening.agreement` (usa `labels=["incluir","excluir","duvida"]`; mapeamos rótulos binários para `"incluir"`/`"excluir"` ⊂ esse espaço — o rótulo "duvida" ausente tem marginal zero e não altera κ, então o reúso é correto e DRY).

---

## Task 1: `build_arbiter_system_block` — prompt árbitro estrito

**Files:**
- Modify: `scripts/screening/llm/prompt.py`
- Test: `tests/screening/test_screening_prompt.py`

- [ ] **Step 1: Write the failing test (append ao arquivo existente)**

```python
# adicionar a tests/screening/test_screening_prompt.py
from scripts.screening.llm.prompt import build_arbiter_system_block


def test_arbiter_block_is_cacheable_and_stable():
    a = build_arbiter_system_block()
    b = build_arbiter_system_block()
    assert a == b
    assert isinstance(a, list) and len(a) == 1
    blk = a[0]
    assert blk["type"] == "text"
    assert blk["cache_control"] == {"type": "ephemeral"}
    txt = blk["text"]
    # mesmos critérios do screening
    assert "2013-01-01" in txt and "2026-06-30" in txt
    for code in ("E1", "E2", "E3", "E4", "E5"):
        assert code in txt
    # contrato ESTRITO: binário, sem "duvida" como saída válida
    assert '"incluir"' in txt and '"excluir"' in txt
    assert '"duvida"' not in txt
    assert "duvida" not in txt.lower().split("json")[-1] or "não" in txt.lower()


def test_arbiter_block_differs_from_screening_block():
    from scripts.screening.llm.prompt import build_system_block
    assert build_arbiter_system_block()[0]["text"] != build_system_block()[0]["text"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/screening/test_screening_prompt.py -k arbiter -v`
Expected: FAIL — `ImportError: cannot import name 'build_arbiter_system_block'`

- [ ] **Step 3: Write minimal implementation**

Em `scripts/screening/llm/prompt.py`, após `build_system_block`, adicione (reaproveitando o miolo dos critérios de `_CRITERIA` — extraia a parte de critérios para uma constante compartilhada para não duplicar texto):

```python
# Substituir a definição de _CRITERIA por um miolo compartilhado + dois contratos.
_CRITERIA_CORE = """\
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
apenas título e resumo; nunca exclua por E4.
- E5: qualidade insuficiente (sem metodologia descrita ou sem evidência \
verificável aparente no resumo)."""

_SCREENING_CONTRACT = """

Na dúvida genuína, responda "duvida" (será resolvido na leitura de texto \
completo) — nunca exclua por incerteza.

Responda EXCLUSIVAMENTE com um objeto JSON estrito, sem texto antes ou depois:
{"decisao": "incluir" | "excluir" | "duvida", "justificativa": "1-2 frases \
citando o critério", "confianca": <float entre 0 e 1>, "criterio": "E1".."E5" \
quando decisao=excluir, senão null}"""

_ARBITER_CONTRACT = """

Esta é a DECISÃO FINAL desta fase de seleção: NÃO é permitido responder \
"duvida". Decida "incluir" ou "excluir" mesmo em casos limítrofes. Na \
incerteza genuína, prefira "incluir" (o estudo segue para leitura de texto \
completo, onde poderá ser excluído).

Responda EXCLUSIVAMENTE com um objeto JSON estrito, sem texto antes ou depois:
{"decisao": "incluir" | "excluir", "justificativa": "1-2 frases citando o \
critério", "confianca": <float entre 0 e 1>}"""

_CRITERIA = _CRITERIA_CORE + _SCREENING_CONTRACT
_ARBITER_CRITERIA = _CRITERIA_CORE + _ARBITER_CONTRACT


def build_arbiter_system_block() -> list[dict]:
    """Bloco de sistema do árbitro: mesmos critérios, contrato BINÁRIO estrito
    (sem "duvida"). Estável → elegível a prompt caching."""
    return [{
        "type": "text",
        "text": _ARBITER_CRITERIA,
        "cache_control": {"type": "ephemeral"},
    }]
```

(O `build_system_block` existente continua retornando `_CRITERIA`, agora montado de `_CRITERIA_CORE + _SCREENING_CONTRACT` — texto final idêntico ao anterior, então os testes de screening seguem verdes.)

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/screening/test_screening_prompt.py -v`
Expected: PASS (testes existentes de `build_system_block` + 2 novos do árbitro). Rode também `pytest -q` (142 prévios + 2 = 144).

- [ ] **Step 5: Commit**

```bash
git add scripts/screening/llm/prompt.py tests/screening/test_screening_prompt.py
git commit -m "feat(arbitragem): build_arbiter_system_block (critérios reusados, contrato binário)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: `system_block` injetável em build_requests/screen_with_model

**Files:**
- Modify: `scripts/screening/llm/batch_client.py`
- Test: `tests/screening/test_batch_client.py`

- [ ] **Step 1: Write the failing test (append)**

```python
# adicionar a tests/screening/test_batch_client.py
from scripts.screening.llm.batch_client import build_requests as _br


def test_build_requests_default_system_block_unchanged():
    df = _df()
    reqs = _br(df, model="claude-sonnet-4-6")
    from scripts.screening.llm.prompt import build_system_block
    assert reqs[0]["params"]["system"] == build_system_block()


def test_build_requests_accepts_injected_system_block():
    df = _df()
    sentinel = [{"type": "text", "text": "ARBITER-X", "cache_control": {"type": "ephemeral"}}]
    reqs = _br(df, model="claude-opus-4-7", system_block=sentinel)
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/screening/test_batch_client.py -k "system_block" -v`
Expected: FAIL — `TypeError: ... unexpected keyword argument 'system_block'`

- [ ] **Step 3: Write minimal implementation**

Em `scripts/screening/llm/batch_client.py`:

(a) `build_requests` (linhas ~109-127) — assinatura e uso do system:

```python
def build_requests(df, model: str, cached: dict | None = None,
                   system_block: list[dict] | None = None) -> list[dict]:
    """Um request por registro ainda não cacheado. system = bloco estável
    (screening por default; injetável p/ árbitro via system_block)."""
    cached = cached or {}
    system = system_block if system_block is not None else build_system_block()
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
                "messages": [{"role": "user", "content": build_user_block(row)}],
            },
        })
    return out
```

(b) `screen_with_model` — adicionar `system_block` ao keyword-only e repassar:

```python
def screen_with_model(
    df,
    model: str,
    *,
    cache_path: Path | None = None,
    submit_fn=None,
    mock: bool = False,
    system_block: list[dict] | None = None,
) -> list[dict]:
```

e na linha que chama build_requests (atual `pending = build_requests(df, model=model, cached=cache)`), trocar para:

```python
    pending = build_requests(df, model=model, cached=cache,
                             system_block=system_block)
```

(Não mudar mais nada em screen_with_model: mock path, cache, logging, retorno permanecem.)

(c) `_MODEL_LABELS` (linhas ~88-90) — adicionar o Opus para logging legível:

```python
_MODEL_LABELS = {
    "claude-sonnet-4-6": "Sonnet 4.6",
    "claude-haiku-4-5-20251001": "Haiku 4.5",
    "claude-opus-4-7": "Opus 4.7",
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/screening/test_batch_client.py -v`
Expected: PASS — todos os testes existentes (regressão: `system_block=None` → idêntico) + 3 novos. Rode `pytest -q` (144 prévios + 3 = 147).

- [ ] **Step 5: Commit**

```bash
git add scripts/screening/llm/batch_client.py tests/screening/test_batch_client.py
git commit -m "feat(arbitragem): system_block injetável (retrocompatível) + label Opus

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `arbitragem.fundir` — tabela-verdade da fusão

**Files:**
- Create: `scripts/screening/arbitragem.py`
- Test: `tests/screening/test_arbitragem.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/screening/test_arbitragem.py
import pandas as pd

from scripts.screening.arbitragem import fundir
from scripts.screening.llm.batch_client import cache_key, custom_id


def _row(s, h, final, doi):
    return {
        "source": "wos", "doi": doi, "title": "T", "authors": "A",
        "year": 2020, "abstract": "x", "venue": "V", "language": "en",
        "decisao_sonnet": s, "justificativa_sonnet": "js", "confianca_sonnet": 0.5,
        "decisao_haiku": h, "justificativa_haiku": "jh", "confianca_haiku": 0.5,
        "decisao_final": final, "concordancia": "x", "criterio_exclusao": "",
    }


def _rid(d):
    return custom_id(cache_key(pd.Series(d)))


def test_fundir_four_categories_plus_failure():
    screening = pd.DataFrame([
        _row("incluir", "incluir", "incluir", "10.1/bi"),   # ambos-incluir
        _row("excluir", "excluir", "excluir", "10.1/be"),    # ambos-excluir
        _row("incluir", "duvida", "incluir", "10.1/s1"),     # soft → árbitro incluir
        _row("duvida", "excluir", "incluir", "10.1/s2"),     # soft → árbitro excluir
        _row("duvida", "duvida", "incluir", "10.1/s3"),      # soft → árbitro falha
    ])
    arb = {
        _rid(screening.iloc[2].to_dict()): {"decisao": "incluir", "justificativa": "ok", "confianca": 0.9},
        _rid(screening.iloc[3].to_dict()): {"decisao": "excluir", "justificativa": "E1", "confianca": 0.8},
        _rid(screening.iloc[4].to_dict()): {"decisao": "duvida", "justificativa": "parse_fail", "confianca": 0.0},
    }
    out = fundir(screening, arb).set_index("doi")
    assert out.loc["10.1/bi", "decisao_final_arbitrada"] == "incluir"
    assert out.loc["10.1/bi", "origem_decisao"] == "llm_concordante"
    assert out.loc["10.1/be", "decisao_final_arbitrada"] == "excluir"
    assert out.loc["10.1/be", "origem_decisao"] == "llm_concordante"
    assert out.loc["10.1/s1", "decisao_final_arbitrada"] == "incluir"
    assert out.loc["10.1/s1", "origem_decisao"] == "arbitro"
    assert out.loc["10.1/s1", "decisao_arbitro"] == "incluir"
    assert out.loc["10.1/s2", "decisao_final_arbitrada"] == "excluir"
    assert out.loc["10.1/s2", "origem_decisao"] == "arbitro"
    assert out.loc["10.1/s3", "decisao_final_arbitrada"] == "incluir"   # falha → conservador
    assert out.loc["10.1/s3", "origem_decisao"] == "arbitro_falha"
    assert len(out) == 5


def test_fundir_concordantes_have_empty_arbiter_cols():
    screening = pd.DataFrame([_row("incluir", "incluir", "incluir", "10.1/bi")])
    out = fundir(screening, {})
    assert out.iloc[0]["decisao_arbitro"] == ""
    assert out.iloc[0]["justificativa_arbitro"] == ""
    assert out.iloc[0]["confianca_arbitro"] == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/screening/test_arbitragem.py -k fundir -v`
Expected: FAIL — `ModuleNotFoundError: scripts.screening.arbitragem`

- [ ] **Step 3: Write minimal implementation**

```python
# scripts/screening/arbitragem.py
"""Arbitragem por 3º LLM (Opus 4.7) dos soft-includes do screening.

Substitui a revisão humana: os 865 casos não-unânimes (decisão final
"incluir" não unânime) são decididos por um árbitro cego e independente,
forçado a binário. Ver docs/superpowers/specs/2026-05-17-arbitragem-3o-llm-design.md
e protocolo §7 (versão 1.1, emenda 2026-05-17).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from scripts.screening.agreement import cohen_kappa
from scripts.screening.llm.batch_client import cache_key, custom_id, screen_with_model
from scripts.screening.llm.prompt import build_arbiter_system_block
from scripts.screening.revisao_export import soft_includes

ARBITRO = "claude-opus-4-7"

_ARB_COLS = ["decisao_arbitro", "justificativa_arbitro", "confianca_arbitro",
             "decisao_final_arbitrada", "origem_decisao"]


def fundir(screening: pd.DataFrame, arb_by_rid: dict[str, dict]) -> pd.DataFrame:
    """Funde concordância LLM + veredito do árbitro nos 865.

    arb_by_rid: review_id → {decisao, justificativa, confianca}.
    Regra (ver spec §5): ambos-incluir/ambos-excluir → llm_concordante;
    soft-include → veredito binário do árbitro (origem 'arbitro'); veredito
    ∉ {incluir,excluir} → 'incluir' conservador (origem 'arbitro_falha').
    """
    out = screening.copy().reset_index(drop=True)
    d_arb, j_arb, c_arb, finais, origens = [], [], [], [], []
    for _, row in out.iterrows():
        s, h = row["decisao_sonnet"], row["decisao_haiku"]
        if s == "incluir" and h == "incluir":
            d_arb.append(""); j_arb.append(""); c_arb.append("")
            finais.append("incluir"); origens.append("llm_concordante")
        elif s == "excluir" and h == "excluir":
            d_arb.append(""); j_arb.append(""); c_arb.append("")
            finais.append("excluir"); origens.append("llm_concordante")
        else:
            a = arb_by_rid.get(custom_id(cache_key(row)), {})
            dec = a.get("decisao")
            d_arb.append(dec if dec is not None else "")
            j_arb.append(a.get("justificativa", ""))
            c_arb.append(a.get("confianca", ""))
            if dec == "incluir":
                finais.append("incluir"); origens.append("arbitro")
            elif dec == "excluir":
                finais.append("excluir"); origens.append("arbitro")
            else:  # duvida / parse_fail / ausente → conservador
                finais.append("incluir"); origens.append("arbitro_falha")
    out["decisao_arbitro"] = d_arb
    out["justificativa_arbitro"] = j_arb
    out["confianca_arbitro"] = c_arb
    out["decisao_final_arbitrada"] = finais
    out["origem_decisao"] = origens
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/screening/test_arbitragem.py -v`
Expected: PASS (2). `pytest -q` (147 prévios + 2 = 149).

- [ ] **Step 5: Commit**

```bash
git add scripts/screening/arbitragem.py tests/screening/test_arbitragem.py
git commit -m "feat(arbitragem): fundir — tabela-verdade (concordante/arbitro/arbitro_falha)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `arbitragem.kappa_table` — concordância binária honesta

**Files:**
- Modify: `scripts/screening/arbitragem.py`
- Test: `tests/screening/test_arbitragem.py`

- [ ] **Step 1: Write the failing test (append)**

```python
# adicionar a tests/screening/test_arbitragem.py
from pathlib import Path
from scripts.screening.arbitragem import kappa_table


def test_kappa_table_writes_latex_pairwise(tmp_path: Path):
    # 4 soft-includes já fundidos com decisao_arbitro preenchida
    df = pd.DataFrame([
        {"decisao_sonnet": "duvida", "decisao_haiku": "excluir",
         "decisao_arbitro": "excluir", "origem_decisao": "arbitro"},
        {"decisao_sonnet": "incluir", "decisao_haiku": "duvida",
         "decisao_arbitro": "incluir", "origem_decisao": "arbitro"},
        {"decisao_sonnet": "duvida", "decisao_haiku": "duvida",
         "decisao_arbitro": "incluir", "origem_decisao": "arbitro"},
        {"decisao_sonnet": "incluir", "decisao_haiku": "incluir",
         "decisao_arbitro": "", "origem_decisao": "llm_concordante"},  # ignorado
    ])
    out = tmp_path / "arbitragem_kappa.tex"
    kappa_table(df, out)
    tex = out.read_text(encoding="utf-8")
    assert "tabular" in tex
    assert "kappa" in tex.lower() or "$\\kappa$" in tex
    assert "Sonnet" in tex and "Haiku" in tex
    assert r"\%" in tex                       # percent escapado
    assert tex.count("{") == tex.count("}")   # balanceado
    # só os 3 arbitrados entram no cálculo (o concordante é excluído)
    assert "n=3" in tex or "n = 3" in tex
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/screening/test_arbitragem.py -k kappa -v`
Expected: FAIL — `ImportError: cannot import name 'kappa_table'`

- [ ] **Step 3: Write minimal implementation (append a arbitragem.py)**

```python
def _to_binary(label: str) -> str:
    """incluir/duvida → 'incluir' (manter); excluir → 'excluir'.

    Mantém o rótulo no espaço ["incluir","excluir","duvida"] de
    agreement.cohen_kappa (o "duvida" ausente tem marginal zero e não
    altera κ → reúso DRY correto)."""
    return "excluir" if str(label) == "excluir" else "incluir"


def kappa_table(arbitrado: pd.DataFrame, output_table: Path) -> None:
    """Concordância par-a-par árbitro×Sonnet e árbitro×Haiku nos arbitrados."""
    sub = arbitrado[arbitrado["origem_decisao"].isin(["arbitro", "arbitro_falha"])]
    n = len(sub)
    output_table.parent.mkdir(parents=True, exist_ok=True)
    if n == 0:
        output_table.write_text(
            "\\begin{tabular}{l}\\toprule Nenhum arbitrado \\\\ \\bottomrule \\end{tabular}\n",
            encoding="utf-8")
        print(f"κ árbitro = n/a (0 arbitrados); → {output_table}")
        return
    arb = [_to_binary(x) for x in sub["decisao_arbitro"]]
    son = [_to_binary(x) for x in sub["decisao_sonnet"]]
    hai = [_to_binary(x) for x in sub["decisao_haiku"]]
    k_s, k_h = cohen_kappa(arb, son), cohen_kappa(arb, hai)
    ag_s = int(sum(a == b for a, b in zip(arb, son)))
    ag_h = int(sum(a == b for a, b in zip(arb, hai)))
    tex = (
        "\\begin{table}[ht]\n\\centering\n"
        "\\caption{Concordância do árbitro (Opus 4.7) com os triadores nos "
        f"casos arbitrados (n={n}; rótulo binário: excluir vs. manter "
        "[incluir/duvida])}\n"
        "\\label{tab:arbitragem-kappa}\n"
        "\\begin{tabular}{lcc}\n\\toprule\n"
        "Par & Concordância & $\\kappa$ de Cohen \\\\\n\\midrule\n"
        f"Árbitro × Sonnet 4.6 & {ag_s}/{n} = {ag_s / n * 100:.1f}\\% & {k_s:.3f} \\\\\n"
        f"Árbitro × Haiku 4.5 & {ag_h}/{n} = {ag_h / n * 100:.1f}\\% & {k_h:.3f} \\\\\n"
        "\\bottomrule\n\\end{tabular}\n\\end{table}\n"
    )
    output_table.write_text(tex, encoding="utf-8")
    print(f"κ árbitro×Sonnet={k_s:.3f}, ×Haiku={k_h:.3f} (n={n}); → {output_table}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/screening/test_arbitragem.py -v`
Expected: PASS (3). `pytest -q` (149 prévios + 1 = 150).

- [ ] **Step 5: Commit**

```bash
git add scripts/screening/arbitragem.py tests/screening/test_arbitragem.py
git commit -m "feat(arbitragem): kappa_table — concordância binária honesta (DRY cohen_kappa)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: `arbitragem.run` + `_cli` — orquestração

**Files:**
- Modify: `scripts/screening/arbitragem.py`
- Test: `tests/screening/test_arbitragem.py`

- [ ] **Step 1: Write the failing test (append)**

```python
# adicionar a tests/screening/test_arbitragem.py
from scripts.screening import arbitragem


def _screening_csv(tmp_path: Path) -> Path:
    p = tmp_path / "03_screening_ta.csv"
    pd.DataFrame([
        _row("incluir", "incluir", "incluir", "10.1/bi"),
        _row("excluir", "excluir", "excluir", "10.1/be"),
        _row("incluir", "duvida", "incluir", "10.1/s1"),
        _row("duvida", "duvida", "incluir", "10.1/s2"),
    ]).to_csv(p, index=False)
    return p


def test_run_mock_produces_arbitrado_and_incluidos(tmp_path: Path):
    src = _screening_csv(tmp_path)
    arb = tmp_path / "03_screening_arbitrado.csv"
    inc = tmp_path / "03_incluidos_final.csv"
    kap = tmp_path / "arbitragem_kappa.tex"
    arbitragem.run(screening_csv=src, arbitrado_csv=arb, incluidos_csv=inc,
                   kappa_table_path=kap, cache_dir=tmp_path, mock=True)
    a = pd.read_csv(arb, keep_default_na=False)
    assert len(a) == 4
    assert {"decisao_arbitro", "decisao_final_arbitrada", "origem_decisao"} <= set(a.columns)
    # 2 concordantes + 2 soft arbitrados (mock _mock_judge decide os soft)
    assert (a["origem_decisao"] == "llm_concordante").sum() == 2
    assert a["decisao_final_arbitrada"].isin(["incluir", "excluir"]).all()
    i = pd.read_csv(inc, keep_default_na=False)
    assert (i["decisao_final_arbitrada"] == "incluir").all()
    assert len(i) == (a["decisao_final_arbitrada"] == "incluir").sum()
    assert kap.exists() and "tabular" in kap.read_text()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/screening/test_arbitragem.py -k run_mock -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'run'`

- [ ] **Step 3: Write minimal implementation (append a arbitragem.py)**

```python
def run(
    screening_csv: Path,
    arbitrado_csv: Path,
    incluidos_csv: Path,
    kappa_table_path: Path,
    cache_dir: Path | None = None,
    mock: bool = False,
) -> None:
    df = pd.read_csv(screening_csv, encoding="utf-8", keep_default_na=False)
    soft = soft_includes(df)
    cache_path = (cache_dir / "03_cache_arbitro.json") if cache_dir else None
    res = screen_with_model(
        soft, model=ARBITRO, cache_path=cache_path, mock=mock,
        system_block=build_arbiter_system_block(),
    )
    arb_by_rid: dict[str, dict] = {}
    for (_, row), r in zip(soft.iterrows(), res):
        arb_by_rid[custom_id(cache_key(row))] = r

    arbitrado = fundir(df, arb_by_rid)
    arbitrado_csv.parent.mkdir(parents=True, exist_ok=True)
    arbitrado.to_csv(arbitrado_csv, index=False, encoding="utf-8")
    incluidos = arbitrado[arbitrado["decisao_final_arbitrada"] == "incluir"]
    incluidos.to_csv(incluidos_csv, index=False, encoding="utf-8")
    kappa_table(arbitrado, kappa_table_path)

    n_inc = len(incluidos)
    n_arb = int(arbitrado["origem_decisao"].isin(["arbitro", "arbitro_falha"]).sum())
    n_fail = int((arbitrado["origem_decisao"] == "arbitro_falha").sum())
    print(f"Arbitragem: {len(arbitrado)} registros | {n_arb} arbitrados | "
          f"{n_inc} incluídos | {n_fail} falhas→incluir")
    print(f"  → {arbitrado_csv}\n  → {incluidos_csv}\n  → {kappa_table_path}")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Arbitragem por 3º LLM dos soft-includes.")
    p.add_argument("--screening", type=Path, required=True)
    p.add_argument("--arbitrado", type=Path, required=True)
    p.add_argument("--incluidos", type=Path, required=True)
    p.add_argument("--kappa-table", type=Path, required=True)
    p.add_argument("--cache-dir", type=Path, default=Path("data/processed"))
    p.add_argument("--mock", action="store_true")
    a = p.parse_args(argv)
    run(screening_csv=a.screening, arbitrado_csv=a.arbitrado,
        incluidos_csv=a.incluidos, kappa_table_path=a.kappa_table,
        cache_dir=a.cache_dir, mock=a.mock)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/screening/test_arbitragem.py -v` → PASS (4).
`source .venv/bin/activate && pytest -q` (expect 150 prévios + 1 = 151). Report actual.
`source .venv/bin/activate && python -c "import scripts.screening.arbitragem; print('ok')"` → ok.

- [ ] **Step 5: Commit**

```bash
git add scripts/screening/arbitragem.py tests/screening/test_arbitragem.py
git commit -m "feat(arbitragem): run + CLI (Opus árbitro → arbitrado/incluidos/kappa)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Makefile — alvo `arbitragem`

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: Editar o Makefile**

Adicionar, após o alvo `revisao-ingest` e ANTES de `fetch`, o bloco (TABs, não espaços; `$(PYTHON)`/`$(DATA_PROC)`/`$(TAB_DIR)` são variáveis existentes):

```makefile
.PHONY: arbitragem
arbitragem:
	$(PYTHON) -m scripts.screening.arbitragem \
	    --screening $(DATA_PROC)/03_screening_ta.csv \
	    --arbitrado $(DATA_PROC)/03_screening_arbitrado.csv \
	    --incluidos $(DATA_PROC)/03_incluidos_final.csv \
	    --kappa-table $(TAB_DIR)/arbitragem_kappa.tex \
	    --cache-dir $(DATA_PROC)
```

NÃO adicionar a `screen` (passo pós-screening, custa API, decisão deliberada).

- [ ] **Step 2: Verificar**

Run: `make -n arbitragem` — imprime o comando com os 5 flags, sem erro de Make. Rode `make -n screen` para confirmar `screen` inalterado.

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "build(arbitragem): alvo arbitragem (fora de screen)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Protocolo §7 reescrito + §11 + versão 1.1

**Files:**
- Modify: `protocols/slr_protocol.md`

- [ ] **Step 1: Atualizar o cabeçalho de versão**

Localizar a linha `**Versão do protocolo:** 1.0` e trocar por:

```markdown
**Versão do protocolo:** 1.1 (emenda 2026-05-17 — ver §7 e §11)
```

- [ ] **Step 2: Reescrever a etapa de Screening em §7**

Em `## 7. Processo de seleção`, substituir o item 3 atual e o parágrafo de revisão humana (adicionado na v0.4.0) por:

```markdown
3. **Screening (título+resumo) — tri-LLM.** Pré-filtragem por dois triadores
   independentes (Claude Sonnet 4.6 + Haiku 4.5, união conservadora, κ=0,602).
   Os casos não-unânimes ("soft-includes": decisão final "incluir" não unânime)
   são decididos por um terceiro avaliador independente e mais capaz — Claude
   Opus 4.7, cego (não vê os pareceres dos triadores) e forçado a binário
   (incluir/excluir). 462 "ambos-incluir" e 1278 "ambos-excluir" são aceitos
   pela concordância dos triadores; os 865 ambíguos pelo árbitro.

   **Emenda 2026-05-17:** o protocolo v1.0 previa "revisão humana" nesta etapa.
   Ela foi substituída por arbitragem por 3º LLM em razão de restrição de
   tempo/escala (revisor único, 865 casos, prazo de um semestre). Desvio
   declarado; mitigação e limitação em §11. A ferramenta de revisão humana
   (`scripts/screening/revisao_export.py`/`revisao_ingest.py`) permanece
   disponível como auditoria alternativa.
```

- [ ] **Step 3: Adicionar item a §11 (Limitações)**

Em `## 11. Limitações antecipadas`, adicionar o item:

```markdown
- **Ausência de revisor humano na seleção (desvio do protocolo registrado).**
  O protocolo v1.0 comprometia-se com revisão humana no screening; a v1.1 a
  substituiu por arbitragem por 3º LLM (Opus 4.7). Mitigação: três modelos
  independentes, sendo o árbitro mais capaz e não-participante do screening;
  concordância par-a-par árbitro×triadores reportada (`arbitragem_kappa.tex`);
  regra conservadora (na incerteza, inclui; falha técnica nunca exclui).
  Limitação reconhecida e passível de questionamento em banca.
```

- [ ] **Step 4: Verificar e commitar**

Run: `grep -n "Versão do protocolo\|tri-LLM\|Ausência de revisor humano" protocols/slr_protocol.md`
Expected: mostra a versão 1.1, o item 3 tri-LLM e o item de §11.

```bash
git add protocols/slr_protocol.md
git commit -m "docs(protocol): v1.1 — screening tri-LLM (árbitro Opus); desvio declarado §11

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Verificação final + tag `v0.5.0-arbitragem`

**Files:** nenhum (validação)

- [ ] **Step 1: Suíte completa verde**

Run: `source .venv/bin/activate && pytest -q`
Expected: todos verdes (≥ 142 prévios + novos das Tasks 1-5). Anotar total.

- [ ] **Step 2: Dry-run mock e2e no corpus real**

Run:
```bash
source .venv/bin/activate && python -m scripts.screening.arbitragem \
  --screening data/processed/03_screening_ta.csv \
  --arbitrado /tmp/03_screening_arbitrado.csv \
  --incluidos /tmp/03_incluidos_final.csv \
  --kappa-table /tmp/arbitragem_kappa.tex \
  --cache-dir /tmp --mock
```
Expected: imprime `Arbitragem: 2605 registros | 865 arbitrados | <n_inc> incluídos | <n_fail> falhas→incluir`.

- [ ] **Step 3: Sanidade do output**

Run:
```bash
source .venv/bin/activate && python -c "
import pandas as pd
a=pd.read_csv('/tmp/03_screening_arbitrado.csv', keep_default_na=False)
print('linhas:', len(a), '(esperado 2605)')
print('origem:', a['origem_decisao'].value_counts().to_dict())
i=pd.read_csv('/tmp/03_incluidos_final.csv', keep_default_na=False)
print('incluidos:', len(i))
print(open('/tmp/arbitragem_kappa.tex').read())
"
```
Expected: 2605 linhas; `origem` com `llm_concordante` (462 incluir + 1278 excluir = 1740) + `arbitro`/`arbitro_falha` somando 865; tabela κ com `\%` escapado e chaves balanceadas. (Em mock, `_mock_judge` decide os 865 por heurística de substring — o número de incluídos NÃO é o gate real; o gate §F4 só vale com Opus real, operação manual do usuário ~US$3-6.)

- [ ] **Step 4: Tag**

```bash
git tag -a v0.5.0-arbitragem -m "Arbitragem por 3º LLM (Opus 4.7) dos 865 soft-includes

Substitui a revisão humana (desvio declarado, protocolo v1.1 §7/§11).
Árbitro cego, binário; saídas 03_screening_arbitrado.csv + 03_incluidos_final.csv
+ arbitragem_kappa.tex. Execução com API real é operação manual do usuário."
git tag -l | tail -3
```

---

## Self-Review (autor do plano)

**Cobertura do spec:** §1 decisões (substitui humano/cego/binário/Opus/fusão/κ/reúso) → Tasks 1-5; §2 desvio declarado → Task 7 (§7+§11+versão 1.1); §3 arquitetura (prompt/batch_client retrocompat/arbitragem/agreement reuso) → Tasks 1-5; §4 fluxo → Task 5; §5 fusão (incl. arbitro_falha) → Task 3; §6 schema saída → Tasks 3,5; §7 κ honesto (binário, DRY) → Task 4; §8 custo → não-código (Task 8 nota); §9 testes → todas; §10 integração (Makefile, protocolo; prisma fora de escopo) → Tasks 6,7; §11 YAGNI (v0.4.0 intacta, prisma não tocado) → respeitado (nenhuma task toca revisao_*/prisma_flow); §12 sucesso → Task 8. Sem lacunas.

**Placeholders:** nenhum "TBD/TODO"; todo passo de código tem o código completo; comandos com saída esperada. A refatoração de `_CRITERIA` (Task 1) preserva o texto final do `build_system_block` (concatenação de core+contrato == texto original), então os testes de screening existentes seguem verdes sem alteração — explicitado.

**Consistência de tipos:** `build_arbiter_system_block()->list[dict]` (T1) injetado via `system_block` em `build_requests`/`screen_with_model` (T2, default None → `build_system_block()`); `soft_includes(df)->DataFrame` (reuso) alimenta `screen_with_model(...)->list[dict]` (T5); `fundir(screening: DataFrame, arb_by_rid: dict[str,dict])->DataFrame` (T3) consumido por `run` (T5); `kappa_table(arbitrado: DataFrame, output_table: Path)->None` (T4) idem; `cohen_kappa(a,b)` reusado de agreement com rótulos mapeados a {"incluir","excluir"} ⊂ labels de agreement (T4, justificado). `review_id = custom_id(cache_key(row))` idêntico em T3/T5 e ao screening/revisão. Colunas de saída (`decisao_arbitro`/`justificativa_arbitro`/`confianca_arbitro`/`decisao_final_arbitrada`/`origem_decisao`) idênticas entre T3 (cria) e T4/T5 (lê). Consistente.
