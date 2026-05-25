# Plano 5 — Análise/Síntese dos resultados — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir a camada de análise que transforma `06_extraction.csv` (756 incluídos-extraídos) nas figuras `.pdf` e tabelas `.tex` dos três capítulos de resultados do TCC.

**Architecture:** Núcleo compartilhado (`corpus` filtra o corpus; `stats` faz proporções e testes χ²/Fisher puros; `texkit` constrói LaTeX) consumido por três módulos de capítulo (`descritivas_corpus`, `sintese_janelas`, `comparacao_pre_pos`). Funções puras, sem estado em disco; re-rodar após recuperar os 61 só atualiza números.

**Tech Stack:** Python 3.12, pandas, scipy.stats (`chi2_contingency`, `fisher_exact`), matplotlib (`Agg`), pytest. Ambiente: `source .venv/bin/activate` (NUNCA `uv run` em comandos ad-hoc; o Makefile usa `PYTHON := uv run python` por convenção e não muda).

**Spec:** `docs/superpowers/specs/2026-05-25-plano-5-analise-sintese-design.md`

---

## File Structure

**Criar:**
- `scripts/analysis/corpus.py` — `load_corpus()` + `CorpusAnalise`; filtro canônico e coerção numérica.
- `scripts/analysis/stats.py` — `prop_por_periodo`, `assoc_chi2`, `assoc_fisher_2x2`, `wilson95`, `RESSALVA`, `NA_VALORES`.
- `scripts/analysis/texkit.py` — `CANON`, `escape`, `fmt_pct`, `fmt_p`, `fmt_ci`, `tabela_booktabs`.
- `scripts/analysis/sintese_janelas.py` — Cap 05 (figura + tabela).
- `tests/analysis/__init__.py`
- `tests/analysis/test_corpus.py`, `test_stats.py`, `test_texkit.py`, `test_descritivas.py`, `test_sintese_janelas.py`, `test_comparacao_pre_pos.py`

**Modificar (reescrever):**
- `scripts/analysis/descritivas_corpus.py` — Cap 04 (4 figuras + 1 tabela), sobre corpus filtrado.
- `scripts/analysis/comparacao_pre_pos.py` — Cap 06 (4 tabelas).
- `Makefile` — `analysis` + `analysis-descritivas`/`analysis-janelas`/`analysis-prepos`.
- `text/chapters/04_resultados_descritivas.tex`, `05_resultados_janelas.tex`, `06_comparacao_pre_pos.tex` — fiação dos novos artefatos.

**Convenções fixas (consistentes entre tarefas):**
- Coluna de período: `pre_pos_chatgpt` ∈ {`pre`, `pos`} (pivô 2022-11-30).
- Filtro do corpus: `elegivel == "incluir"` **e** `nota_extracao != "parse_fail"`.
- `NA_VALORES = {"n/a", "", "nan"}` (case-insensitive) — fora de todo denominador de proporção.
- Vírgula decimal pt-BR nas saídas `.tex`.
- `CorpusAnalise` (dataclass): `.df`, `.n`, `.n_pendentes`, `.n_excluidos`.
- `PropResult` (dataclass): `.counts` (periodo→{cat:int}), `.n_classif` (periodo→int), `.n_na` (periodo→int), método `.pct(periodo, cat)`.
- `ChiResult`: `.chi2`, `.dof`, `.p`, `.low_expected`.
- `FisherResult`: `.odds_ratio`, `.p`, `.k_pre`, `.n_pre`, `.k_pos`, `.n_pos`.

---

## Task 1: `corpus.py` — carregador filtrado (fonte única da verdade)

**Files:**
- Create: `scripts/analysis/corpus.py`
- Create: `tests/analysis/__init__.py`
- Test: `tests/analysis/test_corpus.py`

- [ ] **Step 1: Criar `tests/analysis/__init__.py` vazio**

```bash
: > tests/analysis/__init__.py
```

- [ ] **Step 2: Escrever o teste que falha**

```python
# tests/analysis/test_corpus.py
from pathlib import Path

import pandas as pd
import pytest

from scripts.analysis.corpus import load_corpus


def _csv(tmp_path: Path) -> Path:
    rows = [
        # incluir + extraído de verdade  -> entra
        {"elegivel": "incluir", "nota_extracao": "ok", "score_qualidade": "4",
         "magnitude_normalizada": "0.12", "pre_pos_chatgpt": "pos"},
        {"elegivel": "incluir", "nota_extracao": "", "score_qualidade": "3",
         "magnitude_normalizada": "", "pre_pos_chatgpt": "pre"},
        # incluir mas parse_fail -> fora (pendente)
        {"elegivel": "incluir", "nota_extracao": "parse_fail", "score_qualidade": "",
         "magnitude_normalizada": "", "pre_pos_chatgpt": "pos"},
        # excluir -> fora
        {"elegivel": "excluir", "nota_extracao": "ok", "score_qualidade": "2",
         "magnitude_normalizada": "", "pre_pos_chatgpt": "pre"},
    ]
    p = tmp_path / "06_extraction.csv"
    pd.DataFrame(rows).to_csv(p, index=False, encoding="utf-8")
    return p


def test_filtra_incluidos_extraidos(tmp_path):
    c = load_corpus(_csv(tmp_path))
    assert c.n == 2
    assert c.n_pendentes == 1
    assert c.n_excluidos == 1
    assert set(c.df["elegivel"]) == {"incluir"}
    assert "parse_fail" not in set(c.df["nota_extracao"])


def test_coage_numericos(tmp_path):
    c = load_corpus(_csv(tmp_path))
    assert c.df["score_qualidade"].dtype.kind == "f"
    # vazio vira NaN
    assert c.df["magnitude_normalizada"].isna().sum() == 1
    assert pytest.approx(c.df["magnitude_normalizada"].dropna().iloc[0]) == 0.12
```

