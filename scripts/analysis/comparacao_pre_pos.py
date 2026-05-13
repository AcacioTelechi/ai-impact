"""Analysis: build pre/post-ChatGPT comparative table (LaTeX) from extraction CSV."""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

DIMENSIONS = ["sinal_efeito", "polarizacao", "tecnologia_focada", "tipo_estudo"]
DIM_LABELS = {
    "sinal_efeito": "Sinal sobre emprego",
    "polarizacao": "Ocupações em risco",
    "tecnologia_focada": "Tecnologia de IA focada",
    "tipo_estudo": "Tipo de evidência",
}


def compute(df: pd.DataFrame) -> dict:
    out: dict = {"n_pre": int((df["pre_pos_chatgpt"] == "pre").sum()),
                 "n_pos": int((df["pre_pos_chatgpt"] == "pos").sum())}
    for period in ("pre", "pos"):
        sub = df[df["pre_pos_chatgpt"] == period]
        out[period] = {d: Counter(sub[d].dropna().tolist()) for d in DIMENSIONS}
    return out


def to_latex_table(result: dict) -> str:
    lines = [
        r"\begin{tabular}{lll}",
        r"\toprule",
        rf"Dimensão & Pré-ChatGPT (n={result['n_pre']}) & Pós-ChatGPT (n={result['n_pos']}) \\",
        r"\midrule",
    ]
    for d in DIMENSIONS:
        pre_top = ", ".join(f"{k} ({v})" for k, v in result["pre"][d].most_common(3))
        pos_top = ", ".join(f"{k} ({v})" for k, v in result["pos"][d].most_common(3))
        lines.append(f"{DIM_LABELS[d]} & {pre_top} & {pos_top} \\\\")
    lines.extend([r"\bottomrule", r"\end{tabular}"])
    return "\n".join(lines) + "\n"


def run(input: Path, output_table: Path) -> None:
    df = pd.read_csv(input, encoding="utf-8")
    result = compute(df)
    output_table.parent.mkdir(parents=True, exist_ok=True)
    output_table.write_text(to_latex_table(result), encoding="utf-8")
    print(f"Wrote comparative table to {output_table}")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output-table", type=Path, required=True)
    args = p.parse_args(argv)
    run(args.input, args.output_table)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
