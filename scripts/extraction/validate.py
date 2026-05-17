"""Pipeline step 07: validate extracted rows for internal consistency."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

WINDOWS = {
    "2013-2017": (2013, 2017),
    "2018-2022": (2018, 2022),
    "2022-2026": (2022, 2026),
}


def _check_year_window(row: dict) -> str | None:
    win = WINDOWS.get(row.get("janela", ""))
    if not win:
        return None
    try:
        ano = int(row.get("ano"))
    except (TypeError, ValueError):
        return None
    lo, hi = win
    if not (lo <= ano <= hi):
        return f"ano={ano} fora da janela {row['janela']}"
    return None


def _check_pre_pos(row: dict) -> str | None:
    try:
        ano = int(row.get("ano"))
    except (TypeError, ValueError):
        return None
    expected = "pos" if ano >= 2023 else "pre"
    if row.get("pre_pos_chatgpt") and row["pre_pos_chatgpt"] != expected:
        return f"ano={ano} sugere {expected}, mas pre_pos_chatgpt={row['pre_pos_chatgpt']}"
    return None


def run(path: Path) -> list[dict]:
    df = pd.read_csv(path, encoding="utf-8")
    issues = []
    for _, row in df.iterrows():
        d = row.to_dict()
        if msg := _check_year_window(d):
            issues.append(dict(id=d.get("id"), rule="year_window_mismatch", message=msg))
        if msg := _check_pre_pos(d):
            issues.append(dict(id=d.get("id"), rule="pre_pos_chatgpt_inconsistent", message=msg))
    return issues


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("path", type=Path)
    args = p.parse_args(argv)
    issues = run(args.path)
    if not issues:
        print("OK — no issues found.")
        return 0
    for it in issues:
        print(f"[{it['rule']}] {it['id']}: {it['message']}")
    return 1


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
