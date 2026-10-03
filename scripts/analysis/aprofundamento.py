"""Aprofundamento da análise (revisão 2026-09-19) — tabelas e figura da Discussão.

Responde a quatro perguntas que a comparação pré/pós bruta deixa em aberto:
1. A H1 é sensível à definição de período e ao subconjunto? (`h1_sensibilidade`)
2. O risco para alta qualificação segue a DATA ou o OBJETO tecnológico?
   (`polarizacao_tecnologia`, `logit_h1`, figura `h1_tendencia_anual`)
3. O sinal sobre o emprego depende do que se mede? (`sinal_por_tipo`)
4. As mudanças pré/pós são de composição do corpus ou ocorrem dentro dos tipos
   de estudo? (`composicao_ajuste`, `perfis_mecanismos`, `multiplos_testes`,
   `validade_fonte`)

Tudo exploratório (censo, não amostra). Funções puras + I/O isolado em `run`.
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import chi2_contingency, fisher_exact
from statsmodels.stats.multitest import multipletests

from scripts.analysis.corpus import load_corpus
from scripts.analysis.stats import NA_VALORES, RESSALVA, wilson95
from scripts.analysis.texkit import CANON, MECANISMOS, escape, fmt_p, fmt_pct, tabela_booktabs

ALTA = "alta-quali em risco"
GENAI = "IA generativa/LLMs"
EMPIRICOS = ("exposição ocupacional", "evidência macro/setorial", "firma/freelancer", "indivíduo")


def _ok(s: pd.Series) -> pd.Series:
    return ~s.fillna("").astype(str).str.strip().str.lower().isin(NA_VALORES)


def _num(x: float, nd: int = 2) -> str:
    return f"{x:.{nd}f}".replace(".", "{,}")


def preparar(df: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta as covariáveis binárias usadas nos modelos (não muta o original)."""
    d = df.copy()
    d["ano"] = pd.to_numeric(d["ano"], errors="coerce")
    d["pos"] = (d["pre_pos_chatgpt"] == "pos").astype(int)
    d["genai"] = (d["tecnologia_focada"] == GENAI).astype(int)
    d["china"] = d["pais_estudo"].str.contains("China", case=False).astype(int)
    d["q4"] = (d["score_qualidade"] >= 4).astype(int)
    d["pdf"] = (d["text_source"] == "pdf").astype(int)
    # 'indivíduo' (n=6) é drift do enum; agrega à evidência micro de firma
    d["tipo"] = d["tipo_estudo"].replace({"indivíduo": "firma/freelancer"})
    return d


def cramers_v(tab: pd.DataFrame) -> tuple[float, float, float]:
    chi2, p, _, _ = chi2_contingency(tab)
    n = tab.values.sum()
    return float(chi2), float(p), float(np.sqrt(chi2 / (n * (min(tab.shape) - 1))))


def fisher_pre_pos(sub: pd.DataFrame, alvo: pd.Series, col: str = "pre_pos_chatgpt") -> dict:
    """2×2 período × alvo. OR orientada como chances(pós)/chances(pré)."""
    k = {p: int(alvo[sub[col] == p].sum()) for p in ("pre", "pos")}
    n = {p: int((sub[col] == p).sum()) for p in ("pre", "pos")}
    odds, p = fisher_exact([[k["pos"], n["pos"] - k["pos"]], [k["pre"], n["pre"] - k["pre"]]])
    return {"k_pre": k["pre"], "n_pre": n["pre"], "k_pos": k["pos"], "n_pos": n["pos"],
            "or": float(odds), "p": float(p)}


