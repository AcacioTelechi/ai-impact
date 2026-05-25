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
        "indivíduo",
    ],
    "horizonte": ["curto prazo", "médio prazo", "longo prazo", "projeção"],
    "metodo_empirico": [
        "OLS", "IV", "DiD", "RDD", "evento-estudo", "estrutural",
        "ML", "experimento/survey experimental", "modelo teórico", "descritivo",
    ],
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
            lines.append(r"\par{\footnotesize " + n + "}")
    return "\n".join(lines) + "\n"
