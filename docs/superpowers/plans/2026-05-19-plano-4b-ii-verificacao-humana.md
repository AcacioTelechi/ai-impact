# Plano 4b-ii — Verificação humana amostral (κ + acurácia) + protocolo v1.2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir o tooling determinístico e idempotente que sorteia a amostra de verificação humana (~110 de 790), exporta as duas planilhas (elegibilidade cega + auditoria de campos), ingere as planilhas preenchidas e emite κ humano×LLM + acurácia por campo, ajusta o PRISMA para anotar o estado interino, e amenda o protocolo para v1.2.

**Architecture:** Três scripts novos em `scripts/extraction/` (`verify_sample`, `verify_export`, `verify_ingest`), um ajuste retrocompatível em `scripts/screening/prisma_flow.py`, targets do Makefile, e a emenda prosa do protocolo. Reusa `revisao_export.merge_preserve` (preservação de input humano), `revisao_ingest.normalize_decisao` (i/e/incluir/excluir), `agreement.cohen_kappa` (sklearn, adaptado para 2 labels) e o padrão `.tex` de `arbitragem.kappa_table`.

**Tech Stack:** Python 3.12 · `uv`-managed venv · pandas · numpy (RNG estável) · sklearn (`cohen_kappa_score`, `confusion_matrix`) · scipy (`stats.binomtest` ou cálculo Wilson manual) · pytest. **NUNCA usar `uv run` em comandos ad-hoc** — sempre `source .venv/bin/activate` antes de `pytest`/`python -m`. O Makefile usa `$(PYTHON) := uv run python` por convenção do projeto (preservar).

**Spec:** `docs/superpowers/specs/2026-05-19-plano-4b-ii-verificacao-humana-design.md`

---

## File Structure

**Criar:**
- `scripts/extraction/verify_sample.py` — congela frame (790 review_ids) e sorteia amostra estratificada determinística.
- `scripts/extraction/verify_export.py` — produz as 2 planilhas (cega + auditoria) preservando input humano.
- `scripts/extraction/verify_ingest.py` — calcula κ + acurácia, escreve `.tex` e CSV anotado.
- `tests/extraction/test_verify_sample.py`
- `tests/extraction/test_verify_export.py`
- `tests/extraction/test_verify_ingest.py`
- `tests/extraction/test_prisma_flow_interino.py`

**Modificar:**
- `scripts/screening/prisma_flow.py` — `compute_counts` ganha parâmetro opcional `--extraction`; template TikZ ganha caixa de anotação condicional.
- `Makefile` — targets `verify-sample`, `verify-export`, `verify-ingest`, agrupador `verify`.
- `protocols/slr_protocol.md` — versão → 1.2; §7 referencia §8; §8 absorve nota interina + subseção "Verificação humana amostral"; §11 ganha bullet de limitação da verificação amostral.

**Cada arquivo tem uma responsabilidade clara:** `verify_sample` amostra; `verify_export` formata I/O com humano; `verify_ingest` calcula métricas. Bordas finas — cada um lê só o que precisa.

---

## Pré-requisitos

- Branch atual: `plano-4b-ii-verificacao-humana` (criada no merge da spec, commit `3cc0767`).
- Suite baseline: 206 testes verdes (pós Plano 4b-i, merge `093a1d6`).
- `data/processed/06_extraction.csv` presente (852 linhas, 790 com extração, 62 `parse_fail`).
- `data/processed/04_fulltext_manifest.csv` corrigido pelo Plano 4b-i (121 pdf / 731 abstract).
- Antes de qualquer trabalho, o subagente deve rodar `source .venv/bin/activate && pytest -q` e confirmar 206 verdes; aborta se vermelho.

---

## Task 1 — `verify_sample.py`: snapshot do frame + amostragem estratificada determinística

**Files:**
- Create: `scripts/extraction/verify_sample.py`
- Create: `tests/extraction/test_verify_sample.py`

**Contrato:**
- CLI: `python -m scripts.extraction.verify_sample --extraction <06_extraction.csv> --frame <07_amostra_frame.csv> --sample <07_amostra_verificacao.csv> [--seed 42]`.
- Idempotência: se `--frame` já existe → carrega (não recomputa); senão filtra `nota_extracao != "parse_fail"` e grava. Se `--sample` já existe → carrega (não re-sorteia); senão sorteia e grava.
- Frame CSV: `review_id, text_source, confianca_extracao, elegivel, motivo_exclusao` (subset de `06_extraction.csv`; `review_id` derivado via `custom_id(cache_key(row))` do `batch_client`).
- Amostra CSV: `review_id, estrato, tipo`. `tipo ∈ {"exclusao","inclusao"}`. `estrato = "excluir"` p/ exclusões; `f"{text_source}_{confianca_bin}"` p/ inclusões (`baixa<0.6`, `media∈[0.6,0.8]`, `alta>0.8`).
- Inclusões: amostragem proporcional por estrato com `n_alvo = max(ceil(0.10*n_estrato), min(5, n_estrato))`; `numpy.random.default_rng(seed)`.

- [ ] **Step 1: Escrever testes que falham**

Criar `tests/extraction/test_verify_sample.py`:

```python
"""Testes do verify_sample: frame snapshot + amostragem estratificada determinística."""
from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd
import pytest


def _mk_extraction(n_inc_pdf_alta=20, n_inc_pdf_baixa=10,
                   n_inc_abs_media=30, n_excl=5,
                   n_parse_fail=3, tmp_path: Path | None = None) -> Path:
    """Fabrica um 06_extraction.csv mínimo com mix controlado de estratos."""
    rows = []
    counter = 0

    def add(elegivel, motivo, text_source, confianca, nota_extracao):
        nonlocal counter
        counter += 1
        rows.append({
            "id": f"s-{counter}", "doi": f"d{counter}",
            "titulo": f"t{counter}", "autores": "x",
            "ano": "2024", "periodico": "j", "tipo_pub": "j",
            "pais_estudo": "", "periodo_dados": "", "janela": "",
            "pre_pos_chatgpt": "", "tecnologia_focada": "",
            "tipo_estudo": "", "metodo_empirico": "",
            "unidade_analise": "", "fonte_dados": "",
            "mec_deslocamento": "", "mec_reinstalacao": "",
            "mec_complementaridade": "", "mec_demanda_agregada": "",
            "mec_outros": "", "sinal_efeito": "",
            "magnitude_reportada": "", "magnitude_normalizada": "",
            "ocupacoes_afetadas": "", "polarizacao": "",
            "horizonte": "", "score_qualidade": "",
            "limitacoes_declaradas": "", "replicavel": "",
            "revisado_por_pares": "",
            "nota_extracao": nota_extracao,
            "citacoes_chave": "", "revisto_humano": "",
            "elegivel": elegivel, "motivo_exclusao": motivo,
            "text_source": text_source,
            "confianca_extracao": str(confianca),
        })

    for _ in range(n_inc_pdf_alta):
        add("sim", "", "pdf", 0.90, "")
    for _ in range(n_inc_pdf_baixa):
        add("sim", "", "pdf", 0.40, "")
    for _ in range(n_inc_abs_media):
        add("sim", "", "abstract", 0.70, "")
    for _ in range(n_excl):
        add("nao", "fora do escopo", "abstract", 0.80, "")
    for _ in range(n_parse_fail):
        add("sim", "", "abstract", 0.0, "parse_fail")

    p = (tmp_path or Path("/tmp")) / "06_extraction.csv"
    pd.DataFrame(rows).to_csv(p, index=False, encoding="utf-8")
    return p


def test_frame_exclui_parse_fail(tmp_path):
    from scripts.extraction import verify_sample as V
    ext = _mk_extraction(tmp_path=tmp_path)
    frame = tmp_path / "frame.csv"
    sample = tmp_path / "sample.csv"
    V.run(extraction=ext, frame=frame, sample=sample, seed=42)

    df = pd.read_csv(frame, encoding="utf-8", keep_default_na=False)
    assert len(df) == 65  # 60 inc + 5 excl, 3 parse_fail excluídos
    assert "nota_extracao" not in df.columns  # filtrado, não preservado
    assert set(df.columns) == {
        "review_id", "text_source", "confianca_extracao",
        "elegivel", "motivo_exclusao",
    }


def test_amostra_100pct_exclusoes(tmp_path):
    from scripts.extraction import verify_sample as V
    ext = _mk_extraction(n_excl=5, tmp_path=tmp_path)
    frame = tmp_path / "frame.csv"
    sample = tmp_path / "sample.csv"
    V.run(extraction=ext, frame=frame, sample=sample, seed=42)

    sdf = pd.read_csv(sample, encoding="utf-8", keep_default_na=False)
    exclusoes = sdf[sdf["tipo"] == "exclusao"]
    assert len(exclusoes) == 5
    assert (exclusoes["estrato"] == "excluir").all()


def test_amostra_inclusoes_estratificada_com_piso(tmp_path):
    """Estrato pdf_alta tem 20 → ceil(0.10*20)=2, piso min(5,20)=5 → 5."""
    from scripts.extraction import verify_sample as V
    ext = _mk_extraction(n_inc_pdf_alta=20, n_inc_pdf_baixa=10,
                         n_inc_abs_media=30, n_excl=0, n_parse_fail=0,
                         tmp_path=tmp_path)
    frame = tmp_path / "frame.csv"
    sample = tmp_path / "sample.csv"
    V.run(extraction=ext, frame=frame, sample=sample, seed=42)

    sdf = pd.read_csv(sample, encoding="utf-8", keep_default_na=False)
    inc = sdf[sdf["tipo"] == "inclusao"]
    counts = inc["estrato"].value_counts().to_dict()
    # 20 → piso 5; 10 → piso 5; 30 → ceil(3) vs min(5,30)=5 → 5
    assert counts.get("pdf_alta") == 5
    assert counts.get("pdf_baixa") == 5
    assert counts.get("abstract_media") == 5


def test_idempotencia_snapshot(tmp_path):
    """Se frame/sample já existem, nova chamada não muda nada."""
    from scripts.extraction import verify_sample as V
    ext = _mk_extraction(tmp_path=tmp_path)
    frame = tmp_path / "frame.csv"
    sample = tmp_path / "sample.csv"
    V.run(extraction=ext, frame=frame, sample=sample, seed=42)
    h1 = frame.read_bytes(), sample.read_bytes()
    # Simula re-rodada do extract: muda nota_extracao em 2 linhas
    df = pd.read_csv(ext, encoding="utf-8", keep_default_na=False)
    df.loc[df["nota_extracao"] == "parse_fail", "nota_extracao"] = ""
    df.to_csv(ext, index=False, encoding="utf-8")
    V.run(extraction=ext, frame=frame, sample=sample, seed=42)
    h2 = frame.read_bytes(), sample.read_bytes()
    assert h1 == h2  # byte-idêntico


def test_seed_determinismo(tmp_path):
    """Mesma seed em executions limpas → mesma amostra (em diretórios separados)."""
    from scripts.extraction import verify_sample as V
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    ext_a = _mk_extraction(tmp_path=a)
    ext_b = _mk_extraction(tmp_path=b)
    V.run(extraction=ext_a, frame=a / "f.csv", sample=a / "s.csv", seed=42)
    V.run(extraction=ext_b, frame=b / "f.csv", sample=b / "s.csv", seed=42)
    assert (a / "s.csv").read_bytes() == (b / "s.csv").read_bytes()
```

