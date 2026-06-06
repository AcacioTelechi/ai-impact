"""Normalização e extração de DOI (Plano 6).

Identidade canônica de referência em toda a linha bibliométrica. Um DOI é
reduzido à forma "bare" minúscula (sem prefixo de URL, sem 'doi:'/'DOI ',
sem pontuação final). Strings sem DOI retornam "".
"""
from __future__ import annotations

import re

# DOI: 10.<registrant>/<suffix>; o sufixo vai até espaço/fim (refs WoS têm vírgulas
# antes do 'DOI ', então o token de DOI em si não contém espaço).
_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s]+")
_TRAILING = ".,;:)]}'\"<>"


def norm_doi(raw: str) -> str:
    if not raw:
        return ""
    s = str(raw).strip().lower()
    for pref in ("https://doi.org/", "http://doi.org/", "doi.org/", "doi:", "doi "):
        if s.startswith(pref):
            s = s[len(pref):]
    m = _DOI_RE.search(s)
    if not m:
        return ""
    return m.group(0).rstrip(_TRAILING)
