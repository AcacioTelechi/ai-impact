"""Parser do campo Cited-References dos exports .bib da Web of Science (Plano 6).

O export WoS traz, por registro, `DOI = {...}` e `Cited-References = {ref. ref.
ref.}` — refs separadas por `.\\n`, cada uma no formato
`Autor AA, ANO, PERIODICO, Vvol, Ppag, DOI 10...`. Extraímos o DOI de cada ref
(quando houver) e descartamos as demais. Identidade via DOI normalizado.
"""
from __future__ import annotations

import re
from pathlib import Path

from scripts.biblio.dois import norm_doi


def _extract_field(entry: str, name: str) -> str:
    """Valor de `name = { ... }` com varredura de chaves balanceadas
    (case-insensitive). "" se ausente."""
    m = re.search(rf"(?i)\b{re.escape(name)}\s*=\s*\{{", entry)
    if not m:
        return ""
    i = m.end()
    depth = 1
    buf: list[str] = []
    while i < len(entry) and depth > 0:
        c = entry[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                break
        buf.append(c)
        i += 1
    return "".join(buf)


def _split_refs(cited: str) -> list[str]:
    # refs separadas por ponto-final seguido de quebra de linha
    return [r.strip() for r in re.split(r"\.\s*\n", cited) if r.strip()]


def parse_wos_bib(paths) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for path in paths:
        txt = Path(path).read_text(encoding="utf-8", errors="replace")
        # entradas começam em '@'; split preservando blocos
        for chunk in re.split(r"\n@", txt):
            entry = chunk if chunk.lstrip().startswith("@") else "@" + chunk
            paper_doi = norm_doi(_extract_field(entry, "doi"))
            if not paper_doi:
                continue
            cited = _extract_field(entry, "cited-references")
            seen: set[str] = set()
            refs: list[str] = []
            for r in _split_refs(cited):
                d = norm_doi(r)
                if d and d not in seen:
                    seen.add(d)
                    refs.append(d)
            out[paper_doi] = refs
    return out