- [ ] **Step 2: Confirmar que os testes falham (módulo ausente)**

```
source .venv/bin/activate && pytest tests/extraction/test_verify_sample.py -q
```
Expected: 5 FAILED, todos por `ModuleNotFoundError: No module named 'scripts.extraction.verify_sample'`.

- [ ] **Step 3: Implementar `verify_sample.py`**

Criar `scripts/extraction/verify_sample.py`:

```python
"""Congela o quadro amostral da verificação humana (4b-ii) e sorteia a amostra.

Idempotente: se os snapshots já existem, recarrega-os e não re-sorteia. Isso
sobrevive à re-rodada idempotente de `make extract-llm` que recuperará os 61
estudos sem extração — o frame fica nos 790 da 1ª rodada por decisão da spec.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.screening.llm.batch_client import cache_key, custom_id

_FRAME_COLS = ["review_id", "text_source", "confianca_extracao",
               "elegivel", "motivo_exclusao"]


def _conf_bin(x: float) -> str:
    if x < 0.6:
        return "baixa"
    if x <= 0.8:
        return "media"
    return "alta"


def _build_frame(extraction_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(extraction_csv, encoding="utf-8", keep_default_na=False)
    df = df[df["nota_extracao"] != "parse_fail"].copy()
    # cache_key/custom_id são definidos sobre {doi,title,year}; aqui o corpus
    # de extração usa {doi, titulo, ano} → adaptamos as colunas.
    df_kk = df.rename(columns={"titulo": "title", "ano": "year"})
    df["review_id"] = df_kk.apply(
        lambda r: custom_id(cache_key(r)), axis=1,
    )
    df["confianca_extracao"] = pd.to_numeric(
        df["confianca_extracao"], errors="coerce",
    ).fillna(0.0)
    return df[_FRAME_COLS].reset_index(drop=True)


def _stratify_inclusoes(frame: pd.DataFrame, rng: np.random.Generator,
                        fracao: float = 0.10) -> pd.DataFrame:
    inc = frame[(frame["elegivel"] == "sim") & (frame["motivo_exclusao"] == "")].copy()
    inc["confianca_bin"] = inc["confianca_extracao"].apply(_conf_bin)
    inc["estrato"] = inc["text_source"] + "_" + inc["confianca_bin"]
    out = []
    for est, g in inc.groupby("estrato", sort=True):
        n = len(g)
        alvo = max(math.ceil(fracao * n), min(5, n))
        idx = rng.choice(g.index.to_numpy(), size=alvo, replace=False)
        out.append(g.loc[idx, ["review_id", "estrato"]])
    res = pd.concat(out, ignore_index=True) if out else pd.DataFrame(
        columns=["review_id", "estrato"],
    )
    res["tipo"] = "inclusao"
    return res


def _all_exclusoes(frame: pd.DataFrame) -> pd.DataFrame:
    excl = frame[(frame["elegivel"] != "sim") | (frame["motivo_exclusao"] != "")]
    out = pd.DataFrame({
        "review_id": excl["review_id"].values,
        "estrato": "excluir",
        "tipo": "exclusao",
    })
    return out


def run(extraction: Path, frame: Path, sample: Path, seed: int = 42) -> None:
    # Frame: snapshot
    if frame.exists():
        frame_df = pd.read_csv(frame, encoding="utf-8", keep_default_na=False)
        print(f"  frame carregado de {frame} ({len(frame_df)} linhas)")
    else:
        frame_df = _build_frame(extraction)
        frame.parent.mkdir(parents=True, exist_ok=True)
        frame_df.to_csv(frame, index=False, encoding="utf-8")
        print(f"  frame gravado em {frame} ({len(frame_df)} linhas)")

    # Amostra: snapshot
    if sample.exists():
        sdf = pd.read_csv(sample, encoding="utf-8", keep_default_na=False)
        print(f"  amostra carregada de {sample} ({len(sdf)} linhas)")
        return

    rng = np.random.default_rng(seed)
    exc = _all_exclusoes(frame_df)
    inc = _stratify_inclusoes(frame_df, rng)
    sdf = pd.concat([exc, inc], ignore_index=True)
    sample.parent.mkdir(parents=True, exist_ok=True)
    sdf.to_csv(sample, index=False, encoding="utf-8")
    print(
        f"  amostra gravada em {sample}: "
        f"{(sdf['tipo'] == 'exclusao').sum()} exclusões (100%) + "
        f"{(sdf['tipo'] == 'inclusao').sum()} inclusões (estratificado, seed={seed})"
    )


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Sorteia a amostra de verificação humana (4b-ii).")
    p.add_argument("--extraction", type=Path, required=True)
    p.add_argument("--frame", type=Path, required=True)
    p.add_argument("--sample", type=Path, required=True)
    p.add_argument("--seed", type=int, default=42)
    a = p.parse_args(argv)
    run(extraction=a.extraction, frame=a.frame, sample=a.sample, seed=a.seed)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
```

- [ ] **Step 4: Rodar os testes e confirmar verdes**

```
source .venv/bin/activate && pytest tests/extraction/test_verify_sample.py -q
```
Expected: 5 passed.

- [ ] **Step 5: Adicionar target ao Makefile**

Em `Makefile`, após o bloco `extract-llm` (linha ~148), inserir:

```makefile
.PHONY: verify-sample
verify-sample:
	$(PYTHON) -m scripts.extraction.verify_sample \
	    --extraction $(DATA_PROC)/06_extraction.csv \
	    --frame $(DATA_PROC)/07_amostra_frame.csv \
	    --sample $(DATA_PROC)/07_amostra_verificacao.csv
```

- [ ] **Step 6: Rodar contra dado real (smoke-test)**

```
source .venv/bin/activate && make verify-sample
```
Expected: imprime "frame gravado em data/processed/07_amostra_frame.csv (790 linhas)" e "amostra gravada em data/processed/07_amostra_verificacao.csv: 34 exclusões (100%) + ~76 inclusões (estratificado, seed=42)". Os números exatos dependem do `06_extraction.csv` corrigido pelo 4b-i; aceite qualquer valor coerente com a spec (frame ∈ [780, 800], amostra ∈ [100, 130]).

- [ ] **Step 7: Commit**