- [ ] **Step 3: Rodar o teste e ver falhar**

Run: `source .venv/bin/activate && python -m pytest tests/analysis/test_corpus.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.analysis.corpus'`

- [ ] **Step 4: Implementar `corpus.py`**

```python
# scripts/analysis/corpus.py
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
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return CorpusAnalise(
        df=df.reset_index(drop=True),
        n=int(len(df)),
        n_pendentes=int(parse_fail.sum()),
        n_excluidos=int((raw["elegivel"] != INCLUIDO).sum()),
    )
```

- [ ] **Step 5: Rodar o teste e ver passar**

Run: `source .venv/bin/activate && python -m pytest tests/analysis/test_corpus.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add scripts/analysis/corpus.py tests/analysis/__init__.py tests/analysis/test_corpus.py
git commit -m "feat(plano-5): corpus.py — carregador filtrado (756 incluídos-extraídos)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: `stats.py` — proporções e testes de associação (puros)

**Files:**
- Create: `scripts/analysis/stats.py`
- Test: `tests/analysis/test_stats.py`

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/analysis/test_stats.py
import math

import pandas as pd
import pytest

from scripts.analysis.stats import (
    RESSALVA,
    assoc_chi2,
    assoc_fisher_2x2,
    prop_por_periodo,
    wilson95,
)


def _df():
    # pre: 2 baixa, 1 n/a ; pos: 1 baixa, 1 alta
    return pd.DataFrame(
        {
            "pre_pos_chatgpt": ["pre", "pre", "pre", "pos", "pos"],
            "polarizacao": [
                "baixa-quali em risco",
                "baixa-quali em risco",
                "n/a",
                "baixa-quali em risco",
                "alta-quali em risco",
            ],
        }
    )


def test_prop_exclui_na_do_denominador():
    r = prop_por_periodo(_df(), "polarizacao")
    assert r.n_classif["pre"] == 2          # n/a fora
    assert r.n_na["pre"] == 1
    assert r.counts["pre"]["baixa-quali em risco"] == 2
    assert r.pct("pre", "baixa-quali em risco") == pytest.approx(1.0)
    assert r.pct("pos", "alta-quali em risco") == pytest.approx(0.5)


def test_chi2_confere_com_contingencia_conhecida():
    # associação perfeita -> p pequeno
    df = pd.DataFrame(
        {
            "pre_pos_chatgpt": ["pre"] * 20 + ["pos"] * 20,
            "polarizacao": ["baixa-quali em risco"] * 20 + ["alta-quali em risco"] * 20,
        }
    )
    res = assoc_chi2(prop_por_periodo(df, "polarizacao"))
    assert res.p < 0.001
    assert res.dof == 1


def test_fisher_independencia_p_alto():
    df = pd.DataFrame(
        {
            "pre_pos_chatgpt": ["pre"] * 10 + ["pos"] * 10,
            "polarizacao": (["alta-quali em risco", "baixa-quali em risco"] * 5) * 2,
        }
    )
    r = assoc_fisher_2x2(df, "polarizacao", foco="alta-quali em risco")
    assert r.p > 0.5
    assert r.k_pre == 5 and r.n_pre == 10
    assert r.k_pos == 5 and r.n_pos == 10


def test_wilson95_valor_conhecido():
    low, high = wilson95(5, 10)
    assert low == pytest.approx(0.2366, abs=1e-3)
    assert high == pytest.approx(0.7634, abs=1e-3)


def test_ressalva_menciona_nao_amostra():
    assert "amostra" in RESSALVA.lower()
    assert "explorat" in RESSALVA.lower()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `source .venv/bin/activate && python -m pytest tests/analysis/test_stats.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.analysis.stats'`

- [ ] **Step 3: Implementar `stats.py`**

```python
# scripts/analysis/stats.py
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
```

- [ ] **Step 4: Rodar e ver passar**

Run: `source .venv/bin/activate && python -m pytest tests/analysis/test_stats.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/analysis/stats.py tests/analysis/test_stats.py
git commit -m "feat(plano-5): stats.py — proporções (n/a fora) + χ²/Fisher + Wilson

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `texkit.py` — construção de LaTeX

**Files:**
- Create: `scripts/analysis/texkit.py`
- Test: `tests/analysis/test_texkit.py`

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/analysis/test_texkit.py
from scripts.analysis.texkit import (
    CANON,
    escape,
    fmt_ci,
    fmt_p,
    fmt_pct,
    tabela_booktabs,
)


def test_escape_underscore_e_amp():
    assert escape("a_b & c") == r"a\_b \& c"


def test_fmt_pct_virgula_pt_br():
    assert fmt_pct(0.123) == r"12,3\%"


def test_fmt_p_ramos():
    assert fmt_p(0.0004) == r"$p<0{,}001$"
    assert fmt_p(0.042) == r"$p=0{,}042$"


def test_fmt_ci():
    assert fmt_ci(0.236, 0.763) == "[23,6; 76,3]"


def test_tabela_booktabs_estrutura_e_notas():
    tex = tabela_booktabs(
        "ll",
        ["A", "B"],
        [["x", "y"], ["z", "w"]],
        notas=["nota de teste"],
    )
    assert r"\toprule" in tex and r"\midrule" in tex and r"\bottomrule" in tex
    assert r"A & B \\" in tex
    assert r"x & y \\" in tex
    assert "nota de teste" in tex and r"\footnotesize" in tex


def test_canon_tem_dimensoes_chave():
    for dim in ("polarizacao", "sinal_efeito", "janela", "tecnologia_focada"):
        assert dim in CANON and len(CANON[dim]) >= 2
    assert CANON["janela"] == ["2013-2017", "2018-2022", "2022-2026"]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `source .venv/bin/activate && python -m pytest tests/analysis/test_texkit.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.analysis.texkit'`

