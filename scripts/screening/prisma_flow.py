"""Pipeline step 05: generate PRISMA 2020 flow diagram as a TikZ .tex file.

Reads counts from earlier pipeline outputs and writes a self-contained TikZ
picture into `text/figures/prisma_flow.tex`, included via \\input{} in the
methodology chapter.

Estágios PRISMA mapeados para os artefatos atuais (pós Planos 3/4b-i/4b-ii):
identificação ← `01_corpus_bruto.csv`; deduplicação ← `02_dedup_decisions.csv`;
triagem ← `03_screening_ta.csv` (schema dual-LLM, `decisao_final`); candidatos
a texto completo ← `03_incluidos_final.csv` (já pós-arbitragem); elegibilidade
e extração ← `06_extraction.csv` (`elegivel`, `nota_extracao`); cobertura
full-text ← `04_fulltext_manifest.csv` (corrigido).

Plano 4b-ii: o parâmetro opcional `--extraction` adiciona caixa de anotação
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
    r"(cobertura full-text efetiva %(cobertura_str)s\%%)};"
    "\n"
)


def write_tex(counts: dict, output: Path) -> None:
    # vírgula decimal pt-BR na anotação de cobertura
    nota_counts = {**counts, "cobertura_str": f"{counts.get('cobertura_pct', 0.0):.1f}".replace(".", ",")}
    extra = (_NOTA_INTERINA % nota_counts) if counts.get("pendentes_reextract", 0) > 0 else ""
    output.parent.mkdir(parents=True, exist_ok=True)
    body = _BODY % {**counts, "extra_node": extra}
    output.write_text(body, encoding="utf-8")


def compute_counts(
    bruto: Path, dedup_log: Path, screening: Path, incluidos_final: Path,
    extraction: Path | None = None, manifest: Path | None = None,
) -> dict:
    """Map the current pipeline artifacts to PRISMA 2020 stage counts.

    Schema (pós Planos 3/4b-i/4b-ii):
    - identificados   = linhas de `bruto` (contadas via pandas — robusto a
      campos multilinha de resumo, que inflariam uma contagem de linhas físicas).
    - duplicatas      = linhas do log de deduplicação.
    - triados         = identificados − duplicatas (= linhas de `screening`).
    - candidatos a texto completo (`eligibility`) = linhas de `incluidos_final`,
      que já reflete a triagem dual-LLM (`decisao_final`) **e** a arbitragem.
    - excluídos na triagem (`excluded_ta`) = triados − candidatos (engloba a
      exclusão por união conservadora e a arbitragem).
    - elegibilidade/extração (`extraction`, opcional): `elegivel` ∈
      {incluir, excluir}; `excluded_ft` = excluir; incluídos na síntese =
      elegíveis − `parse_fail`. `pendentes_reextract` = nº de `parse_fail`.
    - cobertura full-text: nº de `text_source == "pdf"` sobre o total; preferir
      o `manifest` (corrigido: PDFs inválidos/protegidos rebaixados a abstract)
      ao `extraction` quando ambos disponíveis.
    """
    identified = len(pd.read_csv(bruto, encoding="utf-8"))
    duplicates = len(pd.read_csv(dedup_log, encoding="utf-8"))
    screened = len(pd.read_csv(screening, encoding="utf-8"))
    eligibility_n = len(pd.read_csv(incluidos_final, encoding="utf-8"))
    excluded_ta = screened - eligibility_n

    counts = dict(
        identified=int(identified), duplicates=int(duplicates),
        screened=int(screened), excluded_ta=int(excluded_ta),
        eligibility=int(eligibility_n), excluded_ft=0, included=0,
        pendentes_reextract=0, cobertura_pct=0.0,
    )

    if extraction is not None:
        ext_df = pd.read_csv(extraction, encoding="utf-8", keep_default_na=False)
        n_elegivel = int((ext_df["elegivel"] == "incluir").sum())
        n_pf = int((ext_df["nota_extracao"] == "parse_fail").sum())
        counts["excluded_ft"] = int((ext_df["elegivel"] == "excluir").sum())
        counts["included"] = n_elegivel - n_pf
        counts["pendentes_reextract"] = n_pf

        cov_df = (
            pd.read_csv(manifest, encoding="utf-8", keep_default_na=False)
            if manifest is not None else ext_df
        )
        n_total = len(cov_df)
        n_pdf = int((cov_df["text_source"] == "pdf").sum())
        counts["cobertura_pct"] = (n_pdf / n_total * 100.0) if n_total else 0.0

    return counts


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--bruto", type=Path, required=True)
    p.add_argument("--dedup-log", type=Path, required=True)
    p.add_argument("--screening", type=Path, required=True)
    p.add_argument("--incluidos-final", type=Path, required=True)
    p.add_argument("--extraction", type=Path, default=None)
    p.add_argument("--manifest", type=Path, default=None)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    counts = compute_counts(args.bruto, args.dedup_log, args.screening,
                            args.incluidos_final, extraction=args.extraction,
                            manifest=args.manifest)
    write_tex(counts, args.output)
    print(f"PRISMA flow written to {args.output} (included N={counts['included']}, "
          f"pendentes_reextract={counts['pendentes_reextract']})")
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