```bash
git add scripts/extraction/verify_sample.py tests/extraction/test_verify_sample.py Makefile \
        data/processed/07_amostra_frame.csv data/processed/07_amostra_verificacao.csv
git commit -m "feat(4b-ii): verify_sample — frame snapshot + amostragem estratificada idempotente

- 100% das exclusões + ~10% das inclusões estratificado por text_source × confiança.
- Snapshot do frame e da amostra → re-rodada do extract não muda a amostra.
- Seed=42 reprodutível.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2 — `verify_export.py`: planilhas (elegibilidade cega + auditoria de campos)

**Files:**
- Create: `scripts/extraction/verify_export.py`
- Create: `tests/extraction/test_verify_export.py`

**Contrato:**
- CLI: `python -m scripts.extraction.verify_export --extraction <06_extraction.csv> --corpus <03_incluidos_final.csv> --sample <07_amostra_verificacao.csv> --sheet-eleg <07_eleg_cega.csv> --sheet-aud <07_auditoria_campos.csv>`.
- Planilha (a) — cega, ~110 linhas: `review_id, decisao_humana, nota_humana, year, title, authors, venue, abstract, text_source, criterios_ref`. **Nenhuma** coluna LLM (`elegivel`, `motivo_exclusao`, decisões do screening, campos extraídos).
- Planilha (b) — auditoria, só inclusões amostradas: cabeçalho do registro + `(campo_llm, campo_auditoria, campo_correto)` × 6 campos críticos (`pre_pos_chatgpt`, `janela`, `sinal_efeito`, `tipo_estudo`, `polarizacao`, `score_qualidade`) + `nota_auditoria`.
- Idempotência: se a planilha já existe, faz `merge_preserve` (preserva `decisao_humana`, `nota_humana`, `<campo>_auditoria`, `<campo>_correto`, `nota_auditoria` por `review_id`) e gera backup `.bak-TS.csv` + `.state.json`.
- `criterios_ref`: string única curta = "Estudo empírico/teórico sobre impacto da IA no mercado de trabalho (emprego/salários/ocupações), publicado em periódico ou working paper; janela 2013–2025; texto disponível em inglês/português/espanhol/francês. Para detalhes, ver protocolo §5."

- [ ] **Step 1: Escrever testes que falham**

Criar `tests/extraction/test_verify_export.py`:

```python
"""Testes do verify_export: planilha cega + planilha de auditoria + preservação."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest


def _mk_inputs(tmp_path: Path):
    # corpus tem o lado bibliográfico
    corpus_rows = [
        {"doi": f"d{i}", "title": f"Title {i}", "year": 2024,
         "authors": "X", "venue": "J", "abstract": f"Abs {i}"}
        for i in range(1, 11)
    ]
    corpus = pd.DataFrame(corpus_rows)

    # extraction tem o lado LLM (campos críticos)
    extr_rows = []
    for i in range(1, 11):
        extr_rows.append({
            "id": f"s-{i}", "doi": f"d{i}", "titulo": f"Title {i}",
            "ano": 2024, "elegivel": "sim" if i <= 8 else "nao",
            "motivo_exclusao": "" if i <= 8 else "fora do escopo",
            "text_source": "pdf" if i % 2 else "abstract",
            "confianca_extracao": 0.8, "nota_extracao": "",
            "pre_pos_chatgpt": "pos", "janela": "2023-2024",
            "sinal_efeito": "negativo", "tipo_estudo": "empirico",
            "polarizacao": "sim", "score_qualidade": "4",
        })
    extr = pd.DataFrame(extr_rows)

    # amostra inclui 2 exclusões (i=9,10) + 3 inclusões (i=1,2,3)
    from scripts.screening.llm.batch_client import cache_key, custom_id

    def rid(i: int) -> str:
        return custom_id(cache_key(pd.Series({
            "doi": f"d{i}", "title": f"Title {i}", "year": 2024,
        })))

    sample = pd.DataFrame([
        {"review_id": rid(9), "estrato": "excluir", "tipo": "exclusao"},
        {"review_id": rid(10), "estrato": "excluir", "tipo": "exclusao"},
        {"review_id": rid(1), "estrato": "pdf_alta", "tipo": "inclusao"},
        {"review_id": rid(2), "estrato": "abstract_alta", "tipo": "inclusao"},
        {"review_id": rid(3), "estrato": "pdf_alta", "tipo": "inclusao"},
    ])

    cp = tmp_path / "corpus.csv"
    ep = tmp_path / "extr.csv"
    sp = tmp_path / "sample.csv"
    corpus.to_csv(cp, index=False, encoding="utf-8")
    extr.to_csv(ep, index=False, encoding="utf-8")
    sample.to_csv(sp, index=False, encoding="utf-8")
    return cp, ep, sp


def test_planilha_eleg_e_cega(tmp_path):
    from scripts.extraction import verify_export as V
    corpus, extr, sample = _mk_inputs(tmp_path)
    eleg = tmp_path / "eleg.csv"
    aud = tmp_path / "aud.csv"
    V.run(extraction=extr, corpus=corpus, sample=sample,
          sheet_eleg=eleg, sheet_aud=aud)

    df = pd.read_csv(eleg, encoding="utf-8", keep_default_na=False)
    assert len(df) == 5
    assert set(df.columns) == {
        "review_id", "decisao_humana", "nota_humana",
        "year", "title", "authors", "venue", "abstract",
        "text_source", "criterios_ref",
    }
    # Cegueira: nenhuma coluna LLM
    for forbidden in ("elegivel", "motivo_exclusao",
                      "decisao_arbitro", "pre_pos_chatgpt",
                      "sinal_efeito", "score_qualidade"):
        assert forbidden not in df.columns


def test_planilha_aud_so_inclusoes(tmp_path):
    from scripts.extraction import verify_export as V
    corpus, extr, sample = _mk_inputs(tmp_path)
    eleg = tmp_path / "eleg.csv"
    aud = tmp_path / "aud.csv"
    V.run(extraction=extr, corpus=corpus, sample=sample,
          sheet_eleg=eleg, sheet_aud=aud)

    df = pd.read_csv(aud, encoding="utf-8", keep_default_na=False)
    assert len(df) == 3  # apenas as 3 inclusões
    # Cabeçalho + 6 campos × 3 colunas + nota
    for campo in ("pre_pos_chatgpt", "janela", "sinal_efeito",
                  "tipo_estudo", "polarizacao", "score_qualidade"):
        assert f"{campo}_llm" in df.columns
        assert f"{campo}_auditoria" in df.columns
        assert f"{campo}_correto" in df.columns
    assert "nota_auditoria" in df.columns
    # Valores LLM presentes (não-vazios)
    assert (df["pre_pos_chatgpt_llm"] == "pos").all()


def test_merge_preserva_input_humano(tmp_path):
    """Segunda rodada preserva decisao_humana e auditoria preenchidas."""
    from scripts.extraction import verify_export as V
    corpus, extr, sample = _mk_inputs(tmp_path)
    eleg = tmp_path / "eleg.csv"
    aud = tmp_path / "aud.csv"
    V.run(extraction=extr, corpus=corpus, sample=sample,
          sheet_eleg=eleg, sheet_aud=aud)

    # Humano preenche 1 linha em cada
    df_e = pd.read_csv(eleg, encoding="utf-8", keep_default_na=False)
    df_e.loc[0, "decisao_humana"] = "incluir"
    df_e.loc[0, "nota_humana"] = "comentário"
    df_e.to_csv(eleg, index=False, encoding="utf-8")
    df_a = pd.read_csv(aud, encoding="utf-8", keep_default_na=False)
    df_a.loc[0, "pre_pos_chatgpt_auditoria"] = "ok"
    df_a.loc[0, "sinal_efeito_auditoria"] = "erro"
    df_a.loc[0, "sinal_efeito_correto"] = "positivo"
    df_a.to_csv(aud, index=False, encoding="utf-8")

    V.run(extraction=extr, corpus=corpus, sample=sample,
          sheet_eleg=eleg, sheet_aud=aud)

    df_e2 = pd.read_csv(eleg, encoding="utf-8", keep_default_na=False)
    df_a2 = pd.read_csv(aud, encoding="utf-8", keep_default_na=False)
    assert df_e2.loc[df_e2["review_id"] == df_e.loc[0, "review_id"],
                     "decisao_humana"].iloc[0] == "incluir"
    assert df_a2.loc[df_a2["review_id"] == df_a.loc[0, "review_id"],
                     "sinal_efeito_correto"].iloc[0] == "positivo"


def test_backup_criado_em_re_export(tmp_path):
    from scripts.extraction import verify_export as V
    corpus, extr, sample = _mk_inputs(tmp_path)
    eleg = tmp_path / "eleg.csv"
    aud = tmp_path / "aud.csv"
    V.run(extraction=extr, corpus=corpus, sample=sample,
          sheet_eleg=eleg, sheet_aud=aud)
    V.run(extraction=extr, corpus=corpus, sample=sample,
          sheet_eleg=eleg, sheet_aud=aud)
    backups_e = list(tmp_path.glob("eleg.bak-*.csv"))
    backups_a = list(tmp_path.glob("aud.bak-*.csv"))
    assert backups_e and backups_a
```

- [ ] **Step 2: Confirmar que os testes falham**

```
source .venv/bin/activate && pytest tests/extraction/test_verify_export.py -q
```
Expected: 4 FAILED por `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `verify_export.py`**

Criar `scripts/extraction/verify_export.py`:

```python
"""Gera as duas planilhas da verificação humana amostral (4b-ii).

Planilha (a) — elegibilidade CEGA: o humano decide incluir/excluir sem ver
nenhuma coluna do LLM (decisão, motivo, campos extraídos). Insumo do κ.

Planilha (b) — auditoria de campos: o humano vê o valor do LLM + a fonte e
marca ok/erro (com o valor correto opcional). Insumo da acurácia por campo.

Idempotente: preserva input humano via merge_preserve; backup .bak-TS.csv.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import pandas as pd

from scripts.screening.llm.batch_client import cache_key, custom_id

CAMPOS_CRITICOS = (
    "pre_pos_chatgpt", "janela", "sinal_efeito",
    "tipo_estudo", "polarizacao", "score_qualidade",
)

ELEG_COLS = [
    "review_id", "decisao_humana", "nota_humana",
    "year", "title", "authors", "venue", "abstract",
    "text_source", "criterios_ref",
]

_CRITERIOS_REF = (
    "Estudo empírico/teórico sobre impacto da IA no mercado de trabalho "
    "(emprego/salários/ocupações), publicado em periódico ou working paper; "
    "janela 2013–2025; texto em inglês/português/espanhol/francês. "
    "Para detalhes, ver protocolo §5."
)


def _state_path(sheet: Path) -> Path:
    return sheet.with_suffix(".state.json")


def _backup(sheet: Path, ts: str) -> None:
    if sheet.exists():
        bak = sheet.with_suffix(f".bak-{ts}.csv")
        bak.write_bytes(sheet.read_bytes())


def _merge_preserve(fresh: pd.DataFrame, sheet: Path,
                    human_cols: list[str]) -> pd.DataFrame:
    if not sheet.exists():
        return fresh.reset_index(drop=True)
    prev = pd.read_csv(sheet, encoding="utf-8", keep_default_na=False)
    prev_idx = prev.set_index("review_id")
    out = fresh.copy()
    for col in human_cols:
        def _prev(rid: str, _col=col) -> str:
            if rid in prev_idx.index:
                val = prev_idx.loc[rid, _col] if _col in prev_idx.columns else ""
                return "" if pd.isna(val) else str(val)
            return ""
        out[col] = out["review_id"].map(_prev)
    return out.reset_index(drop=True)