- [ ] **Step 3: Implementar `texkit.py`**

```python
# scripts/analysis/texkit.py
"""Construção de LaTeX (booktabs) e ordenação canônica — Plano 5.

CANON fixa a ordem de cada enum (de protocols/extraction_schema.md) para tabelas
e figuras byte-estáveis entre rodadas. Sem lógica estatística aqui.
"""
from __future__ import annotations

CANON: dict[str, list[str]] = {
    "polarizacao": ["baixa-quali em risco", "alta-quali em risco", "ambos", "neutro"],
    "sinal_efeito": ["negativo", "positivo", "nulo", "ambíguo"],
    "tipo_estudo": [
        "exposição ocupacional",
        "evidência macro/setorial",
        "firma/freelancer",
        "teórico/modelo",
        "survey/revisão",
    ],
    "horizonte": ["curto prazo", "médio", "longo", "projeção"],
    "tecnologia_focada": [
        "automação",
        "ML/preditiva",
        "deep learning",
        "IA generativa/LLMs",
        "robôs+IA",
        "geral",
    ],
    "janela": ["2013-2017", "2018-2022", "2022-2026"],
    "tipo_pub": ["journal", "working paper", "book chapter"],
    "revisado_por_pares": ["sim", "não"],
}

MECANISMOS = {
    "mec_deslocamento": "Deslocamento",
    "mec_reinstalacao": "Reinstalação",
    "mec_complementaridade": "Complementaridade",
    "mec_demanda_agregada": "Demanda agregada",
}


def escape(s: str) -> str:
    return str(s).replace("&", r"\&").replace("_", r"\_")


def fmt_pct(x: float) -> str:
    return f"{x * 100:.1f}".replace(".", ",") + r"\%"


def fmt_p(p: float) -> str:
    if p < 0.001:
        return r"$p<0{,}001$"
    return ("$p=" + f"{p:.3f}".replace(".", "{,}") + "$")


def fmt_ci(low: float, high: float) -> str:
    return f"[{low * 100:.1f}; {high * 100:.1f}]".replace(".", ",")


def tabela_booktabs(
    colspec: str,
    header: list[str],
    rows: list[list[str]],
    notas: list[str] | None = None,
) -> str:
    lines = [
        r"\begin{tabular}{" + colspec + "}",
        r"\toprule",
        " & ".join(header) + r" \\",
        r"\midrule",
    ]
    for r in rows:
        lines.append(" & ".join(r) + r" \\")
    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    if notas:
        for n in notas:
            lines.append(r"\par\footnotesize{} " + n)
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Rodar e ver passar**

Run: `source .venv/bin/activate && python -m pytest tests/analysis/test_texkit.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/analysis/texkit.py tests/analysis/test_texkit.py
git commit -m "feat(plano-5): texkit.py — booktabs + formatação pt-BR + ordem canônica

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `descritivas_corpus.py` (reescrita) — Cap 04

**Files:**
- Modify (reescrever): `scripts/analysis/descritivas_corpus.py`
- Test: `tests/analysis/test_descritivas.py`

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/analysis/test_descritivas.py
import pandas as pd

from scripts.analysis.descritivas_corpus import run


def _csv(tmp_path):
    rows = []
    # 3 incluídos-extraídos
    for ano, jan, tipo, tec, pub, rev, met, pais in [
        (2015, "2013-2017", "exposição ocupacional", "automação", "journal", "sim", "OLS", "EUA"),
        (2020, "2018-2022", "teórico/modelo", "deep learning", "journal", "sim", "modelo teórico", "EUA"),
        (2024, "2022-2026", "firma/freelancer", "IA generativa/LLMs", "working paper", "não", "DiD", "Brasil"),
    ]:
        rows.append({"elegivel": "incluir", "nota_extracao": "ok", "ano": ano,
                     "janela": jan, "tipo_estudo": tipo, "tecnologia_focada": tec,
                     "tipo_pub": pub, "revisado_por_pares": rev, "metodo_empirico": met,
                     "pais_estudo": pais, "score_qualidade": "3", "magnitude_normalizada": ""})
    # ruído que NÃO pode contaminar as figuras
    rows.append({"elegivel": "excluir", "nota_extracao": "ok", "ano": 1999,
                 "janela": "2013-2017", "tipo_estudo": "survey/revisão", "tecnologia_focada": "geral",
                 "tipo_pub": "journal", "revisado_por_pares": "sim", "metodo_empirico": "descritivo",
                 "pais_estudo": "EUA", "score_qualidade": "1", "magnitude_normalizada": ""})
    rows.append({"elegivel": "incluir", "nota_extracao": "parse_fail", "ano": 2024,
                 "janela": "2022-2026", "tipo_estudo": "", "tecnologia_focada": "",
                 "tipo_pub": "", "revisado_por_pares": "", "metodo_empirico": "",
                 "pais_estudo": "", "score_qualidade": "", "magnitude_normalizada": ""})
    p = tmp_path / "06_extraction.csv"
    pd.DataFrame(rows).to_csv(p, index=False, encoding="utf-8")
    return p


