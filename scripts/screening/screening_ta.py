"""Pipeline step 03: title/abstract screening with LLM-as-judge + human revision.

In `--mock` mode (used for tests and dry-runs), uses a simple rule-based heuristic.
In real mode, calls Claude via Anthropic SDK with a structured prompt; caches
responses per record to be idempotent.

Output columns added to dedup CSV:
- decisao_llm: incluir | excluir | duvida
- justificativa_llm: 1-2 sentence reasoning citing inclusion/exclusion criterion
- confianca_llm: 0–1

CLI:
    python -m scripts.screening.screening_ta \
        --input data/processed/02_corpus_dedup.csv \
        --output data/processed/03_screening_ta.csv \
        --incluidos data/processed/03_incluidos_ta.csv \
        [--mock] [--model claude-sonnet-4-6]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Literal

import pandas as pd

PROMPT_TEMPLATE = """\
Você é um avaliador de revisão sistemática em economia. Avalie se o estudo abaixo
deve ser INCLUÍDO no corpus de uma SLR sobre IMPACTOS DA IA NO EMPREGO (2013–2025).

CRITÉRIOS DE INCLUSÃO:
- Período: 2013–2025.
- Tipo de IA: ML, deep learning, NLP, LLMs/IA generativa, robôs com IA.
- Desfecho: efeito sobre emprego (níveis, criação/destruição, exposição, demanda).
- Tipo: periódico revisado, working paper de instituição reconhecida, capítulo indexado.

EXCLUIR se:
- E1: fora do escopo (educação/saúde/ética/governança sem ligação com emprego; só produtividade individual)
- E2: tecnologia fora do escopo (robótica industrial pré-IA, automação mecânica)
- E3: tipo de documento inválido (editorial, opinião, blog)
- E5: qualidade insuficiente (sem metodologia)

ESTUDO:
Título: {title}
Autores: {authors}
Ano: {year}
Periódico: {venue}
Resumo: {abstract}

Responda em JSON estrito:
{{
  "decisao": "incluir" | "excluir" | "duvida",
  "justificativa": "1-2 frases citando critério",
  "confianca": <float 0-1>
}}
"""


def _mock_judge(row: pd.Series) -> dict:
    """Rule-based mock: include if title mentions AI + (employment OR labor OR jobs)."""
    text = f"{row['title']} {row['abstract']}".lower()
    has_ai = any(t in text for t in ["ai", "artificial intelligence", "machine learning", "llm", "gpt"])
    has_labor = any(
        t in text for t in ["employment", "labor", "labour", "jobs", "wages", "occupation"]
    )
    if has_ai and has_labor:
        return dict(decisao="incluir", justificativa="Mock: AI + labor keywords.", confianca=0.85)
    if has_ai:
        return dict(decisao="duvida", justificativa="Mock: AI mention but no labor.", confianca=0.5)
    return dict(decisao="excluir", justificativa="Mock: no AI keyword.", confianca=0.9)


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


def _llm_judge(row: pd.Series, model: str, cache: dict, client) -> dict:
    cache_key = row.get("doi") or f"{row['title']}-{row['year']}"
    if cache_key in cache:
        return cache[cache_key]
    prompt = PROMPT_TEMPLATE.format(
        title=row["title"], authors=row["authors"], year=row["year"],
        venue=row["venue"], abstract=row["abstract"],
    )
    msg = client.messages.create(
        model=model,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`").lstrip("json").strip()
    parsed = json.loads(raw)
    cache[cache_key] = parsed
    return parsed


def run(
    input: Path,
    output: Path,
    incluidos: Path | None = None,
    mock: bool = False,
    model: str = "claude-sonnet-4-6",
    cache_path: Path | None = None,
) -> None:
    df = pd.read_csv(input, encoding="utf-8")

    cache: dict = {}
    if cache_path and cache_path.exists():
        cache = json.loads(cache_path.read_text())

    if not mock:
        from anthropic import Anthropic
        client = Anthropic()
    else:
        client = None

    decisions = []
    for _, row in df.iterrows():
        d = _mock_judge(row) if mock else _llm_judge(row, model=model, cache=cache, client=client)
        decisions.append(d)

    df["decisao_llm"] = [d["decisao"] for d in decisions]
    df["justificativa_llm"] = [d["justificativa"] for d in decisions]
    df["confianca_llm"] = [d["confianca"] for d in decisions]

    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False, encoding="utf-8")

    if incluidos:
        inc = df[df["decisao_llm"].isin(["incluir", "duvida"])]
        inc.to_csv(incluidos, index=False, encoding="utf-8")

    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2))

    print(f"Screening: {len(df)} records → {(df['decisao_llm']=='incluir').sum()} include, "
          f"{(df['decisao_llm']=='duvida').sum()} duvida, "
          f"{(df['decisao_llm']=='excluir').sum()} excluir")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--incluidos", type=Path)
    p.add_argument("--mock", action="store_true")
    p.add_argument("--model", default="claude-sonnet-4-6")
    p.add_argument("--cache", type=Path, default=Path("data/processed/03_llm_cache.json"))
    args = p.parse_args(argv)
    run(args.input, args.output, incluidos=args.incluidos, mock=args.mock,
        model=args.model, cache_path=args.cache)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