def _build_eleg_sheet(corpus: pd.DataFrame, extraction: pd.DataFrame,
                      sample: pd.DataFrame) -> pd.DataFrame:
    # Mapa review_id → corpus row (lado bibliográfico) + extraction (text_source)
    corp = corpus.copy()
    corp["review_id"] = corp.apply(
        lambda r: custom_id(cache_key(r)), axis=1,
    )
    corp_idx = corp.set_index("review_id")

    ext = extraction.rename(columns={"titulo": "title", "ano": "year"}).copy()
    ext["review_id"] = ext.apply(
        lambda r: custom_id(cache_key(r)), axis=1,
    )
    ts_by_rid = ext.set_index("review_id")["text_source"].to_dict()

    rows = []
    for rid in sample["review_id"]:
        if rid in corp_idx.index:
            row = corp_idx.loc[rid]
            rows.append({
                "review_id": rid,
                "decisao_humana": "", "nota_humana": "",
                "year": row.get("year", ""),
                "title": row.get("title", ""),
                "authors": row.get("authors", ""),
                "venue": row.get("venue", ""),
                "abstract": row.get("abstract", ""),
                "text_source": ts_by_rid.get(rid, ""),
                "criterios_ref": _CRITERIOS_REF,
            })
        else:
            # Sem registro no corpus → sinaliza para o humano (raro)
            rows.append({
                "review_id": rid, "decisao_humana": "", "nota_humana": "",
                "year": "", "title": "[review_id sem corpus]",
                "authors": "", "venue": "", "abstract": "",
                "text_source": ts_by_rid.get(rid, ""),
                "criterios_ref": _CRITERIOS_REF,
            })
    return pd.DataFrame(rows, columns=ELEG_COLS)


def _build_aud_sheet(corpus: pd.DataFrame, extraction: pd.DataFrame,
                     sample: pd.DataFrame) -> pd.DataFrame:
    inc_ids = set(sample.loc[sample["tipo"] == "inclusao", "review_id"])
    corp = corpus.copy()
    corp["review_id"] = corp.apply(
        lambda r: custom_id(cache_key(r)), axis=1,
    )
    corp_idx = corp.set_index("review_id")

    ext = extraction.rename(columns={"titulo": "title", "ano": "year"}).copy()
    ext["review_id"] = ext.apply(
        lambda r: custom_id(cache_key(r)), axis=1,
    )
    ext_idx = ext.set_index("review_id")

    rows = []
    for rid in sample["review_id"]:
        if rid not in inc_ids:
            continue
        row = {
            "review_id": rid,
            "year": corp_idx.loc[rid, "year"] if rid in corp_idx.index else "",
            "title": corp_idx.loc[rid, "title"] if rid in corp_idx.index else "",
            "doi": corp_idx.loc[rid, "doi"] if rid in corp_idx.index
                   and "doi" in corp_idx.columns else "",
            "text_source": ext_idx.loc[rid, "text_source"] if rid in ext_idx.index else "",
        }
        for c in CAMPOS_CRITICOS:
            row[f"{c}_llm"] = ext_idx.loc[rid, c] if rid in ext_idx.index else ""
            row[f"{c}_auditoria"] = ""
            row[f"{c}_correto"] = ""
        row["nota_auditoria"] = ""
        rows.append(row)
    cols = ["review_id", "year", "title", "doi", "text_source"]
    for c in CAMPOS_CRITICOS:
        cols += [f"{c}_llm", f"{c}_auditoria", f"{c}_correto"]
    cols.append("nota_auditoria")
    return pd.DataFrame(rows, columns=cols)