def test_gera_4_figuras_e_tabela(tmp_path):
    figdir = tmp_path / "figs"
    tabdir = tmp_path / "tabs"
    run(_csv(tmp_path), figdir, tabdir / "descritivas_corpus.tex")
    for f in ("corpus_anos.pdf", "corpus_janelas.pdf",
              "corpus_tipo_estudo.pdf", "corpus_tecnologia.pdf"):
        assert (figdir / f).exists() and (figdir / f).stat().st_size > 0
    tex = (tabdir / "descritivas_corpus.tex").read_text(encoding="utf-8")
    assert r"\toprule" in tex
    # N descritivo = 3 incluídos-extraídos (exclui o excluir e o parse_fail)
    assert "3" in tex
    # país de fora do corpus incluído não aparece como ano 1999 etc — sanidade textual:
    assert "1999" not in tex


def test_determinismo_tex(tmp_path):
    csv = _csv(tmp_path)
    out1 = tmp_path / "a.tex"
    out2 = tmp_path / "b.tex"
    run(csv, tmp_path / "f1", out1)
    run(csv, tmp_path / "f2", out2)
    assert out1.read_text(encoding="utf-8") == out2.read_text(encoding="utf-8")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `source .venv/bin/activate && python -m pytest tests/analysis/test_descritivas.py -v`
Expected: FAIL — `TypeError`/assinatura antiga de `run` (a versão atual recebe `output_dir`, não a tabela) ou `ImportError`.

- [ ] **Step 3: Reescrever `descritivas_corpus.py`**

```python
# scripts/analysis/descritivas_corpus.py
"""Cap 04 — descritivas do corpus de análise (Plano 5).

4 figuras (anos, janelas, tipo de estudo, tecnologia) + 1 tabela de atributos
estruturais. Tudo sobre os incluídos-e-extraídos (corpus.load_corpus).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")  # headless — antes de pyplot
import matplotlib.pyplot as plt  # noqa: E402

from scripts.analysis.corpus import load_corpus  # noqa: E402
from scripts.analysis.texkit import CANON, escape, fmt_pct, tabela_booktabs  # noqa: E402


def _fig_anos(df: pd.DataFrame, output: Path) -> None:
    anos = pd.to_numeric(df["ano"], errors="coerce").dropna().astype(int)
    counts = anos.value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(counts.index, counts.values, color="steelblue")
    ax.set_xlabel("Ano de publicação")
    ax.set_ylabel("Número de estudos")
    ax.set_title("Distribuição do corpus por ano")
    fig.tight_layout()
    fig.savefig(output, format="pdf")
    plt.close(fig)


def _fig_categorica(df: pd.DataFrame, col: str, titulo: str, output: Path,
                    horizontal: bool = False) -> None:
    ordem = CANON.get(col, sorted(df[col].dropna().unique().tolist()))
    counts = df[col].value_counts().reindex(ordem).fillna(0)
    fig, ax = plt.subplots(figsize=(7, 4))
    if horizontal:
        ax.barh(counts.index, counts.values, color="seagreen")
        ax.set_xlabel("Número de estudos")
    else:
        ax.bar(counts.index, counts.values, color="#555555")
        ax.set_ylabel("Número de estudos")
        plt.xticks(rotation=20, ha="right")
    ax.set_title(titulo)
    fig.tight_layout()
    fig.savefig(output, format="pdf")
    plt.close(fig)


def _linha_freq(rotulo: str, n: int, total: int) -> list[str]:
    pct = (n / total) if total else 0.0
    return [escape(rotulo), str(n), fmt_pct(pct)]


def _tabela_estrutural(df: pd.DataFrame, total: int) -> str:
    rows: list[list[str]] = []
    for col in ("tipo_pub", "revisado_por_pares", "metodo_empirico"):
        ordem = CANON.get(col)
        cats = ordem if ordem else df[col].value_counts().index.tolist()
        for cat in cats:
            n = int((df[col] == cat).sum())
            if n:
                rows.append(_linha_freq(f"{col}: {cat}", n, total))
    top_pais = df["pais_estudo"].replace("", pd.NA).dropna().value_counts().head(5)
    for pais, n in top_pais.items():
        rows.append(_linha_freq(f"país: {pais}", int(n), total))
    return tabela_booktabs(
        "lrr",
        ["Atributo", "n", r"\%"],
        rows,
        notas=[f"Corpus de análise: N={total} estudos incluídos e extraídos."],
    )


def run(input: Path, output_dir: Path, output_table: Path) -> None:
    corpus = load_corpus(input)
    df = corpus.df
    output_dir.mkdir(parents=True, exist_ok=True)
    output_table.parent.mkdir(parents=True, exist_ok=True)
    _fig_anos(df, output_dir / "corpus_anos.pdf")
    _fig_categorica(df, "janela", "Corpus por janela temporal",
                    output_dir / "corpus_janelas.pdf")
    _fig_categorica(df, "tipo_estudo", "Tipos de estudo no corpus",
                    output_dir / "corpus_tipo_estudo.pdf", horizontal=True)
    _fig_categorica(df, "tecnologia_focada", "Tecnologia de IA focada",
                    output_dir / "corpus_tecnologia.pdf", horizontal=True)
    output_table.write_text(_tabela_estrutural(df, corpus.n), encoding="utf-8")
    print(f"Cap 04: 4 figuras em {output_dir} + tabela {output_table} (N={corpus.n})")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--output-table", type=Path, required=True)
    args = p.parse_args(argv)
    run(args.input, args.output_dir, args.output_table)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
```

