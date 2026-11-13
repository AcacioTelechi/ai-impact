"""Rastreamento de citações (snowballing retroativo) — revisão 2026-11.

A aferição de sensibilidade da busca (`reports/revisao/top_referencias_cobertura.csv`)
mostrou que parte das referências mais citadas pelo próprio corpus, com data de
publicação elegível, não foi recuperada pelas strings. Este módulo trata essas
referências como registros identificados por "outros métodos" (PRISMA 2020):

1. seleciona as referências com ano elegível e não recuperadas na busca;
2. obtém metadados e resumo na OpenAlex (fronteira de rede injetável);
3. submete cada uma à MESMA passada de elegibilidade + extração do corpus
   principal (mesmo prompt, mesmo modelo), sempre a partir do resumo.

O resultado fica em arquivos separados (`09_snowball_*.csv`): o estrato NÃO é
fundido ao corpus da busca; entra apenas como análise de sensibilidade, porque
foi selecionado por citação (amostra intencional), e não pela estratégia de busca.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import quote

import pandas as pd

from scripts.extraction.extract_llm import (
    MAX_TOKENS_EXTRACT, MODEL, OUTPUT_COLUMNS, build_user_content, fundir,
    parse_extraction,
)
from scripts.extraction.llm_extract_prompt import build_extract_system_block
from scripts.screening.llm.batch_client import screen_with_model
from scripts.search.openalex_utils import reconstruct_abstract

ANO_MIN, ANO_MAX = 2013, 2026
API = "https://api.openalex.org/works/https://doi.org/"
CAND_COLUMNS = ["id", "source", "doi", "title", "authors", "year", "abstract",
                "venue", "language", "citacoes_no_corpus", "text_source", "pdf_path"]


def selecionar(cobertura: pd.DataFrame) -> pd.DataFrame:
    """Referências com ano elegível e não recuperadas pela busca."""
    ano = pd.to_numeric(cobertura["ano"], errors="coerce")
    rec = cobertura["recuperado_na_busca"].astype(str).str.lower() == "true"
    return cobertura[ano.between(ANO_MIN, ANO_MAX) & ~rec].reset_index(drop=True)


def http_get(url: str) -> dict | None:
    import requests

    r = requests.get(url, timeout=30, headers={"User-Agent": "slr-snowball/0.1"})
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def montar_candidatos(sel: pd.DataFrame, get=http_get) -> pd.DataFrame:
    rows = []
    for i, r in sel.iterrows():
        doi = str(r["doi"]).strip().lower()
        rec = get(API + quote(doi, safe="/")) or {}
        autores = "; ".join(a.get("author", {}).get("display_name", "")
                            for a in rec.get("authorships") or []
                            if a.get("author", {}).get("display_name"))
        venue = ((rec.get("primary_location") or {}).get("source") or {}).get("display_name")
        rows.append({
            "id": f"sb-{i + 1:03d}", "source": "snowball-backward", "doi": doi,
            "title": rec.get("title") or r["titulo"],
            "authors": autores or r["autor1"],
            "year": int(r["ano"]),
            "abstract": reconstruct_abstract(rec.get("abstract_inverted_index")),
            "venue": venue or r["veiculo"],
            "language": rec.get("language") or "en",
            "citacoes_no_corpus": int(r["citacoes_no_corpus"]),
            "text_source": "abstract", "pdf_path": "",
        })
    return completar_resumos(pd.DataFrame(rows, columns=CAND_COLUMNS))


RESUMO_MIN = 200  # abaixo disso o "resumo" da OpenAlex é só um fragmento


def _resumo_crossref(doi: str) -> str:
    import html
    import re

    import requests

    r = requests.get("https://api.crossref.org/works/" + doi, timeout=30,
                     headers={"User-Agent": "slr-snowball/0.1"})
    if not r.ok:
        return ""
    bruto = html.unescape(r.json()["message"].get("abstract") or "")
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", bruto)).strip()


def _resumo_semantic_scholar(doi: str) -> str:
    import re

    import requests

    r = requests.get(f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=abstract",
                     timeout=30, headers={"User-Agent": "slr-snowball/0.1"})
    return re.sub(r"\s+", " ", (r.json().get("abstract") or "")).strip() if r.ok else ""


def completar_resumos(cand: pd.DataFrame,
                      fontes=(_resumo_crossref, _resumo_semantic_scholar)) -> pd.DataFrame:
    """Resumo ausente na OpenAlex → tenta Crossref e Semantic Scholar, nessa ordem."""
    cand = cand.copy()
    for i, r in cand.iterrows():
        for fonte in fontes:
            if len(str(cand.at[i, "abstract"])) >= RESUMO_MIN:
                break
            ab = fonte(r["doi"])
            if len(ab) >= RESUMO_MIN:
                cand.at[i, "abstract"] = ab
    return cand


def run(cobertura: Path, candidatos: Path, output: Path, cache: Path,
        get=http_get, submit_fn=None) -> pd.DataFrame:
    if candidatos.exists():
        cand = pd.read_csv(candidatos, encoding="utf-8", keep_default_na=False)
    else:
        cand = montar_candidatos(selecionar(pd.read_csv(cobertura, encoding="utf-8")), get)
        candidatos.parent.mkdir(parents=True, exist_ok=True)
        cand.to_csv(candidatos, index=False, encoding="utf-8")
    res = screen_with_model(
        cand, model=MODEL, cache_path=cache, submit_fn=submit_fn,
        system_block=build_extract_system_block(),
        user_content_fn=build_user_content, parse_fn=parse_extraction,
        max_tokens=MAX_TOKENS_EXTRACT,
    )
    odf = pd.DataFrame([fundir(r, p) for (_, r), p in zip(cand.iterrows(), res)],
                       columns=OUTPUT_COLUMNS)
    odf["citacoes_no_corpus"] = cand["citacoes_no_corpus"].values
    odf["tem_resumo"] = (cand["abstract"].astype(str).str.len() >= RESUMO_MIN).values
    odf.to_csv(output, index=False, encoding="utf-8")
    n_inc = int((odf["elegivel"] == "incluir").sum())
    print(f"Snowball: {len(odf)} avaliados | {n_inc} elegíveis | "
          f"{int(odf['tem_resumo'].sum())} com resumo — modelo {MODEL}\n  → {output}")
    return odf


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Snowballing retroativo das referências mais citadas.")
    p.add_argument("--cobertura", type=Path, required=True)
    p.add_argument("--candidatos", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--cache", type=Path, required=True)
    a = p.parse_args(argv)
    run(a.cobertura, a.candidatos, a.output, a.cache)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