def run(extraction: Path, corpus: Path, sample: Path,
        sheet_eleg: Path, sheet_aud: Path) -> None:
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    ext_df = pd.read_csv(extraction, encoding="utf-8", keep_default_na=False)
    corp_df = pd.read_csv(corpus, encoding="utf-8", keep_default_na=False)
    sample_df = pd.read_csv(sample, encoding="utf-8", keep_default_na=False)

    fresh_eleg = _build_eleg_sheet(corp_df, ext_df, sample_df)
    fresh_aud = _build_aud_sheet(corp_df, ext_df, sample_df)

    eleg_human_cols = ["decisao_humana", "nota_humana"]
    aud_human_cols = [f"{c}_auditoria" for c in CAMPOS_CRITICOS] \
        + [f"{c}_correto" for c in CAMPOS_CRITICOS] \
        + ["nota_auditoria"]

    merged_eleg = _merge_preserve(fresh_eleg, sheet_eleg, eleg_human_cols)
    merged_aud = _merge_preserve(fresh_aud, sheet_aud, aud_human_cols)

    _backup(sheet_eleg, ts)
    _backup(sheet_aud, ts)
    sheet_eleg.parent.mkdir(parents=True, exist_ok=True)
    sheet_aud.parent.mkdir(parents=True, exist_ok=True)
    merged_eleg.to_csv(sheet_eleg, index=False, encoding="utf-8")
    merged_aud.to_csv(sheet_aud, index=False, encoding="utf-8")

    _state_path(sheet_eleg).write_text(
        json.dumps({"exportado_em": ts, "n_linhas": len(merged_eleg)},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _state_path(sheet_aud).write_text(
        json.dumps({"exportado_em": ts, "n_linhas": len(merged_aud)},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Verify export: eleg {len(merged_eleg)} | aud {len(merged_aud)}")
    print(f"  → {sheet_eleg}\n  → {sheet_aud}")
    print("Instruções: auditoria ∈ {ok, erro}; vazio = pendente; "
          "correto = valor que deveria estar; nota_auditoria = comentário livre.")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Exporta planilhas da verificação humana (4b-ii).")
    p.add_argument("--extraction", type=Path, required=True)
    p.add_argument("--corpus", type=Path, required=True)
    p.add_argument("--sample", type=Path, required=True)
    p.add_argument("--sheet-eleg", type=Path, required=True)
    p.add_argument("--sheet-aud", type=Path, required=True)
    a = p.parse_args(argv)
    run(extraction=a.extraction, corpus=a.corpus, sample=a.sample,
        sheet_eleg=a.sheet_eleg, sheet_aud=a.sheet_aud)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
```

- [ ] **Step 4: Rodar testes e confirmar verdes**

```
source .venv/bin/activate && pytest tests/extraction/test_verify_export.py -q
```
Expected: 4 passed.

- [ ] **Step 5: Adicionar target ao Makefile**

Após `verify-sample` no Makefile:

```makefile
.PHONY: verify-export
verify-export: verify-sample
	$(PYTHON) -m scripts.extraction.verify_export \
	    --extraction $(DATA_PROC)/06_extraction.csv \
	    --corpus $(DATA_PROC)/03_incluidos_final.csv \
	    --sample $(DATA_PROC)/07_amostra_verificacao.csv \
	    --sheet-eleg $(DATA_PROC)/07_eleg_cega.csv \
	    --sheet-aud $(DATA_PROC)/07_auditoria_campos.csv
```

- [ ] **Step 6: Smoke-test contra dados reais**

```
source .venv/bin/activate && make verify-export
```
Expected: "Verify export: eleg ~110 | aud ~76" + caminhos. Inspecionar `head -2 data/processed/07_eleg_cega.csv` para confirmar visualmente que **não** há coluna `elegivel`/`motivo_exclusao`/campo extraído.

- [ ] **Step 7: Commit**

```bash
git add scripts/extraction/verify_export.py tests/extraction/test_verify_export.py Makefile \
        data/processed/07_eleg_cega.csv data/processed/07_eleg_cega.state.json \
        data/processed/07_auditoria_campos.csv data/processed/07_auditoria_campos.state.json
git commit -m "feat(4b-ii): verify_export — planilhas cega (κ) + auditoria (acurácia)

- Cegueira garantida: planilha (a) NÃO contém colunas LLM (elegivel, motivo,
  campos extraídos); humano decide independente → κ legítimo.
- Auditoria mostra valor LLM + fonte; 6 campos críticos × 3 colunas (llm/auditoria/correto).
- merge_preserve + .state.json + backup .bak-TS preservam input humano em re-runs.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3 — `verify_ingest.py`: κ humano×LLM + acurácia por campo + tabelas .tex

**Files:**
- Create: `scripts/extraction/verify_ingest.py`
- Create: `tests/extraction/test_verify_ingest.py`

**Contrato:**
- CLI: `python -m scripts.extraction.verify_ingest --extraction <06_extraction.csv> --sheet-eleg <07_eleg_cega.csv> --sheet-aud <07_auditoria_campos.csv> --kappa-table <text/tables/verificacao_kappa.tex> --acuracia-table <text/tables/verificacao_acuracia.tex> --annotated <07_verificacao_anotada.csv>`.
- Aborta com mensagem listando pendências se `decisao_humana` vazia ou `<campo>_auditoria` vazia.
- κ humano×LLM: labels `["incluir","excluir"]`; decisão LLM = `"incluir" if elegivel == "sim" else "excluir"`.
- Acurácia por campo: `#ok / (#ok+#erro)`; IC Wilson 95% para proporção binomial.
- Saídas: `verificacao_kappa.tex` (n, κ, IC concordância, matriz 2×2), `verificacao_acuracia.tex` (linha por campo + total), `07_verificacao_anotada.csv` (amostra + decisão humana + concordância + auditoria).

- [ ] **Step 1: Escrever testes que falham**

Criar `tests/extraction/test_verify_ingest.py`:

```python
"""Testes do verify_ingest: κ + acurácia + erros."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


def _setup(tmp_path: Path, human=None, audit=None):
    """human: dict review_id→decisao; audit: dict (rid, campo) → ok/erro."""
    from scripts.screening.llm.batch_client import cache_key, custom_id

    def rid(i: int) -> str:
        return custom_id(cache_key(pd.Series({
            "doi": f"d{i}", "title": f"T{i}", "year": 2024,
        })))

    extr_rows = []
    for i in range(1, 11):
        extr_rows.append({
            "id": f"s-{i}", "doi": f"d{i}", "titulo": f"T{i}", "ano": 2024,
            "elegivel": "sim" if i <= 8 else "nao",
            "motivo_exclusao": "" if i <= 8 else "x",
            "text_source": "pdf", "confianca_extracao": 0.9,
            "nota_extracao": "",
            "pre_pos_chatgpt": "pos", "janela": "2024",
            "sinal_efeito": "neg", "tipo_estudo": "emp",
            "polarizacao": "sim", "score_qualidade": "4",
        })
    extr_p = tmp_path / "extr.csv"
    pd.DataFrame(extr_rows).to_csv(extr_p, index=False, encoding="utf-8")

    eleg_rows = []
    for i in range(1, 11):
        eleg_rows.append({
            "review_id": rid(i),
            "decisao_humana": (human or {}).get(rid(i), ""),
            "nota_humana": "", "year": 2024, "title": f"T{i}",
            "authors": "", "venue": "", "abstract": "",
            "text_source": "pdf", "criterios_ref": "x",
        })
    eleg_p = tmp_path / "eleg.csv"
    pd.DataFrame(eleg_rows).to_csv(eleg_p, index=False, encoding="utf-8")

    campos = ("pre_pos_chatgpt", "janela", "sinal_efeito",
              "tipo_estudo", "polarizacao", "score_qualidade")
    aud_rows = []
    for i in range(1, 9):  # só inclusões
        r = {"review_id": rid(i), "year": 2024, "title": f"T{i}",
             "doi": f"d{i}", "text_source": "pdf"}
        for c in campos:
            r[f"{c}_llm"] = "x"
            r[f"{c}_auditoria"] = (audit or {}).get((rid(i), c), "")
            r[f"{c}_correto"] = ""
        r["nota_auditoria"] = ""
        aud_rows.append(r)
    aud_p = tmp_path / "aud.csv"
    pd.DataFrame(aud_rows).to_csv(aud_p, index=False, encoding="utf-8")

    return extr_p, eleg_p, aud_p, rid


def test_kappa_um_quando_humano_concorda(tmp_path):
    from scripts.extraction import verify_ingest as V
    _, _, _, rid = _setup(tmp_path)
    # Humano = LLM em todos: inc para 1..8, exc para 9..10
    human = {rid(i): ("incluir" if i <= 8 else "excluir") for i in range(1, 11)}
    audit = {(rid(i), c): "ok"
             for i in range(1, 9)
             for c in ("pre_pos_chatgpt", "janela", "sinal_efeito",
                       "tipo_estudo", "polarizacao", "score_qualidade")}
    extr_p, eleg_p, aud_p, _ = _setup(tmp_path, human=human, audit=audit)
    kappa_t = tmp_path / "k.tex"
    acur_t = tmp_path / "a.tex"
    ann = tmp_path / "ann.csv"
    V.run(extraction=extr_p, sheet_eleg=eleg_p, sheet_aud=aud_p,
          kappa_table=kappa_t, acuracia_table=acur_t, annotated=ann)
    txt = kappa_t.read_text(encoding="utf-8")
    assert "1.000" in txt  # κ = 1


def test_kappa_negativo_quando_humano_discorda(tmp_path):
    from scripts.extraction import verify_ingest as V
    _, _, _, rid = _setup(tmp_path)
    # Humano inverte 100%: exc para 1..8, inc para 9..10
    human = {rid(i): ("excluir" if i <= 8 else "incluir") for i in range(1, 11)}
    audit = {(rid(i), c): "ok"
             for i in range(1, 9)
             for c in ("pre_pos_chatgpt", "janela", "sinal_efeito",
                       "tipo_estudo", "polarizacao", "score_qualidade")}
    extr_p, eleg_p, aud_p, _ = _setup(tmp_path, human=human, audit=audit)
    kappa_t = tmp_path / "k.tex"
    acur_t = tmp_path / "a.tex"
    ann = tmp_path / "ann.csv"
    V.run(extraction=extr_p, sheet_eleg=eleg_p, sheet_aud=aud_p,
          kappa_table=kappa_t, acuracia_table=acur_t, annotated=ann)
    txt = kappa_t.read_text(encoding="utf-8")
    # κ < 0 (com sinal negativo no LaTeX)
    assert "-" in txt or "$-$" in txt


def test_aborta_pendencias_eleg(tmp_path):
    from scripts.extraction import verify_ingest as V
    # decisao_humana vazia em algumas
    human = {}  # tudo vazio
    audit = {(_id, c): "ok" for _id, c in []}
    extr_p, eleg_p, aud_p, _ = _setup(tmp_path, human=human, audit=audit)
    with pytest.raises(ValueError, match="decisao_humana"):
        V.run(extraction=extr_p, sheet_eleg=eleg_p, sheet_aud=aud_p,
              kappa_table=tmp_path / "k.tex",
              acuracia_table=tmp_path / "a.tex",
              annotated=tmp_path / "ann.csv")


def test_aborta_pendencias_aud(tmp_path):
    from scripts.extraction import verify_ingest as V
    _, _, _, rid = _setup(tmp_path)
    human = {rid(i): ("incluir" if i <= 8 else "excluir") for i in range(1, 11)}
    # Auditoria parcial: só metade dos campos
    audit = {(rid(i), "pre_pos_chatgpt"): "ok" for i in range(1, 9)}
    extr_p, eleg_p, aud_p, _ = _setup(tmp_path, human=human, audit=audit)
    with pytest.raises(ValueError, match="auditoria"):
        V.run(extraction=extr_p, sheet_eleg=eleg_p, sheet_aud=aud_p,
              kappa_table=tmp_path / "k.tex",
              acuracia_table=tmp_path / "a.tex",
              annotated=tmp_path / "ann.csv")


def test_acuracia_por_campo(tmp_path):
    """sinal_efeito tem 4 ok + 4 erro → acurácia 0.500; pre_pos tem 8 ok → 1.000."""
    from scripts.extraction import verify_ingest as V
    _, _, _, rid = _setup(tmp_path)
    human = {rid(i): ("incluir" if i <= 8 else "excluir") for i in range(1, 11)}
    audit = {}
    for i in range(1, 9):
        for c in ("pre_pos_chatgpt", "janela", "tipo_estudo",
                  "polarizacao", "score_qualidade"):
            audit[(rid(i), c)] = "ok"
        audit[(rid(i), "sinal_efeito")] = "ok" if i <= 4 else "erro"
    extr_p, eleg_p, aud_p, _ = _setup(tmp_path, human=human, audit=audit)
    acur_t = tmp_path / "a.tex"
    V.run(extraction=extr_p, sheet_eleg=eleg_p, sheet_aud=aud_p,
          kappa_table=tmp_path / "k.tex",
          acuracia_table=acur_t, annotated=tmp_path / "ann.csv")
    txt = acur_t.read_text(encoding="utf-8")
    assert "50.0\\%" in txt  # sinal_efeito
    assert "100.0\\%" in txt  # pre_pos_chatgpt
```

- [ ] **Step 2: Confirmar falhas**

```
source .venv/bin/activate && pytest tests/extraction/test_verify_ingest.py -q
```
Expected: 5 FAILED por `ModuleNotFoundError`.

- [ ] **Step 3: Implementar `verify_ingest.py`**

Criar `scripts/extraction/verify_ingest.py`:

```python
"""Calcula κ humano×LLM (elegibilidade cega) e acurácia por campo (auditoria).

Aborta com lista de pendências se as planilhas estiverem incompletas — nunca
calcula métricas silenciosamente com buracos.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import cohen_kappa_score, confusion_matrix

from scripts.screening.llm.batch_client import cache_key, custom_id
from scripts.screening.revisao_ingest import normalize_decisao

CAMPOS_CRITICOS = (
    "pre_pos_chatgpt", "janela", "sinal_efeito",
    "tipo_estudo", "polarizacao", "score_qualidade",
)
_LABELS = ["incluir", "excluir"]
_VALID_AUD = {"ok", "erro"}


def _wilson_95(k: int, n: int) -> tuple[float, float]:
    """IC Wilson 95% para proporção binomial. Devolve (lo, hi). n=0 → (nan,nan)."""
    if n == 0:
        return (float("nan"), float("nan"))
    z = 1.96
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _llm_decision_by_rid(extraction: pd.DataFrame) -> dict[str, str]:
    """review_id → 'incluir' / 'excluir' derivado de elegivel + motivo_exclusao."""
    ext = extraction.rename(columns={"titulo": "title", "ano": "year"}).copy()
    out: dict[str, str] = {}
    for _, r in ext.iterrows():
        rid = custom_id(cache_key(r))
        elig = str(r.get("elegivel", "")).strip()
        motivo = str(r.get("motivo_exclusao", "")).strip()
        out[rid] = "incluir" if (elig == "sim" and motivo == "") else "excluir"
    return out


def _validate_eleg(eleg: pd.DataFrame) -> None:
    pend = eleg.loc[
        eleg["decisao_humana"].astype(str).str.strip() == "",
        "review_id",
    ].tolist()
    if pend:
        raise ValueError(
            f"{len(pend)} linha(s) sem decisao_humana — preencher antes de calcular κ. "
            f"review_ids: {pend[:5]}{' …' if len(pend) > 5 else ''}"
        )


def _validate_aud(aud: pd.DataFrame) -> None:
    pend: list[tuple[str, str]] = []
    for _, r in aud.iterrows():
        for c in CAMPOS_CRITICOS:
            val = str(r.get(f"{c}_auditoria", "")).strip().lower()
            if val not in _VALID_AUD:
                pend.append((str(r["review_id"]), c))
    if pend:
        msg = ", ".join(f"{rid}/{c}" for rid, c in pend[:5])
        raise ValueError(
            f"{len(pend)} auditoria(s) pendente(s)/inválida(s) — esperado ok/erro. "
            f"Ex.: {msg}{' …' if len(pend) > 5 else ''}"
        )


def _kappa_tex(humano: list[str], llm: list[str], out: Path) -> None:
    n = len(humano)
    out.parent.mkdir(parents=True, exist_ok=True)
    if n == 0:
        out.write_text(
            "\\begin{tabular}{l}\\toprule Amostra vazia \\\\ \\bottomrule \\end{tabular}\n",
            encoding="utf-8",
        )
        return
    k = float(cohen_kappa_score(humano, llm, labels=_LABELS))
    agree = sum(a == b for a, b in zip(humano, llm))
    lo, hi = _wilson_95(agree, n)
    cm = confusion_matrix(humano, llm, labels=_LABELS)
    rows = []
    for i, lab in enumerate(_LABELS):
        cells = " & ".join(str(int(x)) for x in cm[i])
        rows.append(f"{lab} & {cells} \\\\")
    body = "\n".join(rows)
    tex = (
        "\\begin{table}[ht]\n\\centering\n"
        "\\caption{Verificação humana amostral — concordância humano $\\times$ LLM "
        f"na elegibilidade (n={n}; $\\kappa$ de Cohen = {k:.3f}; "
        f"concordância = {agree}/{n} = {agree / n * 100:.1f}\\%, IC 95\\% "
        f"[{lo * 100:.1f}\\%, {hi * 100:.1f}\\%])}}\n"
        "\\label{tab:verificacao-kappa}\n"
        "\\begin{tabular}{lcc}\n\\toprule\n"
        " & \\multicolumn{2}{c}{LLM} \\\\\n"
        "Humano & incluir & excluir \\\\\n\\midrule\n"
        f"{body}\n"
        "\\bottomrule\n\\end{tabular}\n\\end{table}\n"
    )
    out.write_text(tex, encoding="utf-8")


def _acuracia_tex(aud: pd.DataFrame, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    rows_tex = []
    total_ok = total_n = 0
    for c in CAMPOS_CRITICOS:
        col = aud[f"{c}_auditoria"].astype(str).str.strip().str.lower()
        ok = int((col == "ok").sum())
        err = int((col == "erro").sum())
        n = ok + err
        acc = ok / n if n else float("nan")
        lo, hi = _wilson_95(ok, n)
        rows_tex.append(
            f"{c.replace('_', '\\_')} & {n} & {ok} & {err} & "
            f"{acc * 100:.1f}\\% & [{lo * 100:.1f}\\%, {hi * 100:.1f}\\%] \\\\"
        )
        total_ok += ok
        total_n += n
    total_acc = total_ok / total_n if total_n else float("nan")
    lo_t, hi_t = _wilson_95(total_ok, total_n)
    rows_tex.append("\\midrule")
    rows_tex.append(
        f"\\textbf{{Total}} & {total_n} & {total_ok} & {total_n - total_ok} & "
        f"{total_acc * 100:.1f}\\% & [{lo_t * 100:.1f}\\%, {hi_t * 100:.1f}\\%] \\\\"
    )
    body = "\n".join(rows_tex)
    tex = (
        "\\begin{table}[ht]\n\\centering\n"
        "\\caption{Verificação humana amostral — acurácia por campo crítico "
        "(auditoria humano sobre extração do LLM; IC Wilson 95\\%)}\n"
        "\\label{tab:verificacao-acuracia}\n"
        "\\begin{tabular}{lrrrrr}\n\\toprule\n"
        "Campo & n & ok & erro & Acurácia & IC 95\\% \\\\\n\\midrule\n"
        f"{body}\n"
        "\\bottomrule\n\\end{tabular}\n\\end{table}\n"
    )
    out.write_text(tex, encoding="utf-8")


def run(extraction: Path, sheet_eleg: Path, sheet_aud: Path,
        kappa_table: Path, acuracia_table: Path, annotated: Path) -> None:
    ext_df = pd.read_csv(extraction, encoding="utf-8", keep_default_na=False)
    eleg = pd.read_csv(sheet_eleg, encoding="utf-8", keep_default_na=False)
    aud = pd.read_csv(sheet_aud, encoding="utf-8", keep_default_na=False)

    _validate_eleg(eleg)
    _validate_aud(aud)

    llm_by_rid = _llm_decision_by_rid(ext_df)
    humano: list[str] = []
    llm: list[str] = []
    concorda: list[bool] = []
    for _, r in eleg.iterrows():
        rid = str(r["review_id"])
        h = normalize_decisao(r["decisao_humana"])  # i/e/incluir/excluir
        l = llm_by_rid.get(rid, "excluir")
        humano.append(h)
        llm.append(l)
        concorda.append(h == l)

    _kappa_tex(humano, llm, kappa_table)
    _acuracia_tex(aud, acuracia_table)

    annotated.parent.mkdir(parents=True, exist_ok=True)
    eleg_out = eleg.copy()
    eleg_out["decisao_llm"] = llm
    eleg_out["concorda_eleg"] = concorda
    # Merge linhas de auditoria por review_id
    aud_subset_cols = ["review_id"] + [f"{c}_auditoria" for c in CAMPOS_CRITICOS] \
        + [f"{c}_correto" for c in CAMPOS_CRITICOS] + ["nota_auditoria"]
    aud_subset = aud[aud_subset_cols]
    merged = eleg_out.merge(aud_subset, on="review_id", how="left")
    merged.to_csv(annotated, index=False, encoding="utf-8")

    print(f"Verify ingest: n={len(eleg)} eleg | n={len(aud)} aud")
    print(f"  → {kappa_table}\n  → {acuracia_table}\n  → {annotated}")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="κ + acurácia da verificação humana (4b-ii).")
    p.add_argument("--extraction", type=Path, required=True)
    p.add_argument("--sheet-eleg", type=Path, required=True)
    p.add_argument("--sheet-aud", type=Path, required=True)
    p.add_argument("--kappa-table", type=Path, required=True)
    p.add_argument("--acuracia-table", type=Path, required=True)
    p.add_argument("--annotated", type=Path, required=True)
    a = p.parse_args(argv)
    run(extraction=a.extraction, sheet_eleg=a.sheet_eleg,
        sheet_aud=a.sheet_aud, kappa_table=a.kappa_table,
        acuracia_table=a.acuracia_table, annotated=a.annotated)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
```

- [ ] **Step 4: Rodar testes e confirmar verdes**

```
source .venv/bin/activate && pytest tests/extraction/test_verify_ingest.py -q
```
Expected: 5 passed.

- [ ] **Step 5: Adicionar target ao Makefile**

```makefile
.PHONY: verify-ingest
verify-ingest:
	$(PYTHON) -m scripts.extraction.verify_ingest \
	    --extraction $(DATA_PROC)/06_extraction.csv \
	    --sheet-eleg $(DATA_PROC)/07_eleg_cega.csv \
	    --sheet-aud $(DATA_PROC)/07_auditoria_campos.csv \
	    --kappa-table $(TAB_DIR)/verificacao_kappa.tex \
	    --acuracia-table $(TAB_DIR)/verificacao_acuracia.tex \
	    --annotated $(DATA_PROC)/07_verificacao_anotada.csv

.PHONY: verify
verify: verify-sample verify-export
	@echo "Planilhas geradas em data/processed/07_*.csv. Preencha-as e rode 'make verify-ingest'."
```

- [ ] **Step 6: Commit**

```bash
git add scripts/extraction/verify_ingest.py tests/extraction/test_verify_ingest.py Makefile
git commit -m "feat(4b-ii): verify_ingest — κ humano×LLM + acurácia por campo + tabelas .tex

- κ binário (incluir/excluir) com matriz 2×2 e IC Wilson 95% na concordância.
- Acurácia por campo crítico + IC Wilson; reusa normalize_decisao e cohen_kappa_score.
- Aborta com lista de pendências em vez de calcular silenciosamente com buracos.
- Saídas: verificacao_kappa.tex, verificacao_acuracia.tex, 07_verificacao_anotada.csv.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4 — `prisma_flow.py`: anotação interina (cobertura efetiva + pendentes)

**Files:**
- Modify: `scripts/screening/prisma_flow.py`
- Create: `tests/extraction/test_prisma_flow_interino.py`
- Modify: `Makefile` (target `prisma`)

**Contrato:**
- `compute_counts` ganha parâmetro opcional `extraction: Path | None = None`. Quando dado, computa também `extraidos`, `pendentes_reextract = 852 − extraidos`, `cobertura_pdf` (linhas com `text_source == "pdf"` na `06_extraction.csv`).
- Template TikZ ganha sufixo condicional: se `pendentes_reextract > 0`, adiciona um nó de **anotação** abaixo de `inc` com "Reextração pendente: N (cobertura full-text efetiva X,X%)". Se zero, sufixo vazio.
- Retrocompat: chamadas sem `--extraction` mantêm comportamento atual byte-idêntico.

- [ ] **Step 1: Escrever testes que falham**

Criar `tests/extraction/test_prisma_flow_interino.py`:

```python
"""Testes da anotação interina do PRISMA (Plano 4b-ii)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


def _mk_inputs(tmp_path: Path, n_parse_fail: int = 0):
    bruto = tmp_path / "bruto.csv"
    bruto.write_text("\n".join(["a"] + [str(i) for i in range(20)]),
                     encoding="utf-8")
    dedup = tmp_path / "dedup.csv"
    pd.DataFrame({"a": [1, 2]}).to_csv(dedup, index=False)
    scr = tmp_path / "scr.csv"
    pd.DataFrame({"decisao_llm": ["incluir"] * 12 + ["excluir"] * 6}).to_csv(scr, index=False)
    elig = tmp_path / "elig.csv"
    pd.DataFrame({"decisao_final": ["incluido"] * 10 + ["excluido"] * 2}).to_csv(elig, index=False)
    ext = None
    if n_parse_fail >= 0:
        ext = tmp_path / "ext.csv"
        rows = []
        for i in range(10):
            note = "parse_fail" if i < n_parse_fail else ""
            ts = "pdf" if i % 3 else "abstract"
            rows.append({"id": i, "nota_extracao": note, "text_source": ts})
        pd.DataFrame(rows).to_csv(ext, index=False)
    return bruto, dedup, scr, elig, ext


def test_retrocompat_sem_extraction(tmp_path):
    from scripts.screening import prisma_flow as P
    bruto, dedup, scr, elig, _ = _mk_inputs(tmp_path, n_parse_fail=0)
    counts = P.compute_counts(bruto, dedup, scr, elig)
    out = tmp_path / "p.tex"
    P.write_tex(counts, out)
    tex = out.read_text(encoding="utf-8")
    assert "Reextração pendente" not in tex


def test_anotacao_quando_pendentes_positivos(tmp_path):
    from scripts.screening import prisma_flow as P
    bruto, dedup, scr, elig, ext = _mk_inputs(tmp_path, n_parse_fail=3)
    counts = P.compute_counts(bruto, dedup, scr, elig, extraction=ext)
    out = tmp_path / "p.tex"
    P.write_tex(counts, out)
    tex = out.read_text(encoding="utf-8")
    assert "Reextração pendente: 3" in tex
    assert "cobertura full-text efetiva" in tex


def test_sem_anotacao_quando_zero_pendentes(tmp_path):
    from scripts.screening import prisma_flow as P
    bruto, dedup, scr, elig, ext = _mk_inputs(tmp_path, n_parse_fail=0)
    counts = P.compute_counts(bruto, dedup, scr, elig, extraction=ext)
    out = tmp_path / "p.tex"
    P.write_tex(counts, out)
    tex = out.read_text(encoding="utf-8")
    assert "Reextração pendente" not in tex
```

- [ ] **Step 2: Confirmar falhas**

```
source .venv/bin/activate && pytest tests/extraction/test_prisma_flow_interino.py -q
```
Expected: 3 FAILED (parâmetro `extraction` inexistente).

- [ ] **Step 3: Implementar ajuste retrocompatível em `prisma_flow.py`**

Editar `scripts/screening/prisma_flow.py` — substituir o `TEMPLATE` por uma constante base + sufixo condicional, e estender `compute_counts` e o CLI:

```python
"""Pipeline step 05: generate PRISMA 2020 flow diagram as a TikZ .tex file.

Reads counts from earlier pipeline outputs and writes a self-contained TikZ
picture into `text/figures/prisma_flow.tex`, included via \\input{} in the
methodology chapter.

Plano 4b-ii: parâmetro opcional `--extraction` adiciona caixa de anotação
"Reextração pendente: N (cobertura full-text efetiva X,X%)" quando houver
linhas com nota_extracao=parse_fail. Some sozinha pós-re-rodada.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

_BODY = r"""\begin{tikzpicture}[
    node distance=1.2cm,
    every node/.style={draw, rectangle, rounded corners, align=center, minimum width=5cm, minimum height=0.9cm, font=\small},
    arr/.style={-{Stealth[length=2mm]}, thick}
]
\node (id)   {Registros identificados nas bases\\(\textbf{N = %(identified)d})};
\node (dup) [below=of id] {Duplicatas removidas\\(N = %(duplicates)d)};
\node (scr) [below=of dup] {Registros para triagem TA\\(N = %(screened)d)};
\node (exta)[right=2cm of scr] {Excluídos na triagem TA\\(N = %(excluded_ta)d)};
\node (elig)[below=of scr] {Candidatos a texto completo\\(N = %(eligibility)d)};
\node (exft)[right=2cm of elig] {Excluídos na elegibilidade\\(N = %(excluded_ft)d)};
\node (inc) [below=of elig, fill=blue!10] {Estudos incluídos na síntese\\(\textbf{N = %(included)d})};
%(extra_node)s
\draw[arr] (id)  -- (dup);
\draw[arr] (dup) -- (scr);
\draw[arr] (scr) -- (elig);
\draw[arr] (scr) -- (exta);
\draw[arr] (elig)-- (inc);
\draw[arr] (elig)-- (exft);
\end{tikzpicture}
"""

_NOTA_INTERINA = (
    r"\node (nota) [below=of inc, draw=red!60, fill=red!5, font=\footnotesize, "
    r"align=center] {Reextração pendente: %(pendentes_reextract)d "
    r"(cobertura full-text efetiva %(cobertura_pct).1f\%%)};"
    "\n"
)


def write_tex(counts: dict, output: Path) -> None:
    extra = (_NOTA_INTERINA % counts) if counts.get("pendentes_reextract", 0) > 0 else ""
    output.parent.mkdir(parents=True, exist_ok=True)
    body = _BODY % {**counts, "extra_node": extra}
    output.write_text(body, encoding="utf-8")


def compute_counts(
    bruto: Path, dedup_log: Path, screening: Path, eligibility: Path,
    extraction: Path | None = None,
) -> dict:
    with open(bruto) as f:
        identified = sum(1 for _ in f) - 1
    dup_df = pd.read_csv(dedup_log)
    duplicates = len(dup_df)
    screened = identified - duplicates

    scr_df = pd.read_csv(screening)
    excluded_ta = (scr_df["decisao_llm"] == "excluir").sum()
    eligibility_n = len(scr_df) - excluded_ta

    elig_df = pd.read_csv(eligibility)
    included = (elig_df["decisao_final"] == "incluido").sum()
    excluded_ft = (elig_df["decisao_final"] == "excluido").sum()

    counts = dict(
        identified=int(identified), duplicates=int(duplicates),
        screened=int(screened), excluded_ta=int(excluded_ta),
        eligibility=int(eligibility_n), excluded_ft=int(excluded_ft),
        included=int(included),
        pendentes_reextract=0, cobertura_pct=0.0,
    )

    if extraction is not None:
        ext_df = pd.read_csv(extraction, encoding="utf-8", keep_default_na=False)
        n_total = len(ext_df)
        n_pf = int((ext_df["nota_extracao"] == "parse_fail").sum())
        n_pdf = int((ext_df["text_source"] == "pdf").sum())
        counts["pendentes_reextract"] = n_pf
        counts["cobertura_pct"] = (n_pdf / n_total * 100.0) if n_total else 0.0

    return counts


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--bruto", type=Path, required=True)
    p.add_argument("--dedup-log", type=Path, required=True)
    p.add_argument("--screening", type=Path, required=True)
    p.add_argument("--eligibility", type=Path, required=True)
    p.add_argument("--extraction", type=Path, default=None)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    counts = compute_counts(args.bruto, args.dedup_log, args.screening,
                            args.eligibility, extraction=args.extraction)
    write_tex(counts, args.output)
    print(f"PRISMA flow written to {args.output} (included N={counts['included']}, "
          f"pendentes_reextract={counts['pendentes_reextract']})")
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
```

- [ ] **Step 4: Rodar testes e confirmar verdes — novos e a suite cheia**

```
source .venv/bin/activate && pytest tests/extraction/test_prisma_flow_interino.py -q
source .venv/bin/activate && pytest -q
```
Expected: novos 3 passed; total >= 218 verdes (206 base + 5 + 4 + 5 + 3 + os 2 já em test_pdf_validity… na verdade base = 206, +17 novos = 223; aceitar qualquer total entre 220 e 230 verde).

- [ ] **Step 5: Atualizar target `prisma` no Makefile**

Editar o bloco `.PHONY: prisma` para passar `--extraction`:

```makefile
.PHONY: prisma
prisma:
	$(PYTHON) -m scripts.screening.prisma_flow \
	    --bruto $(DATA_PROC)/01_corpus_bruto.csv \
	    --dedup-log $(DATA_PROC)/02_dedup_decisions.csv \
	    --screening $(DATA_PROC)/03_screening_ta.csv \
	    --eligibility $(DATA_PROC)/04_eligibility.csv \
	    --extraction $(DATA_PROC)/06_extraction.csv \
	    --output $(FIG_DIR)/prisma_flow.tex
```

- [ ] **Step 6: Commit**

```bash
git add scripts/screening/prisma_flow.py tests/extraction/test_prisma_flow_interino.py Makefile
git commit -m "feat(4b-ii): PRISMA — anotação interina com pendentes de reextração

- compute_counts ganha --extraction opcional (retrocompat byte-idêntico sem ele).
- TikZ ganha caixa de anotação quando pendentes_reextract > 0; some quando = 0.
- Cobertura full-text efetiva (text_source==pdf / total) reportada na caixa.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5 — Emenda do protocolo: v1.1 → v1.2

**Files:**
- Modify: `protocols/slr_protocol.md` (cabeçalho, §7, §8, §11)

Sem TDD (prosa). Faça edições cirúrgicas; a suite continua verde.

- [ ] **Step 1: Bump da versão no cabeçalho**

Editar a linha 9 (`Versão do protocolo: 1.1 (...)`):

```
**Versão do protocolo:** 1.2 (emenda 2026-05-19 — ver §7, §8 e §11)
```

- [ ] **Step 2: Adicionar parágrafo em §7 referenciando §8**

Após o parágrafo iniciado por "**Emenda 2026-05-17 (protocolo v1.1).**" (linha ~81), adicionar:

```
**Emenda 2026-05-19 (protocolo v1.2).** A etapa de elegibilidade (texto
completo) e a extração dos 33 campos passaram a ser executadas pelo LLM
(Claude Sonnet 4.6) — ver §8. A verificação humana amostral (κ humano×LLM
para a elegibilidade, auditoria de acurácia por campo crítico) é descrita
na nova subseção "Verificação humana amostral" de §8 e na limitação
correspondente em §11.
```

- [ ] **Step 3: Adicionar subseção em §8 após o bloco "Incidente da 1ª rodada"**

Após o parágrafo terminado por "...permanecem sem extração e são declarados como tal." (linha ~117), adicionar:

```
**Verificação humana amostral (Plano 4b-ii, 2026-05-19).** Uma amostra
estratificada de aproximadamente 110 estudos dos 790 com extração real é
verificada manualmente: **100% das exclusões** (≈ 34) e **~10% das inclusões**
(≈ 76) estratificado por `text_source` × faixa de `confianca_extracao` (seed
fixa 42, snapshot do quadro amostral em `07_amostra_frame.csv`). A
elegibilidade é decidida **cega** (o revisor não vê a decisão do LLM) e
produz **κ de Cohen humano×LLM** + concordância com IC Wilson 95%
(`text/tables/verificacao_kappa.tex`). Os campos analiticamente centrais
(`pre_pos_chatgpt`, `janela`, `sinal_efeito`, `tipo_estudo`, `polarizacao`,
`score_qualidade`) são **auditados** (o revisor vê valor do LLM + fonte e
marca ok/erro) e produzem **acurácia por campo** + IC Wilson 95%
(`text/tables/verificacao_acuracia.tex`). Scripts em `scripts/extraction/
verify_{sample,export,ingest}.py`. Por desenho, a verificação é **definitiva
sobre os 790**: a re-rodada idempotente que recuperar os 61 estudos sem
extração da 1ª rodada **não altera** as métricas reportadas (decisão
declarada do protocolo; a amostra não é re-sorteada nem suplementada). O
PRISMA permanece em modo interino enquanto houver pendentes de reextração e
se torna definitivo automaticamente quando essa pendência for zerada.
```

- [ ] **Step 4: Adicionar bullet em §11**

Após o bullet "Reextração pendente de 61…" (linha ~144), adicionar:

```
- **Verificação humana amostral, revisor único.** A validação foi feita por
  um único revisor sobre ~110 estudos (100% das exclusões + ~10% das
  inclusões estratificado). Mitigações: cegueira na elegibilidade (κ
  legítimo); intervalos de confiança Wilson 95% reportados para concordância
  e acurácia por campo; auditoria com fonte explícita (o revisor vê o que o
  LLM viu). Limitação: estratos pequenos podem produzir ICs largos; a
  auditoria de campos não é cega (mostra o valor do LLM antes da
  classificação), o que pode ancorar o revisor — escolha consciente para
  viabilizar a taxa de revisão em prazo.
```

- [ ] **Step 5: Confirmar suite verde**

```
source .venv/bin/activate && pytest -q
```
Expected: a mesma contagem do final da Task 4 (mudanças apenas em prosa).

- [ ] **Step 6: Commit**

```bash
git add protocols/slr_protocol.md
git commit -m "docs(protocol): emenda v1.2 — verificação humana amostral (Plano 4b-ii)

- Versão 1.1 → 1.2 (emenda 2026-05-19).
- §7: emenda referenciando a nova subseção em §8.
- §8: subseção 'Verificação humana amostral' com amostragem, modo (cego para
  elegibilidade, auditoria para campos críticos), métricas e arquivos .tex
  gerados; declara que a verificação é definitiva sobre os 790.
- §11: bullet sobre limitações da verificação amostral (revisor único, ICs,
  auditoria não-cega para campos).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6 — Integração final + verificação de prontidão

**Files:**
- (apenas leituras + commit final)

- [ ] **Step 1: Suite cheia verde**

```
source .venv/bin/activate && pytest -q
```
Expected: todos verdes (~220-230 testes).

- [ ] **Step 2: Pipeline `verify-*` ponta-a-ponta**

```
source .venv/bin/activate && make verify-sample
source .venv/bin/activate && make verify-export
```
Expected: 4 arquivos novos em `data/processed/` (`07_amostra_frame.csv`, `07_amostra_verificacao.csv`, `07_eleg_cega.csv`, `07_auditoria_campos.csv`) + 2 `.state.json`.

- [ ] **Step 3: Sanidade da cegueira**

```
head -1 data/processed/07_eleg_cega.csv
```
Expected (uma linha CSV): contém `review_id,decisao_humana,nota_humana,year,title,authors,venue,abstract,text_source,criterios_ref` e **não** contém `elegivel`, `motivo_exclusao`, `pre_pos_chatgpt`.

- [ ] **Step 4: Regenerar PRISMA com anotação interina**

```
source .venv/bin/activate && make prisma
grep -c "Reextração pendente" text/figures/prisma_flow.tex
```
Expected: `1` (caixa de anotação presente). O número de pendentes deve bater com o atual estado do `06_extraction.csv` (~62 enquanto a re-rodada não rodar).

- [ ] **Step 5: Smoke do erro de pendência**

```
source .venv/bin/activate && python -m scripts.extraction.verify_ingest \
    --extraction data/processed/06_extraction.csv \
    --sheet-eleg data/processed/07_eleg_cega.csv \
    --sheet-aud data/processed/07_auditoria_campos.csv \
    --kappa-table /tmp/k.tex --acuracia-table /tmp/a.tex \
    --annotated /tmp/ann.csv ; echo "exit=$?"
```
Expected: exit≠0 + mensagem listando `decisao_humana` pendentes (planilhas ainda vazias). Confirma que o aborto-cedo funciona contra dado real.

- [ ] **Step 6: Commit de versionamento dos artefatos gerados**

```bash
git add data/processed/07_amostra_frame.csv data/processed/07_amostra_verificacao.csv \
        data/processed/07_eleg_cega.csv data/processed/07_eleg_cega.state.json \
        data/processed/07_auditoria_campos.csv data/processed/07_auditoria_campos.state.json \
        text/figures/prisma_flow.tex
git commit -m "chore(4b-ii): versiona artefatos do pipeline verify + PRISMA interino

Estado pós-Plano 4b-ii (antes do preenchimento humano):
- Frame: 790 review_ids (snapshot congelado).
- Amostra: 34 exclusões (100%) + ~76 inclusões (estratificado, seed=42).
- Planilhas cega + auditoria geradas com colunas humanas vazias.
- PRISMA com caixa de anotação interina enquanto a reextração estiver pendente.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>" || echo "(sem mudança a commitar — ok)"
```

(Alguns desses arquivos podem cair em `.gitignore` data/processed/**/*.csv. Se o `git add` rejeitar, use `-f` para os artefatos não-PII, como já foi feito para o manifesto no Plano 4b-i; **nunca** force PDFs.)

- [ ] **Step 7: Relatório final**

Imprima/anote um resumo curto: contagem do frame (esperado 790), tamanho da amostra (esperado ~110), número de exclusões na amostra (esperado 34), número de pendentes de reextração no PRISMA, total de testes verdes. Esse resumo vai para a entrega ao usuário antes do `finishing-a-development-branch`.

---

## Self-review

**1. Spec coverage** — passei por todas as seções da spec:
- §3 Arquitetura (5 unidades): cobertas em Tasks 1–5 (verify_sample, verify_export, verify_ingest, prisma_flow, protocolo). ✓
- §4.1 verify_sample: idempotência (snapshot), 100% exclusões, ~10% estratificado, piso. ✓
- §4.2 verify_export: cegueira, auditoria, merge_preserve, .state.json, backup. ✓
- §4.3 verify_ingest: κ + matriz 2×2, IC Wilson, acurácia, aborta em pendências. ✓
- §4.4 prisma_flow: parâmetro opcional, anotação condicional, retrocompat. ✓
- §4.5 Protocolo v1.2: cabeçalho, §7, §8 subseção, §11 bullet. ✓
- §4.6 Makefile: 4 targets novos. ✓
- §5 Testes: cada teste da spec tem um test_* explícito. ✓
- §6 Escopo: não inclui re-rodada nem PDFs suplementares; suplementação dos 61 fora. ✓
- §7 Critérios de sucesso: 7 critérios → cobertos pelas Tasks 1, 2, 6. ✓

**2. Placeholder scan** — nenhum "TBD"/"TODO"/"similar to" no plano; todos os steps têm código ou comandos concretos.

**3. Type consistency** —
- `cache_key/custom_id` sempre via `scripts.screening.llm.batch_client` (consistente).
- `CAMPOS_CRITICOS` tupla idêntica em `verify_export` e `verify_ingest`.
- Nomes de colunas `<campo>_llm/_auditoria/_correto` consistentes entre exportador e ingestor.
- `nota_extracao == "parse_fail"` como sentinela consistente em verify_sample e prisma_flow.
- `normalize_decisao` reusado de `scripts.screening.revisao_ingest` (não redefinido).
- `keep_default_na=False` em todos os `pd.read_csv` de planilhas humanas (idêntico ao padrão revisao).

Sem inconsistências detectadas. Plano consistente com a spec.
