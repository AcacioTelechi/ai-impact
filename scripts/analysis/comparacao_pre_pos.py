"""Cap 06 — comparação pré/pós-ChatGPT (capítulo central, Plano 5).

4 tabelas: central (multi-dimensão + χ²/Fisher), foco H1 (polarização 2×2 + Fisher
+ Wilson), robustez (score≥4) e cobertura de magnitude (descritivo, sem teste).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from scripts.analysis.corpus import load_corpus
from scripts.analysis.stats import (
    RESSALVA,
    assoc_chi2,
    assoc_fisher_2x2,
    prop_por_periodo,
    wilson95,
)
from scripts.analysis.texkit import (
    CANON,
    MECANISMOS,
    escape,
    fmt_ci,
    fmt_p,
    fmt_pct,
    tabela_booktabs,
)

FOCO_H1 = "alta-quali em risco"
DIMS_MULTI = ("polarizacao", "sinal_efeito", "tipo_estudo", "horizonte")
DIM_LABEL = {
    "polarizacao": "Polarização (quem está em risco)",
    "sinal_efeito": "Sinal sobre o emprego",
    "tipo_estudo": "Tipo de evidência",
    "horizonte": "Horizonte",
}


def _linhas_dim(df: pd.DataFrame, dim: str) -> list[list[str]]:
    prop = prop_por_periodo(df, dim)
    chi = assoc_chi2(prop)
    chi2_str = f"{chi.chi2:.2f}".replace(".", "{,}")
    cab = [
        DIM_LABEL[dim]
        + f" — $\\chi^2={chi2_str}$, $\\mathrm{{gl}}={chi.dof}$, " + fmt_p(chi.p)
        + (" (células esperadas <5)" if chi.low_expected else ""),
        "", "",
    ]
    rows = [cab]
    for cat in CANON[dim]:
        if prop.counts["pre"].get(cat, 0) or prop.counts["pos"].get(cat, 0):
            rows.append([
                r"\quad " + escape(cat),
                fmt_pct(prop.pct("pre", cat)),
                fmt_pct(prop.pct("pos", cat)),
            ])
    return rows


def _tabela_central(df: pd.DataFrame, n_pre: int, n_pos: int) -> str:
    rows: list[list[str]] = []
    for dim in DIMS_MULTI:
        rows.extend(_linhas_dim(df, dim))
    # mecanismos: cada um é binário -> linha com Fisher próprio
    rows.append(["Mecanismos teóricos (\\% que invoca)", "", ""])
    for mec, rotulo in MECANISMOS.items():
        f = assoc_fisher_2x2(df, mec, foco="sim")
        rows.append([
            r"\quad " + rotulo + " (" + fmt_p(f.p) + ")",
            fmt_pct(f.k_pre / f.n_pre if f.n_pre else 0.0),
            fmt_pct(f.k_pos / f.n_pos if f.n_pos else 0.0),
        ])
    return tabela_booktabs(
        "lcc",
        ["Dimensão / categoria", f"Pré (n={n_pre})", f"Pós (n={n_pos})"],
        rows,
        notas=[RESSALVA, "Proporções calculadas sobre os estudos que classificaram cada dimensão (n/a fora do denominador); o denominador varia por linha."],
    )


def _tabela_polarizacao(df: pd.DataFrame) -> str:
    f = assoc_fisher_2x2(df, "polarizacao", foco=FOCO_H1)
    lo_pre, hi_pre = wilson95(f.k_pre, f.n_pre)
    lo_pos, hi_pos = wilson95(f.k_pos, f.n_pos)
    rows = [
        [escape(FOCO_H1),
         f"{fmt_pct(f.k_pre / f.n_pre if f.n_pre else 0)} {fmt_ci(lo_pre, hi_pre)}",
         f"{fmt_pct(f.k_pos / f.n_pos if f.n_pos else 0)} {fmt_ci(lo_pos, hi_pos)}"],
        ["Demais categorias",
         fmt_pct((f.n_pre - f.k_pre) / f.n_pre if f.n_pre else 0),
         fmt_pct((f.n_pos - f.k_pos) / f.n_pos if f.n_pos else 0)],
    ]
    return tabela_booktabs(
        "lcc",
        ["Polarização", f"Pré (n={f.n_pre})", f"Pós (n={f.n_pos})"],
        rows,
        notas=[f"Fisher exato: razão de chances $={f.odds_ratio:.2f}$".replace(".", "{,}") + ", " + fmt_p(f.p)
               + "; IC Wilson 95\\% entre colchetes.", RESSALVA],
    )


def _tabela_robustez(df: pd.DataFrame) -> str:
    alta = df[df["score_qualidade"] >= 4]
    f = assoc_fisher_2x2(alta, "polarizacao", foco=FOCO_H1)
    rows = [
        ["Alta-quali em risco",
         fmt_pct(f.k_pre / f.n_pre if f.n_pre else 0),
         fmt_pct(f.k_pos / f.n_pos if f.n_pos else 0)],
        ["Demais categorias",
         fmt_pct((f.n_pre - f.k_pre) / f.n_pre if f.n_pre else 0),
         fmt_pct((f.n_pos - f.k_pos) / f.n_pos if f.n_pos else 0)],
    ]
    return tabela_booktabs(
        "lcc",
        ["Polarização (score$\\geq$4)", f"Pré (n={f.n_pre})", f"Pós (n={f.n_pos})"],
        rows,
        notas=[f"Subconjunto de robustez: estudos com score de qualidade $\\geq 4$. "
               f"$n$ é o número com polarização classificada nesse subconjunto (n/a fora). "
               f"Fisher exato: " + fmt_p(f.p) + ". Células pequenas; leitura cautelosa.",
               RESSALVA],
    )


def _tabela_magnitude(df: pd.DataFrame) -> str:
    def linha(rotulo, fn):
        vals = []
        for per in ("pre", "pos"):
            s = pd.to_numeric(df[df["pre_pos_chatgpt"] == per]["magnitude_normalizada"],
                              errors="coerce").dropna()
            vals.append(fn(s))
        return [rotulo, vals[0], vals[1]]

    def cobertura(per):
        sub = df[df["pre_pos_chatgpt"] == per]
        k = int(pd.to_numeric(sub["magnitude_normalizada"], errors="coerce").notna().sum())
        n = int(len(sub))
        return f"{k}/{n} ({fmt_pct(k / n if n else 0)})"

    def stat(s, fn, default="—"):
        return f"{fn(s):.3f}".replace(".", ",") if len(s) else default

    rows = [
        ["Cobertura (normalizável)", cobertura("pre"), cobertura("pos")],
        linha("Mediana", lambda s: stat(s, lambda x: x.median())),
        linha("Q1--Q3", lambda s: (f"[{s.quantile(.25):.3f}; {s.quantile(.75):.3f}]".replace(".", ",")
                                   if len(s) else "—")),
        linha("Faixa (mín--máx)", lambda s: (f"[{s.min():.3f}; {s.max():.3f}]".replace(".", ",")
                                            if len(s) else "—")),
    ]
    return tabela_booktabs(
        "lcc",
        ["Magnitude normalizada", "Pré", "Pós"],
        rows,
        notas=["Sem teste de hipótese: cobertura baixa, unidades heterogêneas, não-pooling "
               "(revisão narrativa-estruturada, não meta-analítica)."],
    )


def run(input: Path, output_dir: Path) -> None:
    corpus = load_corpus(input)
    df = corpus.df
    n_pre = int((df["pre_pos_chatgpt"] == "pre").sum())
    n_pos = int((df["pre_pos_chatgpt"] == "pos").sum())
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "comparacao_pre_pos.tex").write_text(_tabela_central(df, n_pre, n_pos), encoding="utf-8")
    (output_dir / "polarizacao_pre_pos.tex").write_text(_tabela_polarizacao(df), encoding="utf-8")
    (output_dir / "robustez_qualidade.tex").write_text(_tabela_robustez(df), encoding="utf-8")
    (output_dir / "magnitude_cobertura.tex").write_text(_tabela_magnitude(df), encoding="utf-8")
    print(f"Cap 06: 4 tabelas em {output_dir} (pré={n_pre}, pós={n_pos})")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args(argv)
    run(args.input, args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
