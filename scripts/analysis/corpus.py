"""Fonte única da verdade do corpus de análise (Plano 5).

Filtra 06_extraction.csv para os incluídos-e-extraídos:
`elegivel == "incluir"` e `nota_extracao != "parse_fail"`.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

INCLUIDO = "incluir"
PARSE_FAIL = "parse_fail"
_NUMERICAS = ("score_qualidade", "magnitude_normalizada")


@dataclass(frozen=True)
class CorpusAnalise:
    df: pd.DataFrame
    n: int
    n_pendentes: int
    n_excluidos: int


def load_corpus(path: Path) -> CorpusAnalise:
    raw = pd.read_csv(path, encoding="utf-8", dtype=str).fillna("")
    incluidos = raw["elegivel"] == INCLUIDO
    parse_fail = raw["nota_extracao"] == PARSE_FAIL
    df = raw[incluidos & ~parse_fail].copy()
    for col in _NUMERICAS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    return CorpusAnalise(
        df=df.reset_index(drop=True),
        n=int(len(df)),
        n_pendentes=int(parse_fail.sum()),
        n_excluidos=int((raw["elegivel"] != INCLUIDO).sum()),
    )