# ---------------------------------------------------------------- 1. sensibilidade H1
def h1_especificacoes(d: pd.DataFrame) -> list[tuple[str, dict]]:
    pol = d[_ok(d["polarizacao"])].copy()
    alvo = pol["polarizacao"] == ALTA

    def f(mask=None, col="pre_pos_chatgpt"):
        sub = pol if mask is None else pol[mask]
        return fisher_pre_pos(sub, alvo.loc[sub.index], col)

    pol["p2024"] = np.where(pol["ano"] >= 2024, "pos", "pre")
    donut = (pol["ano"] <= 2021) | (pol["ano"] >= 2024)
    specs = [
        ("Principal: ano de publicação (pós = 2023+)", f()),
        ("Classificação original do LLM", f(col="pre_pos_chatgpt_llm")),
        ("Pivô alternativo: pós = 2024+ (defasagem editorial)", f(col="p2024")),
        ("Excluindo a transição 2022--2023", f(donut)),
        ("Apenas revisados por pares", f(pol["revisado_por_pares"] == "sim")),
        ("Apenas estudos empíricos", f(pol["tipo_estudo"].isin(EMPIRICOS))),
        ("Excluindo estudos sobre a China", f(pol["china"] == 0)),
        ("Excluindo estudos de IA generativa/LLMs", f(pol["genai"] == 0)),
        (r"Apenas \textit{score} de qualidade $\geq 4$", f(pol["q4"] == 1)),
        ("Apenas lidos em texto completo", f(pol["pdf"] == 1)),
    ]
    return specs


def tabela_h1_sensibilidade(specs) -> str:
    rows = []
    for rot, r in specs:
        rows.append([
            rot,
            f"{r['k_pre']}/{r['n_pre']} ({fmt_pct(r['k_pre'] / r['n_pre'])})",
            f"{r['k_pos']}/{r['n_pos']} ({fmt_pct(r['k_pos'] / r['n_pos'])})",
            _num(r["or"]), fmt_p(r["p"]),
        ])
    return tabela_booktabs(
        "p{6.6cm}cccc", ["Especificação", "Pré", "Pós", "RC", "Fisher"], rows,
        notas=["Fração de estudos que situam o risco na alta qualificação, entre os que "
               "classificaram a polarização. RC = razão de chances (pós/pré).", RESSALVA])


# ---------------------------------------------------------------- 2. objeto tecnológico
def tabela_polarizacao_tecnologia(d: pd.DataFrame) -> tuple[str, dict]:
    pol = d[_ok(d["polarizacao"]) & _ok(d["tecnologia_focada"])]
    tab = pd.crosstab(pol["tecnologia_focada"], pol["polarizacao"])
    rows = []
    for tec in CANON["tecnologia_focada"]:
        if tec not in tab.index or tab.loc[tec].sum() < 5:
            continue
        n = int(tab.loc[tec].sum())
        rows.append([escape(tec), str(n)] + [
            fmt_pct(tab.loc[tec].get(c, 0) / n) for c in CANON["polarizacao"]])
    g = pol["tecnologia_focada"] == GENAI
    a = pol["polarizacao"] == ALTA
    odds, p = fisher_exact([[int((g & a).sum()), int((g & ~a).sum())],
                            [int((~g & a).sum()), int((~g & ~a).sum())]])
    tex = tabela_booktabs(
        "lrcccc", ["Tecnologia em foco", "$n$", "Baixa-quali", "Alta-quali", "Ambos", "Neutro"],
        rows,
        notas=[f"Percentuais na linha, sobre os estudos que classificaram a polarização "
               f"(categorias com $n<5$ omitidas). IA generativa vs.\\ demais, alta-quali em "
               f"risco: RC $={_num(odds)}$, Fisher " + fmt_p(p) + ".", RESSALVA])
    return tex, {"or_genai": float(odds), "p_genai": float(p)}


