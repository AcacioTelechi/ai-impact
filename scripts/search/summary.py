"""Pipeline component: build summary table of all search executions.

Reads every `*.meta.json` in `data/raw/searches/` and produces a LaTeX table
for the methodology chapter (`text/tables/searches_summary.tex`).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


def run(searches_dir: Path, output_table: Path) -> None:
    meta_files = sorted(searches_dir.glob("*.meta.json"))
    records: list[dict] = []
    for mf in meta_files:
        data = json.loads(mf.read_text(encoding="utf-8"))
        records.append({
            "Base": data.get("base", ""),
            "Data": data.get("executed_at_utc", "")[:10],
            "Idioma": data.get("lang") or "—",
            "n_brutos": int(data.get("n_hits_raw", 0)),
            "n_filtrados": int(data.get("n_after_filters", 0)),
        })
    df = pd.DataFrame(records)
    if df.empty:
        output_table.parent.mkdir(parents=True, exist_ok=True)
        output_table.write_text(
            r"\begin{tabular}{l}\toprule Nenhuma execução registrada \\ \bottomrule \end{tabular}",
            encoding="utf-8",
        )
        return

    total_raw = int(df["n_brutos"].sum())
    total_filt = int(df["n_filtrados"].sum())

    lines = [
        r"\begin{tabular}{lllrr}",
        r"\toprule",
        r"Base & Data & Idioma & n\_brutos & n\_filtrados \\",
        r"\midrule",
    ]
    for _, row in df.iterrows():
        lines.append(
            f"{row['Base']} & {row['Data']} & {row['Idioma']} & "
            f"{int(row['n_brutos'])} & {int(row['n_filtrados'])} \\\\"
        )
    lines.append(r"\midrule")
    lines.append(
        rf"\textbf{{Total}} & & & \textbf{{{total_raw}}} & \textbf{{{total_filt}}} \\"
    )
    lines.extend([r"\bottomrule", r"\end{tabular}"])

    output_table.parent.mkdir(parents=True, exist_ok=True)
    output_table.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Summary table written to {output_table} ({len(records)} executions)")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--searches-dir", type=Path, required=True)
    p.add_argument("--output-table", type=Path, required=True)
    a = p.parse_args(argv)
    run(searches_dir=a.searches_dir, output_table=a.output_table)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
