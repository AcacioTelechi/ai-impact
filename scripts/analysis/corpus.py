"""Fonte única da verdade do corpus de análise (Plano 5).

Filtra 06_extraction.csv para os incluídos-e-extraídos:
`elegivel == "incluir"` e `nota_extracao != "parse_fail"`.

Os contadores ``n_pendentes`` e ``n_excluidos`` são calculados sobre o arquivo
inteiro (não sobre o df filtrado) e NÃO formam uma partição disjunta com ``n``.
``n_pendentes`` = estudos ``incluir`` ainda sem extração (parse_fail, pendentes de
re-rodada). Não mutar ``.df``: ele é compartilhado por referência entre os módulos
de análise.

``load_corpus`` também normaliza a coluna ``horizonte``, colapsando o drift de
extração do LLM: "médio" → "médio prazo" e "longo" → "longo prazo".

PERÍODO DETERMINÍSTICO (revisão 2026-09-19). O prompt de extração pedia ``janela`` e
``pre_pos_chatgpt`` ao LLM sem dizer "data de publicação"; o modelo misturou data de
publicação com o período dos dados (115 estudos publicados em 2023–2026 saíram como
"pre"). Como o texto define o período pela PUBLICAÇÃO, ``load_corpus`` passa a derivar
as duas colunas do ``ano`` (bloco A, determinístico): pré = ano ≤ 2022; pós = ano ≥ 2023
(granularidade anual: as bases não trazem mês confiável). Os valores originais do LLM
são preservados em ``pre_pos_chatgpt_llm`` e ``janela_llm`` para análise de sensibilidade.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

INCLUIDO = "incluir"
PARSE_FAIL = "parse_fail"
_NUMERICAS = ("score_qualidade", "magnitude_normalizada")

# Drift de extração: o LLM emitiu "médio"/"longo" e "médio prazo"/"longo prazo"
# para o mesmo horizonte. Colapsa nas formas com "prazo" (ver CANON em texkit).
_HORIZONTE_NORM = {"médio": "médio prazo", "longo": "longo prazo"}

ANO_PIVO = 2023  # primeiro ano-calendário "pós-ChatGPT" (lançamento em 2022-11-30)


def periodo_por_ano(ano: float) -> str:
    if pd.isna(ano):
        return ""
    return "pos" if ano >= ANO_PIVO else "pre"


def janela_por_ano(ano: float) -> str:
    if pd.isna(ano):
        return ""
    if ano <= 2017:
        return "2013-2017"
    return "2018-2022" if ano < ANO_PIVO else "2022-2026"


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
    if "ano" in df.columns:
        ano = pd.to_numeric(df["ano"], errors="coerce")
        for col, fn in (("pre_pos_chatgpt", periodo_por_ano), ("janela", janela_por_ano)):
            if col in df.columns:
                df[col + "_llm"] = df[col]
            df[col] = ano.map(fn)
    if "horizonte" in df.columns:
        df["horizonte"] = (
            df["horizonte"].astype(str).str.strip().replace(_HORIZONTE_NORM)
        )
    return CorpusAnalise(
        df=df.reset_index(drop=True),
        n=int(len(df)),
        n_pendentes=int((incluidos & parse_fail).sum()),
        n_excluidos=int((raw["elegivel"] != INCLUIDO).sum()),
    )
