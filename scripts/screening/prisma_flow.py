"""Pipeline step 05: generate PRISMA 2020 flow diagram as a TikZ .tex file.

Reads counts from earlier pipeline outputs and writes a self-contained TikZ
picture into `text/figures/prisma_flow.tex`, included via \\input{} in the
methodology chapter.

Plano 4b-ii: parâmetro opcional `--extraction` adiciona caixa de anotação
"Reextração pendente: N (cobertura full-text efetiva X,X%)" quando houver
linhas com nota_extracao=parse_fail. Some sozinha pós-re-rodada.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

_BODY = r"""\begin{tikzpicture}[
    node distance=1.2cm,
    every node/.style={draw, rectangle, rounded corners, align=center, minimum width=5cm, minimum height=0.9cm, font=\small},
    arr/.style={-{Stealth[length=2mm]}, thick}
]
\node (id)   {Registros identificados nas bases\\(\textbf{N = %(identified)d})};
\node (dup) [below=of id] {Duplicatas removidas\\(N = %(duplicates)d)};
\node (scr) [below=of dup] {Registros para triagem TA\\(N = %(screened)d)};
\node (exta)[right=2cm of scr] {Excluídos na triagem TA\\(N = %(excluded_ta)d)};
\node (elig)[below=of scr] {Candidatos a texto completo\\(N = %(eligibility)d)};
\node (exft)[right=2cm of elig] {Excluídos na elegibilidade\\(N = %(excluded_ft)d)};
\node (inc) [below=of elig, fill=blue!10] {Estudos incluídos na síntese\\(\textbf{N = %(included)d})};
%(extra_node)s
\draw[arr] (id)  -- (dup);
\draw[arr] (dup) -- (scr);
\draw[arr] (scr) -- (elig);
\draw[arr] (scr) -- (exta);
\draw[arr] (elig)-- (inc);
\draw[arr] (elig)-- (exft);
\end{tikzpicture}
"""

_NOTA_INTERINA = (
    r"\node (nota) [below=of inc, draw=red!60, fill=red!5, font=\footnotesize, "
    r"align=center] {Reextração pendente: %(pendentes_reextract)d "
    r"(cobertura full-text efetiva %(cobertura_pct).1f\%%)};"
    "\n"
)


def write_tex(counts: dict, output: Path) -> None:
    extra = (_NOTA_INTERINA % counts) if counts.get("pendentes_reextract", 0) > 0 else ""
    output.parent.mkdir(parents=True, exist_ok=True)
    body = _BODY % {**counts, "extra_node": extra}
    output.write_text(body, encoding="utf-8")


def compute_counts(
    bruto: Path, dedup_log: Path, screening: Path, eligibility: Path,
    extraction: Path | None = None,
) -> dict:
    with open(bruto) as f:
        identified = sum(1 for _ in f) - 1
    dup_df = pd.read_csv(dedup_log)
    duplicates = len(dup_df)
    screened = identified - duplicates

    scr_df = pd.read_csv(screening)
    excluded_ta = (scr_df["decisao_llm"] == "excluir").sum()
    eligibility_n = len(scr_df) - excluded_ta

    elig_df = pd.read_csv(eligibility)
    included = (elig_df["decisao_final"] == "incluido").sum()
    excluded_ft = (elig_df["decisao_final"] == "excluido").sum()

    counts = dict(
        identified=int(identified), duplicates=int(duplicates),
        screened=int(screened), excluded_ta=int(excluded_ta),
        eligibility=int(eligibility_n), excluded_ft=int(excluded_ft),
        included=int(included),
        pendentes_reextract=0, cobertura_pct=0.0,
    )

    if extraction is not None:
        ext_df = pd.read_csv(extraction, encoding="utf-8", keep_default_na=False)
        n_total = len(ext_df)
        n_pf = int((ext_df["nota_extracao"] == "parse_fail").sum())
        n_pdf = int((ext_df["text_source"] == "pdf").sum())
        counts["pendentes_reextract"] = n_pf
        counts["cobertura_pct"] = (n_pdf / n_total * 100.0) if n_total else 0.0

    return counts


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--bruto", type=Path, required=True)
    p.add_argument("--dedup-log", type=Path, required=True)
    p.add_argument("--screening", type=Path, required=True)
    p.add_argument("--eligibility", type=Path, required=True)
    p.add_argument("--extraction", type=Path, default=None)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    counts = compute_counts(args.bruto, args.dedup_log, args.screening,
                            args.eligibility, extraction=args.extraction)
    write_tex(counts, args.output)
    print(f"PRISMA flow written to {args.output} (included N={counts['included']}, "
          f"pendentes_reextract={counts['pendentes_reextract']})")
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