- [ ] **Step 4: Rodar e ver passar**

Run: `source .venv/bin/activate && python -m pytest tests/analysis/test_descritivas.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/analysis/descritivas_corpus.py tests/analysis/test_descritivas.py
git commit -m "feat(plano-5): descritivas_corpus — Cap 04 sobre corpus filtrado (4 figs + tabela)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: `sintese_janelas.py` (novo) — Cap 05

**Files:**
- Create: `scripts/analysis/sintese_janelas.py`
- Test: `tests/analysis/test_sintese_janelas.py`

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/analysis/test_sintese_janelas.py
import pandas as pd

from scripts.analysis.sintese_janelas import run


def _csv(tmp_path):
    rows = []
    spec = [
        ("2013-2017", "automação", "exposição ocupacional", "negativo", "baixa-quali em risco", "sim", "não"),
        ("2013-2017", "automação", "exposição ocupacional", "negativo", "baixa-quali em risco", "sim", "não"),
        ("2022-2026", "IA generativa/LLMs", "firma/freelancer", "ambíguo", "alta-quali em risco", "não", "sim"),
    ]
    for jan, tec, tipo, sinal, pol, desl, compl in spec:
        rows.append({"elegivel": "incluir", "nota_extracao": "ok", "janela": jan,
                     "tecnologia_focada": tec, "tipo_estudo": tipo, "sinal_efeito": sinal,
                     "polarizacao": pol, "mec_deslocamento": desl, "mec_reinstalacao": "não",
                     "mec_complementaridade": compl, "mec_demanda_agregada": "não",
                     "score_qualidade": "3", "magnitude_normalizada": ""})
    p = tmp_path / "06_extraction.csv"
    pd.DataFrame(rows).to_csv(p, index=False, encoding="utf-8")
    return p


def test_tabela_tem_3_janelas_e_N(tmp_path):
    out_tab = tmp_path / "sintese_janelas.tex"
    out_fig = tmp_path / "mecanismos_janela.pdf"
    run(_csv(tmp_path), out_tab, out_fig)
    tex = out_tab.read_text(encoding="utf-8")
    assert "2013-2017" in tex and "2018-2022" in tex and "2022-2026" in tex
    assert "n=2" in tex  # janela 1 tem 2 estudos
    assert out_fig.exists() and out_fig.stat().st_size > 0


def test_determinismo(tmp_path):
    csv = _csv(tmp_path)
    a, b = tmp_path / "a.tex", tmp_path / "b.tex"
    run(csv, a, tmp_path / "f1.pdf")
    run(csv, b, tmp_path / "f2.pdf")
    assert a.read_text(encoding="utf-8") == b.read_text(encoding="utf-8")
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `source .venv/bin/activate && python -m pytest tests/analysis/test_sintese_janelas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.analysis.sintese_janelas'`

- [ ] **Step 3: Implementar `sintese_janelas.py`**

```python
# scripts/analysis/sintese_janelas.py
"""Cap 05 — síntese por janela temporal (Plano 5).

Figura: % de estudos invocando cada mecanismo Acemoglu-Restrepo nas 3 janelas.
Tabela: tecnologia dominante, tipo modal, sinal/polarização predominantes e
% de cada mecanismo, por janela.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from scripts.analysis.corpus import load_corpus  # noqa: E402
from scripts.analysis.stats import _classificados  # noqa: E402
from scripts.analysis.texkit import (  # noqa: E402
    CANON,
    MECANISMOS,
    escape,
    fmt_pct,
    tabela_booktabs,
)

JANELAS = CANON["janela"]


def _pct_mec_por_janela(df: pd.DataFrame, mec: str) -> dict[str, float]:
    out = {}
    for jan in JANELAS:
        sub = _classificados(df[df["janela"] == jan][mec])
        n = len(sub)
        out[jan] = (int((sub.str.lower() == "sim").sum()) / n) if n else 0.0
    return out


def _modal(df: pd.DataFrame, jan: str, col: str) -> str:
    classif = _classificados(df[df["janela"] == jan][col])
    if classif.empty:
        return "—"
    return str(classif.value_counts().idxmax())


def _fig_mecanismos(df: pd.DataFrame, output: Path) -> None:
    import numpy as np

    x = np.arange(len(JANELAS))
    largura = 0.2
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for i, (mec, rotulo) in enumerate(MECANISMOS.items()):
        pcts = [_pct_mec_por_janela(df, mec)[j] * 100 for j in JANELAS]
        ax.bar(x + (i - 1.5) * largura, pcts, largura, label=rotulo)
    ax.set_xticks(x)
    ax.set_xticklabels(JANELAS)
    ax.set_ylabel("% dos estudos da janela")
    ax.set_title("Mecanismos teóricos invocados por janela")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(output, format="pdf")
    plt.close(fig)


def _tabela(df: pd.DataFrame) -> str:
    n_por_jan = {j: int((df["janela"] == j).sum()) for j in JANELAS}
    header = ["Dimensão"] + [f"{j} (n={n_por_jan[j]})" for j in JANELAS]
    rows: list[list[str]] = []
    rows.append(["Tecnologia dominante"] + [escape(_modal(df, j, "tecnologia_focada")) for j in JANELAS])
    rows.append(["Tipo de estudo modal"] + [escape(_modal(df, j, "tipo_estudo")) for j in JANELAS])
    rows.append(["Sinal predominante"] + [escape(_modal(df, j, "sinal_efeito")) for j in JANELAS])
    rows.append(["Polarização predominante"] + [escape(_modal(df, j, "polarizacao")) for j in JANELAS])
    for mec, rotulo in MECANISMOS.items():
        pj = _pct_mec_por_janela(df, mec)
        rows.append([f"% {rotulo}"] + [fmt_pct(pj[j]) for j in JANELAS])
    return tabela_booktabs(
        "l" + "c" * len(JANELAS),
        header,
        rows,
        notas=["Proporções de mecanismo sobre os estudos que classificaram a dimensão (n/a fora)."],
    )


def run(input: Path, output_table: Path, output_fig: Path) -> None:
    df = load_corpus(input).df
    output_table.parent.mkdir(parents=True, exist_ok=True)
    output_fig.parent.mkdir(parents=True, exist_ok=True)
    _fig_mecanismos(df, output_fig)
    output_table.write_text(_tabela(df), encoding="utf-8")
    print(f"Cap 05: tabela {output_table} + figura {output_fig}")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output-table", type=Path, required=True)
    p.add_argument("--output-fig", type=Path, required=True)
    args = p.parse_args(argv)
    run(args.input, args.output_table, args.output_fig)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
```

