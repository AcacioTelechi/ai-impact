"""Proporções e testes de associação (puros, sem I/O) — Plano 5.

Convenção central: `n/a` e vazio NUNCA entram no denominador das proporções.
Testes de associação são exploratórios (corpus é censo, não amostra) — ver RESSALVA.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd
from scipy.stats import chi2_contingency, fisher_exact

NA_VALORES = {"n/a", "", "nan"}
RESSALVA = (
    "O corpus é o censo dos estudos incluídos, não uma amostra aleatória; "
    "os testes de associação devem ser lidos como exploratórios."
)


def _norm(serie: pd.Series) -> pd.Series:
    return serie.fillna("").astype(str).str.strip()


def _classificados(serie: pd.Series) -> pd.Series:
    s = _norm(serie)
    return s[~s.str.lower().isin(NA_VALORES)]


@dataclass
class PropResult:
    counts: dict           # periodo -> {categoria: int}  (n/a excluído)
    n_classif: dict        # periodo -> int (denominador)
    n_na: dict             # periodo -> int

    def pct(self, periodo: str, categoria: str) -> float:
        d = self.n_classif.get(periodo, 0)
        return (self.counts.get(periodo, {}).get(categoria, 0) / d) if d else 0.0


def prop_por_periodo(
    df: pd.DataFrame,
    dim: str,
    periodo_col: str = "pre_pos_chatgpt",
    periodos: tuple[str, ...] = ("pre", "pos"),
) -> PropResult:
    counts, n_classif, n_na = {}, {}, {}
    for p in periodos:
        sub = df[df[periodo_col] == p]
        classif = _classificados(sub[dim])
        vc = classif.value_counts()
        counts[p] = {str(k): int(v) for k, v in vc.items()}
        n_classif[p] = int(vc.sum())
        n_na[p] = int(len(sub) - vc.sum())
    return PropResult(counts=counts, n_classif=n_classif, n_na=n_na)


@dataclass
class ChiResult:
    chi2: float
    dof: int
    p: float
    low_expected: bool


def assoc_chi2(prop: PropResult) -> ChiResult:
    cats = sorted({c for per in prop.counts for c in prop.counts[per]})
    table = [[prop.counts[per].get(c, 0) for c in cats] for per in prop.counts]
    # remove colunas inteiramente nulas (categorias ausentes nos dois períodos)
    table = [list(col) for col in zip(*table)]               # transpõe -> cats x periodos
    table = [row for row in table if sum(row) > 0]
    table = [list(col) for col in zip(*table)]               # volta -> periodos x cats
    chi2, p, dof, expected = chi2_contingency(table)
    return ChiResult(chi2=float(chi2), dof=int(dof), p=float(p),
                     low_expected=bool((expected < 5).any()))


@dataclass
class FisherResult:
    odds_ratio: float
    p: float
    k_pre: int
    n_pre: int
    k_pos: int
    n_pos: int


def assoc_fisher_2x2(
    df: pd.DataFrame,
    dim: str,
    foco: str,
    periodo_col: str = "pre_pos_chatgpt",
    periodos: tuple[str, str] = ("pre", "pos"),
) -> FisherResult:
    foco_l = foco.strip().lower()
    k, n = {}, {}
    for p in periodos:
        classif = _classificados(df[df[periodo_col] == p][dim])
        k[p] = int((classif.str.lower() == foco_l).sum())
        n[p] = int(len(classif))
    table = [[k[periodos[0]], n[periodos[0]] - k[periodos[0]]],
             [k[periodos[1]], n[periodos[1]] - k[periodos[1]]]]
    odds, p = fisher_exact(table)
    return FisherResult(odds_ratio=float(odds), p=float(p),
                        k_pre=k[periodos[0]], n_pre=n[periodos[0]],
                        k_pos=k[periodos[1]], n_pos=n[periodos[1]])


def wilson95(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    z = 1.959963984540054
    phat = k / n
    denom = 1 + z * z / n
    centre = phat + z * z / (2 * n)
    margin = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))
    return ((centre - margin) / denom, (centre + margin) / denom)
