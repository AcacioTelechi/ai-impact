"""Calcula κ humano×LLM (elegibilidade cega) e acurácia por campo (auditoria).

Aborta com lista de pendências se as planilhas estiverem incompletas — nunca
calcula métricas silenciosamente com buracos.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import cohen_kappa_score, confusion_matrix

from scripts.screening.llm.batch_client import cache_key, custom_id
from scripts.screening.revisao_ingest import normalize_decisao

CAMPOS_CRITICOS = (
    "pre_pos_chatgpt", "janela", "sinal_efeito",
    "tipo_estudo", "polarizacao", "score_qualidade",
)
_LABELS = ["incluir", "excluir"]
_VALID_AUD = {"ok", "erro"}


def _wilson_95(k: int, n: int) -> tuple[float, float]:
    """IC Wilson 95% para proporção binomial. Devolve (lo, hi). n=0 → (nan,nan)."""
    if n == 0:
        return (float("nan"), float("nan"))
    z = 1.96
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _llm_decision_by_rid(extraction: pd.DataFrame) -> dict[str, str]:
    """review_id → 'incluir' / 'excluir' derivado de elegivel + motivo_exclusao."""
    ext = extraction.rename(columns={"titulo": "title", "ano": "year"}).copy()
    out: dict[str, str] = {}
    for _, r in ext.iterrows():
        rid = custom_id(cache_key(r))
        elig = str(r.get("elegivel", "")).strip()
        motivo = str(r.get("motivo_exclusao", "")).strip()
        out[rid] = "incluir" if (elig == "incluir" and motivo == "") else "excluir"
    return out


def _validate_eleg(eleg: pd.DataFrame) -> None:
    pend = eleg.loc[
        eleg["decisao_humana"].astype(str).str.strip() == "",
        "review_id",
    ].tolist()
    if pend:
        raise ValueError(
            f"{len(pend)} linha(s) sem decisao_humana — preencher antes de calcular κ. "
            f"review_ids: {pend[:5]}{' …' if len(pend) > 5 else ''}"
        )


def _validate_aud(aud: pd.DataFrame) -> None:
    pend: list[tuple[str, str]] = []
    for _, r in aud.iterrows():
        for c in CAMPOS_CRITICOS:
            val = str(r.get(f"{c}_auditoria", "")).strip().lower()
            if val not in _VALID_AUD:
                pend.append((str(r["review_id"]), c))
    if pend:
        msg = ", ".join(f"{rid}/{c}" for rid, c in pend[:5])
        raise ValueError(
            f"{len(pend)} auditoria(s) pendente(s)/inválida(s) — esperado ok/erro. "
            f"Ex.: {msg}{' …' if len(pend) > 5 else ''}"
        )


def _kappa_tex(humano: list[str], llm: list[str], out: Path) -> None:
    n = len(humano)
    out.parent.mkdir(parents=True, exist_ok=True)
    if n == 0:
        out.write_text(
            "\\begin{tabular}{l}\\toprule Amostra vazia \\\\ \\bottomrule \\end{tabular}\n",
            encoding="utf-8",
        )
        return
    k = float(cohen_kappa_score(humano, llm, labels=_LABELS))
    agree = sum(a == b for a, b in zip(humano, llm))
    lo, hi = _wilson_95(agree, n)
    cm = confusion_matrix(humano, llm, labels=_LABELS)
    rows = []
    for i, lab in enumerate(_LABELS):
        cells = " & ".join(str(int(x)) for x in cm[i])
        rows.append(f"{lab} & {cells} \\\\")
    body = "\n".join(rows)
    tex = (
        "\\begin{table}[ht]\n\\centering\n"
        "\\caption{Verificação humana amostral — concordância humano $\\times$ LLM "
        f"na elegibilidade (n={n}; $\\kappa$ de Cohen = {k:.3f}; "
        f"concordância = {agree}/{n} = {agree / n * 100:.1f}\\%, IC 95\\% "
        f"[{lo * 100:.1f}\\%, {hi * 100:.1f}\\%])}}\n"
        "\\label{tab:verificacao-kappa}\n"
        "\\begin{tabular}{lcc}\n\\toprule\n"
        " & \\multicolumn{2}{c}{LLM} \\\\\n"
        "Humano & incluir & excluir \\\\\n\\midrule\n"
        f"{body}\n"
        "\\bottomrule\n\\end{tabular}\n\\end{table}\n"
    )
    out.write_text(tex, encoding="utf-8")


def _acuracia_tex(aud: pd.DataFrame, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    rows_tex = []
    total_ok = total_n = 0
    for c in CAMPOS_CRITICOS:
        col = aud[f"{c}_auditoria"].astype(str).str.strip().str.lower()
        ok = int((col == "ok").sum())
        err = int((col == "erro").sum())
        n = ok + err
        acc = ok / n if n else float("nan")
        lo, hi = _wilson_95(ok, n)
        rows_tex.append(
            f"{c.replace('_', '\\_')} & {n} & {ok} & {err} & "
            f"{acc * 100:.1f}\\% & [{lo * 100:.1f}\\%, {hi * 100:.1f}\\%] \\\\"
        )
        total_ok += ok
        total_n += n
    total_acc = total_ok / total_n if total_n else float("nan")
    lo_t, hi_t = _wilson_95(total_ok, total_n)
    rows_tex.append("\\midrule")
    rows_tex.append(
        f"\\textbf{{Total}} & {total_n} & {total_ok} & {total_n - total_ok} & "
        f"{total_acc * 100:.1f}\\% & [{lo_t * 100:.1f}\\%, {hi_t * 100:.1f}\\%] \\\\"
    )
    body = "\n".join(rows_tex)
    tex = (
        "\\begin{table}[ht]\n\\centering\n"
        "\\caption{Verificação humana amostral — acurácia por campo crítico "
        "(auditoria humano sobre extração do LLM; IC Wilson 95\\%)}\n"
        "\\label{tab:verificacao-acuracia}\n"
        "\\begin{tabular}{lrrrrr}\n\\toprule\n"
        "Campo & n & ok & erro & Acurácia & IC 95\\% \\\\\n\\midrule\n"
        f"{body}\n"
        "\\bottomrule\n\\end{tabular}\n\\end{table}\n"
    )
    out.write_text(tex, encoding="utf-8")


def run(extraction: Path, sheet_eleg: Path, sheet_aud: Path,
        kappa_table: Path, acuracia_table: Path, annotated: Path) -> None:
    ext_df = pd.read_csv(extraction, encoding="utf-8", keep_default_na=False)
    eleg = pd.read_csv(sheet_eleg, encoding="utf-8", keep_default_na=False)
    aud = pd.read_csv(sheet_aud, encoding="utf-8", keep_default_na=False)

    _validate_eleg(eleg)
    _validate_aud(aud)

    llm_by_rid = _llm_decision_by_rid(ext_df)
    humano: list[str] = []
    llm: list[str] = []
    concorda: list[bool] = []
    for _, r in eleg.iterrows():
        rid = str(r["review_id"])
        h = normalize_decisao(r["decisao_humana"])  # i/e/incluir/excluir
        l = llm_by_rid.get(rid, "excluir")
        humano.append(h)
        llm.append(l)
        concorda.append(h == l)

    _kappa_tex(humano, llm, kappa_table)
    _acuracia_tex(aud, acuracia_table)

    annotated.parent.mkdir(parents=True, exist_ok=True)
    eleg_out = eleg.copy()
    eleg_out["decisao_llm"] = llm
    eleg_out["concorda_eleg"] = concorda
    # Merge linhas de auditoria por review_id
    aud_subset_cols = ["review_id"] + [f"{c}_auditoria" for c in CAMPOS_CRITICOS] \
        + [f"{c}_correto" for c in CAMPOS_CRITICOS] + ["nota_auditoria"]
    aud_subset = aud[aud_subset_cols]
    merged = eleg_out.merge(aud_subset, on="review_id", how="left")
    merged.to_csv(annotated, index=False, encoding="utf-8")

    print(f"Verify ingest: n={len(eleg)} eleg | n={len(aud)} aud")
    print(f"  → {kappa_table}\n  → {acuracia_table}\n  → {annotated}")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="κ + acurácia da verificação humana (4b-ii).")
    p.add_argument("--extraction", type=Path, required=True)
    p.add_argument("--sheet-eleg", type=Path, required=True)
    p.add_argument("--sheet-aud", type=Path, required=True)
    p.add_argument("--kappa-table", type=Path, required=True)
    p.add_argument("--acuracia-table", type=Path, required=True)
    p.add_argument("--annotated", type=Path, required=True)
    a = p.parse_args(argv)
    run(extraction=a.extraction, sheet_eleg=a.sheet_eleg,
        sheet_aud=a.sheet_aud, kappa_table=a.kappa_table,
        acuracia_table=a.acuracia_table, annotated=a.annotated)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