- [ ] **Step 4: Rodar e ver passar**

Run: `source .venv/bin/activate && python -m pytest tests/analysis/test_sintese_janelas.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/analysis/sintese_janelas.py tests/analysis/test_sintese_janelas.py
git commit -m "feat(plano-5): sintese_janelas — Cap 05 (mecanismos×janela + tabela síntese)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: `comparacao_pre_pos.py` (reescrita) — Cap 06

**Files:**
- Modify (reescrever): `scripts/analysis/comparacao_pre_pos.py`
- Test: `tests/analysis/test_comparacao_pre_pos.py`

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/analysis/test_comparacao_pre_pos.py
import pandas as pd

from scripts.analysis.comparacao_pre_pos import run


def _csv(tmp_path):
    rows = []
    # pré: maioria baixa-quali; pós: mais alta-quali (desloca o risco)
    spec = (
        [("pre", "baixa-quali em risco", "negativo", "4")] * 12
        + [("pre", "alta-quali em risco", "ambíguo", "3")] * 2
        + [("pos", "baixa-quali em risco", "negativo", "5")] * 7
        + [("pos", "alta-quali em risco", "ambíguo", "4")] * 9
    )
    for per, pol, sinal, score in spec:
        rows.append({"elegivel": "incluir", "nota_extracao": "ok",
                     "pre_pos_chatgpt": per, "polarizacao": pol, "sinal_efeito": sinal,
                     "tipo_estudo": "exposição ocupacional", "horizonte": "médio",
                     "mec_deslocamento": "sim", "mec_reinstalacao": "não",
                     "mec_complementaridade": "não", "mec_demanda_agregada": "não",
                     "score_qualidade": score, "magnitude_normalizada": ("0.1" if per == "pre" else "")})
    p = tmp_path / "06_extraction.csv"
    pd.DataFrame(rows).to_csv(p, index=False, encoding="utf-8")
    return p


def _run(tmp_path):
    d = tmp_path / "tabs"
    run(_csv(tmp_path), d)
    return d


def test_tabela_central_tem_p_e_ressalva(tmp_path):
    tex = (_run(tmp_path) / "comparacao_pre_pos.tex").read_text(encoding="utf-8")
    assert "$p" in tex                  # algum p-valor
    assert "amostra" in tex.lower()     # ressalva injetada


def test_polarizacao_2x2_com_fisher_e_wilson(tmp_path):
    tex = (_run(tmp_path) / "polarizacao_pre_pos.tex").read_text(encoding="utf-8")
    assert "alta-quali em risco" in tex
    assert "Fisher" in tex
    assert "[" in tex and ";" in tex    # IC Wilson formatado


def test_robustez_usa_score_ge_4(tmp_path):
    tex = (_run(tmp_path) / "robustez_qualidade.tex").read_text(encoding="utf-8")
    # n robusto pré = 12 (score 4); pós = 7+9=16 (scores 5 e 4) -> total 28
    assert "score" in tex.lower() and "4" in tex


def test_magnitude_sem_teste(tmp_path):
    tex = (_run(tmp_path) / "magnitude_cobertura.tex").read_text(encoding="utf-8")
    assert "Cobertura" in tex or "cobertura" in tex
    assert "$p" not in tex              # NÃO há teste de hipótese
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `source .venv/bin/activate && python -m pytest tests/analysis/test_comparacao_pre_pos.py -v`
Expected: FAIL — assinatura antiga de `run` (recebe `output_table`, não um diretório) / `KeyError`.

- [ ] **Step 3: Reescrever `comparacao_pre_pos.py`**

```python
# scripts/analysis/comparacao_pre_pos.py
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
    _classificados,
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
    cab = [
        DIM_LABEL[dim]
        + f" — $\\chi^2={chi.chi2:.2f}$, gl$={chi.dof}$, " + fmt_p(chi.p)
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
        notas=[RESSALVA, "Proporções calculadas sobre os estudos que classificaram cada dimensão (n/a fora do denominador)."],
    )