def logit_h1(d: pd.DataFrame):
    pol = d[_ok(d["polarizacao"]) & _ok(d["tipo"])].copy()
    pol["alta"] = (pol["polarizacao"] == ALTA).astype(int)
    formulas = ["alta ~ pos", "alta ~ pos + genai",
                "alta ~ pos + genai + C(tipo) + china + q4 + pdf"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return [smf.logit(f, pol).fit(disp=0) for f in formulas]


_ROTULO_TERMO = {
    "pos": "Publicado em 2023+", "genai": "Objeto: IA generativa/LLMs",
    "C(tipo)[T.exposição ocupacional]": "Tipo: exposição ocupacional",
    "C(tipo)[T.firma/freelancer]": "Tipo: firma/\\textit{freelancer}",
    "C(tipo)[T.survey/revisão]": "Tipo: \\textit{survey}/revisão",
    "C(tipo)[T.teórico/modelo]": "Tipo: teórico/modelo",
    "china": "País-foco: China", "q4": "\\textit{Score} $\\geq 4$", "pdf": "Texto completo",
}


def tabela_logit(modelos) -> str:
    def cel(m, termo):
        if termo not in m.params:
            return "---"
        lo, hi = np.exp(m.conf_int().loc[termo])
        est = "*" if m.pvalues[termo] < 0.05 else ""
        return f"{_num(np.exp(m.params[termo]))}{est} [{_num(lo)}; {_num(hi)}]"
    rows = [[rot] + [cel(m, t) for m in modelos] for t, rot in _ROTULO_TERMO.items()]
    rows.append(["$n$"] + [str(int(m.nobs)) for m in modelos])
    rows.append(["Pseudo-$R^2$ (McFadden)"] + [_num(m.prsquared, 3) for m in modelos])
    return tabela_booktabs(
        "p{5.2cm}ccc", ["", "(1)", "(2)", "(3)"], rows,
        notas=["Logit; variável dependente: o estudo situa o risco na alta qualificação. "
               "Razões de chances com IC 95\\% entre colchetes; * $p<0{,}05$. Categoria de "
               "referência do tipo: evidência macro/setorial.", RESSALVA])


def figura_tendencia(d: pd.DataFrame, out: Path) -> dict:
    pol = d[_ok(d["polarizacao"])].copy()
    pol["alta"] = (pol["polarizacao"] == ALTA).astype(int)
    g = pol[pol["ano"] >= 2018].groupby("ano")["alta"].agg(["sum", "count"])
    pct = g["sum"] / g["count"] * 100
    ci = np.array([wilson95(int(k), int(n)) for k, n in zip(g["sum"], g["count"])]) * 100
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m = smf.logit("alta ~ ano", pol).fit(disp=0)
        m2 = smf.logit("alta ~ ano", pol[pol["genai"] == 0]).fit(disp=0)
    cor, tinta, grade = "#2a5d9f", "#333333", "#dddddd"
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    ax.axvspan(2022.5, g.index.max() + 0.5, color="#f1f1f1", zorder=0)
    ax.fill_between(g.index, ci[:, 0], ci[:, 1], color=cor, alpha=0.15, linewidth=0)
    ax.plot(g.index, pct, color=cor, linewidth=2, marker="o", markersize=5, clip_on=False)
    for x, y, n in zip(g.index, pct, g["count"]):
        ax.annotate(f"n={n}", (x, y), textcoords="offset points", xytext=(0, 8),
                    ha="center", fontsize=7, color=tinta)
    ax.text(2022.57, ax.get_ylim()[1] * 0.93, "pós-ChatGPT", fontsize=8, color=tinta)
    ax.set_ylabel("% dos estudos classificados", fontsize=9, color=tinta)
    ax.set_xticks(list(g.index))
    ax.tick_params(labelsize=8, colors=tinta, length=0)
    ax.grid(axis="y", color=grade, linewidth=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(grade)
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)
    return {"or_ano": float(np.exp(m.params["ano"])), "p_ano": float(m.pvalues["ano"]),
            "or_ano_sem_genai": float(np.exp(m2.params["ano"])),
            "p_ano_sem_genai": float(m2.pvalues["ano"]),
            "por_ano": {int(a): [int(k), int(n)] for a, k, n in zip(g.index, g["sum"], g["count"])}}


# ---------------------------------------------------------------- 3. sinal × objeto medido
def tabela_sinal_por_tipo(d: pd.DataFrame) -> tuple[str, dict]:
    s = d[_ok(d["sinal_efeito"]) & _ok(d["tipo"])]
    tab = pd.crosstab(s["tipo"], s["sinal_efeito"])
    chi2, p, v = cramers_v(tab)
    rows = []
    for t in CANON["tipo_estudo"]:
        if t in tab.index:
            n = int(tab.loc[t].sum())
            rows.append([escape(t), str(n)] + [fmt_pct(tab.loc[t].get(c, 0) / n)
                                                for c in CANON["sinal_efeito"]])
    tex = tabela_booktabs(
        "lrcccc", ["Tipo de evidência", "$n$", "Negativo", "Positivo", "Nulo", "Ambíguo"], rows,
        notas=[f"Percentuais na linha. $\\chi^2={_num(chi2)}$, " + fmt_p(p)
               + f", $V$ de Cramér $={_num(v)}$. `Indivíduo' ($n=6$) agregado a "
               "firma/\\textit{freelancer}.", RESSALVA])
    return tex, {"chi2": chi2, "p": p, "v": v}


# ---------------------------------------------------------------- 4. composição
DESFECHOS = [
    ("Risco na alta qualificação", "polarizacao", ALTA),
    ("Sinal negativo", "sinal_efeito", "negativo"),
    ("Sinal positivo", "sinal_efeito", "positivo"),
    ("Invoca deslocamento", "mec_deslocamento", "sim"),
    ("Invoca complementaridade", "mec_complementaridade", "sim"),
    ("Invoca demanda agregada", "mec_demanda_agregada", "sim"),
    ("Horizonte de longo prazo/projeção", "horizonte", ("longo prazo", "projeção")),
]


def composicao(d: pd.DataFrame) -> list[dict]:
    out = []
    for rot, col, alvo in DESFECHOS:
        s = d[_ok(d[col]) & _ok(d["tipo"])].copy()
        alvos = alvo if isinstance(alvo, tuple) else (alvo,)
        s["y"] = s[col].isin(alvos).astype(int)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            bruto = smf.logit("y ~ pos", s).fit(disp=0)
            ajust = smf.logit("y ~ pos + C(tipo) + genai + china + q4", s).fit(disp=0)
        out.append({"rotulo": rot, "n": int(len(s)),
                    "pre": float(s[s.pos == 0].y.mean()), "pos": float(s[s.pos == 1].y.mean()),
                    "or_b": float(np.exp(bruto.params["pos"])), "p_b": float(bruto.pvalues["pos"]),
                    "or_a": float(np.exp(ajust.params["pos"])), "p_a": float(ajust.pvalues["pos"])})
    return out


def tabela_composicao(res: list[dict]) -> str:
    rows = [[r["rotulo"], fmt_pct(r["pre"]), fmt_pct(r["pos"]),
             f"{_num(r['or_b'])} ({fmt_p(r['p_b'])})", f"{_num(r['or_a'])} ({fmt_p(r['p_a'])})"]
            for r in res]
    return tabela_booktabs(
        "p{5.0cm}cccc", ["Desfecho", "Pré", "Pós", "RC bruta", "RC ajustada"], rows,
        notas=["RC do indicador ``publicado em 2023+'' em logit sem controles (bruta) e com "
               "controles para tipo de evidência, objeto IA generativa, país-foco China e "
               "\\textit{score} $\\geq 4$ (ajustada). Uma RC que se aproxima de 1 após o ajuste "
               "indica mudança de composição do corpus, e não mudança dentro dos tipos.", RESSALVA])


def perfis_mecanismos(d: pd.DataFrame) -> tuple[str, dict]:
    cols = list(MECANISMOS)
    m = d[np.logical_and.reduce([_ok(d[c]) for c in cols])].copy()
    desl = m["mec_deslocamento"] == "sim"
    comp = (m[cols[1:]] == "sim").any(axis=1)
    m["perfil"] = np.select([desl & ~comp, desl & comp, ~desl & comp],
                            ["Só deslocamento", "Deslocamento + compensação", "Só compensação"],
                            "Nenhum")
    ordem = ["Só deslocamento", "Deslocamento + compensação", "Só compensação"]
    m = m[m["perfil"].isin(ordem)]
    tab = pd.crosstab(m["perfil"], m["pre_pos_chatgpt"])
    chi2, p, v = cramers_v(tab)
    sinal = m[_ok(m["sinal_efeito"])]
    ts = pd.crosstab(sinal["perfil"], sinal["sinal_efeito"], normalize="index")
    rows = [[pf, fmt_pct(tab.loc[pf, "pre"] / tab["pre"].sum()),
             fmt_pct(tab.loc[pf, "pos"] / tab["pos"].sum()),
             fmt_pct(ts.loc[pf].get("negativo", 0)), fmt_pct(ts.loc[pf].get("positivo", 0)),
             fmt_pct(ts.loc[pf].get("ambíguo", 0))] for pf in ordem]
    tex = tabela_booktabs(
        "lccccc", ["Perfil de mecanismos", "Pré", "Pós", "Negativo", "Positivo", "Ambíguo"], rows,
        notas=[f"Colunas Pré/Pós: participação do perfil no período ($\\chi^2={_num(chi2)}$, "
               + fmt_p(p) + "). Demais colunas: sinal sobre o emprego dentro de cada perfil. "
               "`Compensação' = reinstalação, complementaridade ou demanda agregada.", RESSALVA])
    return tex, {"chi2": chi2, "p": p}


def familia_testes(d: pd.DataFrame) -> list[tuple[str, float]]:
    fam = []
    for rot, col in [("Polarização (distribuição completa)", "polarizacao"),
                     ("Sinal sobre o emprego", "sinal_efeito"),
                     ("Tipo de evidência", "tipo_estudo"), ("Horizonte", "horizonte")]:
        s = d[_ok(d[col])]
        fam.append((rot, cramers_v(pd.crosstab(s[col], s["pre_pos_chatgpt"]))[1]))
    pol = d[_ok(d["polarizacao"])]
    fam.append(("Risco na alta qualificação (H1)",
                fisher_pre_pos(pol, pol["polarizacao"] == ALTA)["p"]))
    for col, rot in MECANISMOS.items():
        s = d[_ok(d[col])]
        fam.append((rot, fisher_pre_pos(s, s[col] == "sim")["p"]))
    return fam


def tabela_multiplos(fam) -> str:
    adj = multipletests([p for _, p in fam], method="holm")[1]
    rows = [[r, fmt_p(p), fmt_p(a), "sim" if a < 0.05 else "não"]
            for (r, p), a in zip(fam, adj)]
    return tabela_booktabs(
        "lccc", ["Teste pré/pós", "$p$ bruto", "$p$ Holm", "$<0{,}05$"], rows,
        notas=["Correção de Holm sobre a família dos nove testes pré/pós do "
               "Capítulo~\\ref{cap:comparacao}.", RESSALVA])


def tabela_validade_fonte(d: pd.DataFrame) -> str:
    rows = []
    for rot, col in [("Polarização", "polarizacao"), ("Sinal sobre o emprego", "sinal_efeito"),
                     ("Tipo de evidência", "tipo_estudo"), ("Horizonte", "horizonte")]:
        na = pd.crosstab(d["text_source"], ~_ok(d[col]), normalize="index")
        s = d[_ok(d[col])]
        _, p, v = cramers_v(pd.crosstab(s[col], s["text_source"]))
        rows.append([rot, fmt_pct(na.loc["abstract"].get(True, 0)),
                     fmt_pct(na.loc["pdf"].get(True, 0)), _num(v), fmt_p(p)])
    return tabela_booktabs(
        "lcccc", ["Dimensão", "n/a (resumo)", "n/a (texto compl.)", "$V$", "$\\chi^2$"], rows,
        notas=["Compara os estudos extraídos do resumo com os lidos em texto completo: taxa de "
               "não classificação e associação entre a fonte e a distribuição das categorias.",
               RESSALVA])


# ---------------------------------------------------------------- 5. robótica como comparação
ROBOS = ("robôs+IA", "automação")
CAUSAL = ("IV", "DiD", "RDD", "evento-estudo")


def placebo_tecnologia(d: pd.DataFrame) -> list[dict]:
    """Pré/pós DENTRO de cada objeto. Se a mudança é do objeto (IA generativa), a
    robótica/automação não deve mudar (placebo); se muda, é efeito de época."""
    grupos = [("Robótica e automação", d["tecnologia_focada"].isin(ROBOS)),
              ("IA em geral", d["tecnologia_focada"] == "geral")]
    out = []
    for rot, col, alvo in DESFECHOS:
        alvos = alvo if isinstance(alvo, tuple) else (alvo,)
        linha = {"rotulo": rot}
        for g, mask in grupos:
            s = d[mask & _ok(d[col])]
            linha[g] = fisher_pre_pos(s, s[col].isin(alvos))
        out.append(linha)
    return out


def tabela_placebo(res: list[dict]) -> str:
    def cel(r):
        return [fmt_pct(r["k_pre"] / r["n_pre"]), fmt_pct(r["k_pos"] / r["n_pos"]), fmt_p(r["p"])]
    rows = [[r["rotulo"]] + cel(r["Robótica e automação"]) + cel(r["IA em geral"]) for r in res]
    tex = tabela_booktabs("p{3.9cm}cccccc",
                          ["Desfecho", "Pré", "Pós", "Fisher", "Pré", "Pós", "Fisher"], rows,
                          notas=["Colunas 2--4: estudos cujo objeto é robótica ou automação "
                                 "(placebo). Colunas 5--7: estudos que tratam a IA de modo geral. "
                                 "Os estudos de IA generativa não comportam o teste, pois só um é "
                                 "anterior a 2023.", RESSALVA])
    cab = ("\\toprule\n & \\multicolumn{3}{c}{Robótica e automação} & "
           "\\multicolumn{3}{c}{IA em geral} \\\\\n\\cmidrule(lr){2-4}\\cmidrule(lr){5-7}")
    return tex.replace("\\toprule", cab, 1)

def robos_vs_genai(d: pd.DataFrame) -> list[tuple[str, float, float, float]]:
    """Confronto direto, só entre publicados em 2023+ (iguala o calendário)."""
    pos = d[d["pos"] == 1]
    r, g = pos[pos["tecnologia_focada"] == "robôs+IA"], pos[pos["genai"] == 1]
    itens = [("Risco na alta qualificação", "polarizacao", (ALTA,)),
             ("Risco na baixa qualificação", "polarizacao", ("baixa-quali em risco",)),
             ("Sinal negativo", "sinal_efeito", ("negativo",)),
             ("Sinal positivo", "sinal_efeito", ("positivo",)),
             ("Invoca deslocamento", "mec_deslocamento", ("sim",)),
             ("Invoca reinstalação", "mec_reinstalacao", ("sim",)),
             ("Invoca complementaridade", "mec_complementaridade", ("sim",)),
             ("Invoca demanda agregada", "mec_demanda_agregada", ("sim",)),
             ("Horizonte de curto prazo", "horizonte", ("curto prazo",)),
             ("Tipo: \\textit{survey}/revisão", "tipo_estudo", ("survey/revisão",)),
             ("Tipo: evidência macro/setorial", "tipo_estudo", ("evidência macro/setorial",)),
             ("Método com identificação causal", "metodo_empirico", CAUSAL),
             ("\\textit{Score} de qualidade $\\geq 4$", None, None)]
    out = []
    for rot, col, alvos in itens:
        if col is None:
            yr, yg = r["q4"] == 1, g["q4"] == 1
        else:
            yr, yg = r[_ok(r[col])][col].isin(alvos), g[_ok(g[col])][col].isin(alvos)
        _, p = fisher_exact([[int(yg.sum()), int((~yg).sum())], [int(yr.sum()), int((~yr).sum())]])
        out.append((rot, float(yr.mean()), float(yg.mean()), float(p)))
    return out, len(r), len(g)


def tabela_robos_vs_genai(res, n_r: int, n_g: int) -> str:
    rows = [[rot, fmt_pct(a), fmt_pct(b), fmt_p(p)] for rot, a, b, p in res]
    return tabela_booktabs(
        "lccc", ["Característica", f"Robôs+IA ($n={n_r}$)", f"IA generativa ($n={n_g}$)", "Fisher"],
        rows, notas=["Apenas estudos publicados de 2023 em diante. Proporções sobre os estudos que "
                     "classificaram cada dimensão. Identificação causal: IV, DiD, RDD ou estudo de "
                     "evento.", RESSALVA])


def run(input: Path, tab_dir: Path, fig_dir: Path, json_out: Path | None = None) -> dict:
    d = preparar(load_corpus(input).df)
    tab_dir.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)
    nums: dict = {"n": len(d), "n_pre": int((d.pos == 0).sum()), "n_pos": int((d.pos == 1).sum())}
    specs = h1_especificacoes(d)
    nums["h1"] = {r: v for r, v in specs}
    (tab_dir / "h1_sensibilidade.tex").write_text(tabela_h1_sensibilidade(specs), "utf-8")
    tex, nums["tecnologia"] = tabela_polarizacao_tecnologia(d)
    (tab_dir / "polarizacao_tecnologia.tex").write_text(tex, "utf-8")
    (tab_dir / "logit_h1.tex").write_text(tabela_logit(logit_h1(d)), "utf-8")
    nums["tendencia"] = figura_tendencia(d, fig_dir / "h1_tendencia_anual.pdf")
    tex, nums["sinal_tipo"] = tabela_sinal_por_tipo(d)
    (tab_dir / "sinal_por_tipo.tex").write_text(tex, "utf-8")
    nums["composicao"] = composicao(d)
    (tab_dir / "composicao_ajuste.tex").write_text(tabela_composicao(nums["composicao"]), "utf-8")
    tex, nums["perfis"] = perfis_mecanismos(d)
    (tab_dir / "perfis_mecanismos.tex").write_text(tex, "utf-8")
    (tab_dir / "multiplos_testes.tex").write_text(tabela_multiplos(familia_testes(d)), "utf-8")
    (tab_dir / "validade_fonte.tex").write_text(tabela_validade_fonte(d), "utf-8")
    nums["placebo"] = placebo_tecnologia(d)
    (tab_dir / "placebo_tecnologia.tex").write_text(tabela_placebo(nums["placebo"]), "utf-8")
    res, n_r, n_g = robos_vs_genai(d)
    nums["robos_vs_genai"] = res
    (tab_dir / "robos_vs_genai.tex").write_text(tabela_robos_vs_genai(res, n_r, n_g), "utf-8")
    if json_out:
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(nums, ensure_ascii=False, indent=1), "utf-8")
    print(f"Aprofundamento: 10 tabelas em {tab_dir}, 1 figura em {fig_dir}")
    return nums


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--tab-dir", type=Path, required=True)
    p.add_argument("--fig-dir", type=Path, required=True)
    p.add_argument("--json-out", type=Path, default=None)
    a = p.parse_args(argv)
    run(a.input, a.tab_dir, a.fig_dir, a.json_out)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
