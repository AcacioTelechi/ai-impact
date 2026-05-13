"""Pipeline step 05: generate PRISMA 2020 flow diagram as a TikZ .tex file.

Reads counts from earlier pipeline outputs and writes a self-contained TikZ
picture into `text/figures/prisma_flow.tex`, included via \\input{} in the
methodology chapter.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

TEMPLATE = r"""\begin{tikzpicture}[
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

\draw[arr] (id)  -- (dup);
\draw[arr] (dup) -- (scr);
\draw[arr] (scr) -- (elig);
\draw[arr] (scr) -- (exta);
\draw[arr] (elig)-- (inc);
\draw[arr] (elig)-- (exft);
\end{tikzpicture}
"""


def write_tex(counts: dict, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(TEMPLATE % counts, encoding="utf-8")


def compute_counts(
    bruto: Path, dedup_log: Path, screening: Path, eligibility: Path,
) -> dict:
    # identified = lines in bruto minus header
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

    return dict(
        identified=int(identified), duplicates=int(duplicates),
        screened=int(screened), excluded_ta=int(excluded_ta),
        eligibility=int(eligibility_n), excluded_ft=int(excluded_ft),
        included=int(included),
    )


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--bruto", type=Path, required=True)
    p.add_argument("--dedup-log", type=Path, required=True)
    p.add_argument("--screening", type=Path, required=True)
    p.add_argument("--eligibility", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    counts = compute_counts(args.bruto, args.dedup_log, args.screening, args.eligibility)
    write_tex(counts, args.output)
    print(f"PRISMA flow written to {args.output} (included N={counts['included']})")
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
