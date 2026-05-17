"""Plano 4b-i: elegibilidade + extração por LLM (Sonnet 4.6), 1 passada
combinada, PDF nativo onde houver / abstract no resto.

Ver docs/superpowers/specs/2026-05-17-plano-4b-i-elegibilidade-extracao-llm-design.md
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from pathlib import Path

import pandas as pd

from scripts.extraction.extract import SCHEMA_COLUMNS
from scripts.extraction.llm_extract_prompt import build_extract_system_block
from scripts.screening.llm.batch_client import (
    cache_key, custom_id, screen_with_model,
)

MODEL = "claude-sonnet-4-6"
MAX_TOKENS_EXTRACT = 4096

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


_TEXT_FIELDS = {"mec_outros", "fonte_dados", "magnitude_reportada",
                "magnitude_normalizada", "ocupacoes_afetadas",
                "limitacoes_declaradas", "nota_extracao", "citacoes_chave",
                "pais_estudo", "periodo_dados"}
assert _TEXT_FIELDS <= set(_LLM_FIELDS), (
    f"_TEXT_FIELDS fora do schema: {_TEXT_FIELDS - set(_LLM_FIELDS)}"
)


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
    out["ano"] = row.get("year", "")  # int (não str): validate.py faz int(ano); CSV normaliza
    out["periodico"] = str(row.get("venue") or "")
    out["revisto_humano"] = "False"
    out["elegivel"] = parsed.get("elegivel", "incluir")
    out["motivo_exclusao"] = parsed.get("motivo_exclusao", "")
    out["text_source"] = row.get("text_source", "")
    out["confianca_extracao"] = parsed.get("confianca_extracao", 0.0)
    return {c: out.get(c, "") for c in OUTPUT_COLUMNS}


def run(corpus: Path, manifest: Path, output: Path, cache: Path,
        submit_fn=None) -> None:
    cdf = pd.read_csv(corpus, encoding="utf-8", keep_default_na=False)
    mdf = pd.read_csv(manifest, encoding="utf-8", keep_default_na=False)
    cdf["review_id"] = [custom_id(cache_key(r)) for _, r in cdf.iterrows()]
    # `id` (s-NNN) e text_source/pdf_path vêm do manifesto (4a) via este merge;
    # o corpus não tem coluna id. fundir/_meta_text dependem do df pós-merge.
    m = mdf[["id", "review_id", "text_source", "pdf_path"]]
    df = cdf.merge(m, on="review_id", how="inner")
    assert len(df) == len(cdf), (
        f"join corpus↔manifesto perdeu linhas: {len(cdf)} corpus → {len(df)} "
        "após merge por review_id (manifesto desatualizado/incompleto?) — abortando"
    )

    res = screen_with_model(
        df, model=MODEL, cache_path=cache, submit_fn=submit_fn,
        system_block=build_extract_system_block(),
        user_content_fn=build_user_content, parse_fn=parse_extraction,
        max_tokens=MAX_TOKENS_EXTRACT,
    )
    assert len(res) == len(df), (
        f"screen_with_model devolveu {len(res)} para {len(df)} linhas; "
        "o zip truncaria silenciosamente — abortando"
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