def _tabela_polarizacao(df: pd.DataFrame) -> str:
    f = assoc_fisher_2x2(df, "polarizacao", foco=FOCO_H1)
    lo_pre, hi_pre = wilson95(f.k_pre, f.n_pre)
    lo_pos, hi_pos = wilson95(f.k_pos, f.n_pos)
    rows = [
        ["Alta-quali em risco",
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
        notas=[f"Fisher exato: razão de chances $={f.odds_ratio:.2f}$, " + fmt_p(f.p)
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
        linha("Q1–Q3", lambda s: (f"[{s.quantile(.25):.3f}; {s.quantile(.75):.3f}]".replace(".", ",")
                                   if len(s) else "—")),
        linha("Faixa (mín–máx)", lambda s: (f"[{s.min():.3f}; {s.max():.3f}]".replace(".", ",")
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
```

- [ ] **Step 4: Rodar e ver passar**

Run: `source .venv/bin/activate && python -m pytest tests/analysis/test_comparacao_pre_pos.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/analysis/comparacao_pre_pos.py tests/analysis/test_comparacao_pre_pos.py
git commit -m "feat(plano-5): comparacao_pre_pos — Cap 06 (central + H1 + robustez + magnitude)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Makefile, fiação dos capítulos e verificação de integração

**Files:**
- Modify: `Makefile` (target `analysis` + 3 isolados)
- Modify: `text/chapters/04_resultados_descritivas.tex`, `05_resultados_janelas.tex`, `06_comparacao_pre_pos.tex`

- [ ] **Step 1: Atualizar o target `analysis` no Makefile**

Localize o bloco `analysis:` atual (chama `descritivas_corpus` com `--output-dir` e `comparacao_pre_pos` com `--output-table`) e substitua por:

```makefile
analysis: analysis-descritivas analysis-janelas analysis-prepos

analysis-descritivas:
	$(PYTHON) -m scripts.analysis.descritivas_corpus \
	    --input $(DATA_PROC)/06_extraction.csv \
	    --output-dir $(FIG_DIR) \
	    --output-table $(TAB_DIR)/descritivas_corpus.tex

analysis-janelas:
	$(PYTHON) -m scripts.analysis.sintese_janelas \
	    --input $(DATA_PROC)/06_extraction.csv \
	    --output-table $(TAB_DIR)/sintese_janelas.tex \
	    --output-fig $(FIG_DIR)/mecanismos_janela.pdf

analysis-prepos:
	$(PYTHON) -m scripts.analysis.comparacao_pre_pos \
	    --input $(DATA_PROC)/06_extraction.csv \
	    --output-dir $(TAB_DIR)
```

> Variáveis confirmadas no topo do Makefile: `PYTHON := uv run python`, `DATA_PROC := data/processed`, `FIG_DIR := text/figures`, `TAB_DIR := text/tables`. Use-as como acima.

- [ ] **Step 2: Verificar a sintaxe e a lista de `.PHONY`**

Run: `grep -nE "^\.PHONY|^analysis" Makefile`
Adicione `analysis-descritivas analysis-janelas analysis-prepos` à linha `.PHONY` se ela enumerar targets.

- [ ] **Step 3: Fiar o Cap 04 (adicionar figura tecnologia + tabela estrutural)**

Edite `text/chapters/04_resultados_descritivas.tex`, acrescentando ao final (após a subseção de tipos de estudo):

```latex
\subsection{Tecnologia de IA focada}

\begin{figure}[h]
\centering
\includegraphics[width=0.85\linewidth]{figures/corpus_tecnologia.pdf}
\caption{Distribuição do corpus por tecnologia de IA focada.}
\label{fig:corpus_tecnologia}
\end{figure}

\subsection{Atributos estruturais}

\begin{table}[h]
\centering
\caption{Atributos estruturais do corpus de análise.}
\label{tab:descritivas_estrutural}
\input{tables/descritivas_corpus.tex}
\end{table}
```

- [ ] **Step 4: Fiar o Cap 05 (figura mecanismos + tabela síntese)**

Edite `text/chapters/05_resultados_janelas.tex`, inserindo após a linha `\section{...}` e antes das subseções de janela:

```latex
\begin{figure}[h]
\centering
\includegraphics[width=0.9\linewidth]{figures/mecanismos_janela.pdf}
\caption{Mecanismos teóricos invocados por janela temporal.}
\label{fig:mecanismos_janela}
\end{figure}

\begin{table}[h]
\centering
\caption{Síntese das dimensões por janela temporal.}
\label{tab:sintese_janelas}
\input{tables/sintese_janelas.tex}
\end{table}
```

- [ ] **Step 5: Fiar o Cap 06 (3 tabelas novas além da central)**

Edite `text/chapters/06_comparacao_pre_pos.tex`. A tabela central (`comparacao_pre_pos.tex`) já está incluída. Acrescente, na subseção "Eixo 1: Quem está em risco", a tabela de polarização; e nas posições adequadas, as de robustez e magnitude:

```latex
\subsection{Eixo 1: Quem está em risco}

\begin{table}[h]
\centering
\caption{Foco da hipótese: risco para alta qualificação, pré vs.\ pós-ChatGPT.}
\label{tab:polarizacao_prepos}
\input{tables/polarizacao_pre_pos.tex}
\end{table}

\begin{table}[h]
\centering
\caption{Robustez: polarização restrita a estudos de alta qualidade (score $\geq$ 4).}
\label{tab:robustez_qualidade}
\input{tables/robustez_qualidade.tex}
\end{table}
```

E na subseção "Eixo 3: Como se mede":

```latex
\subsection{Eixo 3: Como se mede}

\begin{table}[h]
\centering
\caption{Cobertura e descritivo da magnitude normalizada, pré vs.\ pós-ChatGPT.}
\label{tab:magnitude_cobertura}
\input{tables/magnitude_cobertura.tex}
\end{table}
```

- [ ] **Step 6: Rodar a análise de integração na base real**

Run:
```bash
source .venv/bin/activate && \
python -m scripts.analysis.descritivas_corpus --input data/processed/06_extraction.csv --output-dir text/figures --output-table text/tables/descritivas_corpus.tex && \
python -m scripts.analysis.sintese_janelas --input data/processed/06_extraction.csv --output-table text/tables/sintese_janelas.tex --output-fig text/figures/mecanismos_janela.pdf && \
python -m scripts.analysis.comparacao_pre_pos --input data/processed/06_extraction.csv --output-dir text/tables
```
Expected: três linhas de log; `Cap 04 ... (N=756)`, `Cap 06 ... (pré=329, pós=427)`. Confirme que existem as 5 figuras e 6 tabelas:
```bash
ls text/figures/corpus_*.pdf text/figures/mecanismos_janela.pdf text/tables/{descritivas_corpus,sintese_janelas,comparacao_pre_pos,polarizacao_pre_pos,robustez_qualidade,magnitude_cobertura}.tex
```

- [ ] **Step 7: Verificar determinismo na base real (byte-idêntico)**

Run:
```bash
source .venv/bin/activate && \
for t in comparacao_pre_pos polarizacao_pre_pos robustez_qualidade magnitude_cobertura sintese_janelas descritivas_corpus; do cp text/tables/$t.tex /tmp/$t.1; done && \
python -m scripts.analysis.comparacao_pre_pos --input data/processed/06_extraction.csv --output-dir text/tables && \
python -m scripts.analysis.sintese_janelas --input data/processed/06_extraction.csv --output-table text/tables/sintese_janelas.tex --output-fig text/figures/mecanismos_janela.pdf && \
python -m scripts.analysis.descritivas_corpus --input data/processed/06_extraction.csv --output-dir text/figures --output-table text/tables/descritivas_corpus.tex && \
for t in comparacao_pre_pos polarizacao_pre_pos robustez_qualidade magnitude_cobertura sintese_janelas descritivas_corpus; do diff -q /tmp/$t.1 text/tables/$t.tex && echo "OK $t"; done
```
Expected: `OK` para os 6 (tabelas byte-idênticas entre rodadas).

- [ ] **Step 8: Rodar a suíte completa**

Run: `source .venv/bin/activate && python -m pytest -q`
Expected: todos verdes (225 anteriores + ~21 novos de `tests/analysis/`).

- [ ] **Step 9: Commit**

```bash
git add Makefile text/chapters/04_resultados_descritivas.tex text/chapters/05_resultados_janelas.tex text/chapters/06_comparacao_pre_pos.tex text/tables/*.tex text/figures/*.pdf
git commit -m "feat(plano-5): Makefile (analysis) + fiação dos caps 04/05/06 + artefatos

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

> **Nota sobre versionar artefatos:** figuras `.pdf` e tabelas `.tex` em `text/` são fontes do documento (não `data/processed/**`), então não caem no `.gitignore` de dados. Se algum `.pdf` for ignorado, NÃO use `git add -f` sem confirmar com o usuário.

---

## Self-Review

**Cobertura da spec:**
- §2.1 escopo 3 capítulos → Tasks 4 (04), 5 (05), 6 (06). ✓
- §2.2 χ²/Fisher com ressalva → `stats.assoc_chi2`/`assoc_fisher_2x2` + `RESSALVA` (Task 2), aplicados na Task 6. ✓
- §2.3 sensibilidade score≥4 → `_tabela_robustez` (Task 6). ✓
- §2.4 magnitude cobertura+descritivo sem pooling → `_tabela_magnitude` + teste `test_magnitude_sem_teste` (Task 6). ✓
- §2.5 arquitetura em camadas → Tasks 1–3 (núcleo) + 4–6 (capítulos). ✓
- §4 denominador-sem-n/a → `_classificados`/`prop_por_periodo` (Task 2), testado. ✓
- §4 mec_* binários como linhas com Fisher → `_tabela_central` (Task 6). ✓
- §4 determinismo (ordem canônica) → `CANON` (Task 3) + testes de determinismo (Tasks 4, 5) + verificação real (Task 7 step 7). ✓
- §3 Makefile + fiação dos caps → Task 7. ✓
- §7 critérios (N=756, byte-idêntico, ausência de teste na magnitude) → Task 7 steps 6–8 + testes. ✓

**Placeholder scan:** nenhum TBD/TODO; todo passo de código traz o código. ✓

**Consistência de tipos:** `CorpusAnalise(.df/.n/.n_pendentes/.n_excluidos)`, `PropResult(.counts/.n_classif/.n_na/.pct)`, `ChiResult(.chi2/.dof/.p/.low_expected)`, `FisherResult(.odds_ratio/.p/.k_pre/.n_pre/.k_pos/.n_pos)` usados de forma idêntica nas Tasks 2 e 6. `run()` de cada módulo tem assinatura própria e consistente com o Makefile (Task 7) e os testes. `_classificados` é importado de `stats` por `sintese_janelas` e `comparacao_pre_pos` (mesma função). ✓
