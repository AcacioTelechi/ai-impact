"""Aquisição híbrida de referências (Plano 6): WoS local onde houver, OpenAlex
no resto. Saída: data/processed/08_paper_refs.csv (paper_doi, ref_doi, fonte).

`build_paper_refs` é puro (fetchers injetáveis). `run` faz o I/O: carrega o
corpus + .bib, monta fetchers reais com cache em disco e grava os artefatos.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from scripts.biblio.dois import norm_doi
from scripts.biblio.openalex import (
    make_http_get, referenced_works, resolve_ids_to_dois,
)
from scripts.biblio.wos_refs import parse_wos_bib


def build_paper_refs(paper_dois, wos_map, oa_fetch, oa_resolve):
    rows: list[tuple[str, str, str]] = []
    stats = {"papers_wos": 0, "papers_openalex": 0, "papers_sem_refs": 0,
             "papers_oa_erro": 0}
    for pd_ in paper_dois:
        if pd_ in wos_map:
            refs = wos_map[pd_]
            fonte = "wos"
            stats["papers_wos"] += 1
        else:
            try:
                ids = oa_fetch(pd_)
            except Exception:
                ids = []
                stats["papers_oa_erro"] += 1
            idmap = oa_resolve(ids)
            refs = [idmap[i] for i in ids if i in idmap]
            fonte = "openalex"
            stats["papers_openalex"] += 1
        refs = [r for r in refs if r and r != pd_]
        if not refs:
            stats["papers_sem_refs"] += 1
        for r in refs:
            rows.append((pd_, r, fonte))
    return rows, stats


def _included_dois(extraction: Path) -> list[str]:
    df = pd.read_csv(extraction, encoding="utf-8", dtype=str).fillna("")
    inc = df[df["elegivel"] == "incluir"]
    dois = [norm_doi(d) for d in inc["doi"]]
    return list(dict.fromkeys([d for d in dois if d]))


def run(extraction: Path, wos_glob_dir: Path, out_csv: Path,
        cache_refs: Path, cache_idmap: Path, mailto: str) -> None:
    paper_dois = _included_dois(extraction)
    wos_map = parse_wos_bib(sorted(Path(wos_glob_dir).glob("*.bib")))

    get = make_http_get(mailto)
    refs_cache = json.loads(cache_refs.read_text()) if cache_refs.exists() else {}
    idmap = json.loads(cache_idmap.read_text()) if cache_idmap.exists() else {}

    fetched = {"n": 0}

    def oa_fetch(doi: str):
        if doi not in refs_cache:
            refs_cache[doi] = referenced_works(doi, get, mailto=mailto)
            fetched["n"] += 1
            if fetched["n"] % 25 == 0:
                cache_refs.write_text(json.dumps(refs_cache, ensure_ascii=False))
        return refs_cache[doi]

    def oa_resolve(ids):
        missing = [i for i in ids if i not in idmap]
        if missing:
            idmap.update(resolve_ids_to_dois(missing, get, mailto=mailto))
        return idmap

    rows, stats = build_paper_refs(paper_dois, wos_map, oa_fetch, oa_resolve)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=["paper_doi", "ref_doi", "fonte"]).to_csv(
        out_csv, index=False, encoding="utf-8")
    cache_refs.write_text(json.dumps(refs_cache, ensure_ascii=False))
    cache_idmap.write_text(json.dumps(idmap, ensure_ascii=False))
    print(f"Refs: {len(paper_dois)} papers c/ DOI | "
          f"{stats['papers_wos']} via WoS, {stats['papers_openalex']} via OpenAlex | "
          f"{stats['papers_sem_refs']} sem refs | "
          f"{stats['papers_oa_erro']} erro OpenAlex | {len(rows)} pares paper→ref")
    print(f"  → {out_csv}")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--extraction", type=Path, required=True)
    p.add_argument("--wos-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--cache-refs", type=Path, required=True)
    p.add_argument("--cache-idmap", type=Path, required=True)
    p.add_argument("--mailto", required=True)
    a = p.parse_args(argv)
    run(a.extraction, a.wos_dir, a.out, a.cache_refs, a.cache_idmap, a.mailto)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
