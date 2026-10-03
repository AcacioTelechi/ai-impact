"""Pipeline component: build summary table of all search executions.

Reads every `*.meta.json` in `data/raw/searches/` (and the CSV exported next to
each one) and produces a LaTeX table for the methodology chapter
(`text/tables/searches_summary.tex`), with one COLUMN per database.

Kept to the essentials: records retrieved per database (after intra-database
deduplication) and, when the optional inputs are given, the overlap
between databases (`--dedup-decisions`) and the contribution of each database
to the final synthesis corpus (`--extraction`).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

ROTULO_BASE = {"scopus": "Scopus", "wos": "Web of Science", "scielo": "SciELO"}


def _milhar(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _pct(k: int, n: int) -> str:
    return (f"{k / n * 100:.1f}".replace(".", ",") + r"\%") if n else "---"


def _chave(doi: str, titulo: str) -> str:
    """Identidade de um registro entre bases: DOI normalizado ou, na falta, título."""
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", str(doi).strip().lower())
    if doi:
        return "doi:" + doi
    t = unicodedata.normalize("NFKD", str(titulo).lower())
    return "tit:" + re.sub(r"[^a-z0-9]+", "", t.encode("ascii", "ignore").decode())


def _ler_base(meta_file: Path) -> tuple[dict, pd.DataFrame]:
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    csv = meta_file.with_name(meta_file.name.replace(".meta.json", ".csv"))
    df = pd.read_csv(csv, dtype=str).fillna("") if csv.exists() else pd.DataFrame()
    return meta, df


def run(searches_dir: Path, output_table: Path, dedup_decisions: Path | None = None,
        extraction: Path | None = None) -> None:
    bases = [_ler_base(mf) for mf in sorted(searches_dir.glob("*.meta.json"))]
    output_table.parent.mkdir(parents=True, exist_ok=True)
    if not bases:
        output_table.write_text(
            r"\begin{tabular}{l}\toprule Nenhuma execução registrada \\ \bottomrule \end{tabular}",
            encoding="utf-8",
        )
        return

    nomes = [ROTULO_BASE.get(m.get("base", ""), m.get("base", "")) for m, _ in bases]
    n_int = [int(m.get("n_after_filters", 0)) for m, _ in bases]
    rows: list[list[str]] = [
        ["Registros recuperados"] + [_milhar(n) for n in n_int] + [_milhar(sum(n_int))],
    ]

    tem_csv = all(not df.empty for _, df in bases)
    if dedup_decisions and dedup_decisions.exists() and len(bases) > 1:
        n_dup = len(pd.read_csv(dedup_decisions, dtype=str))
        rows.append(["Presentes em mais de uma base"] + [_milhar(n_dup)] * len(bases)
                    + [_milhar(n_dup)])
        rows.append(["Registros únicos após deduplicação"] + [""] * len(bases)
                    + [_milhar(sum(n_int) - n_dup)])

    if extraction and extraction.exists() and tem_csv:
        e = pd.read_csv(extraction, dtype=str).fillna("")
        e = e[(e["elegivel"] == "incluir") & (e["nota_extracao"] != "parse_fail")]
        finais = {_chave(d, t) for d, t in zip(e["doi"], e["titulo"])}
        chaves = [{_chave(d, t) for d, t in zip(df["doi"], df["title"])} for _, df in bases]
        em = [finais & c for c in chaves]
        rows.append(["Incluídos na síntese"] + [_milhar(len(x)) for x in em]
                    + [_milhar(len(set().union(*em)))])
        excl = [x - set().union(*(y for j, y in enumerate(em) if j != i))
                for i, x in enumerate(em)]
        rows.append([r"\quad dos quais exclusivos da base"] + [_milhar(len(x)) for x in excl]
                    + [_milhar(sum(len(x) for x in excl))])
        rows.append(["Taxa de inclusão"]
                    + [_pct(len(x), n) for x, n in zip(em, n_int)]
                    + [_pct(len(set().union(*em)), sum(n_int) - (n_dup if dedup_decisions else 0))])

    lines = [r"\begin{tabular}{l" + "r" * (len(bases) + 1) + "}", r"\toprule",
             " & ".join([""] + nomes + ["Total"]) + r" \\", r"\midrule"]
    lines += [" & ".join(r) + r" \\" for r in rows]
    lines += [r"\bottomrule", r"\end{tabular}"]
    output_table.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Summary table written to {output_table} ({len(bases)} executions)")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--searches-dir", type=Path, required=True)
    p.add_argument("--output-table", type=Path, required=True)
    p.add_argument("--dedup-decisions", type=Path, default=None)
    p.add_argument("--extraction", type=Path, default=None)
    a = p.parse_args(argv)
    run(searches_dir=a.searches_dir, output_table=a.output_table,
        dedup_decisions=a.dedup_decisions, extraction=a.extraction)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
