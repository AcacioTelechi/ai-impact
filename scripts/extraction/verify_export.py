"""Gera as duas planilhas da verificação humana amostral (4b-ii).

Planilha (a) — elegibilidade CEGA: o humano decide incluir/excluir sem ver
nenhuma coluna do LLM (decisão, motivo, campos extraídos). Insumo do κ.

Planilha (b) — auditoria de campos: o humano vê o valor do LLM + a fonte e
marca ok/erro (com o valor correto opcional). Insumo da acurácia por campo.

Idempotente: preserva input humano via merge_preserve; backup .bak-TS.csv.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import pandas as pd

from scripts.screening.llm.batch_client import cache_key, custom_id

CAMPOS_CRITICOS = (
    "pre_pos_chatgpt", "janela", "sinal_efeito",
    "tipo_estudo", "polarizacao", "score_qualidade",
)

ELEG_COLS = [
    "review_id", "decisao_humana", "nota_humana",
    "year", "title", "authors", "venue", "abstract",
    "text_source", "criterios_ref",
]

_CRITERIOS_REF = (
    "Estudo empírico/teórico sobre impacto da IA no mercado de trabalho "
    "(emprego/salários/ocupações), publicado em periódico ou working paper; "
    "janela 2013–2025; texto em inglês/português/espanhol/francês. "
    "Para detalhes, ver protocolo §5."
)


def _state_path(sheet: Path) -> Path:
    return sheet.with_suffix(".state.json")


def _backup(sheet: Path, ts: str) -> None:
    if sheet.exists():
        bak = sheet.with_suffix(f".bak-{ts}.csv")
        bak.write_bytes(sheet.read_bytes())


def _merge_preserve(fresh: pd.DataFrame, sheet: Path,
                    human_cols: list[str]) -> pd.DataFrame:
    if not sheet.exists():
        return fresh.reset_index(drop=True)
    prev = pd.read_csv(sheet, encoding="utf-8", keep_default_na=False)
    _ids = prev["review_id"].astype(str).str.strip()
    _dups = sorted(_ids[(_ids != "") & _ids.duplicated()].unique())
    if _dups:
        raise ValueError(
            f"review_id duplicado em {sheet.name} — corrija no LibreOffice "
            f"(cada linha deve ter um review_id único): {_dups}"
        )
    prev_idx = prev.set_index("review_id")
    out = fresh.copy()
    for col in human_cols:
        def _prev(rid: str, _col=col) -> str:
            if rid in prev_idx.index:
                val = prev_idx.loc[rid, _col] if _col in prev_idx.columns else ""
                return "" if pd.isna(val) else str(val)
            return ""
        out[col] = out["review_id"].map(_prev)
    return out.reset_index(drop=True)


def _load_prior_decided(sheet: Path) -> set[str]:
    sp = _state_path(sheet)
    if not sp.exists():
        return set()
    try:
        data = json.loads(sp.read_text(encoding="utf-8"))
        return set(data.get("decided_review_ids", []))
    except (json.JSONDecodeError, OSError) as e:
        print(f"  ⚠ Aviso: estado anterior inválido em {sp} ({e}); "
              f"detecção de perda ignorada nesta execução.")
        return set()


def _decided_eleg(df: pd.DataFrame) -> set[str]:
    mask = df["decisao_humana"].astype(str).str.strip() != ""
    return set(df.loc[mask, "review_id"].astype(str))


def _decided_aud(df: pd.DataFrame) -> set[str]:
    cols = [f"{c}_auditoria" for c in CAMPOS_CRITICOS]
    mask = pd.Series(False, index=df.index)
    for c in cols:
        if c in df.columns:
            mask = mask | (df[c].astype(str).str.strip() != "")
    return set(df.loc[mask, "review_id"].astype(str))


def _build_eleg_sheet(corpus: pd.DataFrame, extraction: pd.DataFrame,
                      sample: pd.DataFrame) -> pd.DataFrame:
    # Mapa review_id → corpus row (lado bibliográfico) + extraction (text_source)
    corp = corpus.copy()
    corp["review_id"] = corp.apply(
        lambda r: custom_id(cache_key(r)), axis=1,
    )
    corp_idx = corp.set_index("review_id")

    ext = extraction.rename(columns={"titulo": "title", "ano": "year"}).copy()
    ext["review_id"] = ext.apply(
        lambda r: custom_id(cache_key(r)), axis=1,
    )
    ts_by_rid = ext.set_index("review_id")["text_source"].to_dict()

    rows = []
    for rid in sample["review_id"]:
        if rid in corp_idx.index:
            row = corp_idx.loc[rid]
            rows.append({
                "review_id": rid,
                "decisao_humana": "", "nota_humana": "",
                "year": row.get("year", ""),
                "title": row.get("title", ""),
                "authors": row.get("authors", ""),
                "venue": row.get("venue", ""),
                "abstract": row.get("abstract", ""),
                "text_source": ts_by_rid.get(rid, ""),
                "criterios_ref": _CRITERIOS_REF,
            })
        else:
            # Sem registro no corpus → sinaliza para o humano (raro)
            rows.append({
                "review_id": rid, "decisao_humana": "", "nota_humana": "",
                "year": "", "title": "[review_id sem corpus]",
                "authors": "", "venue": "", "abstract": "",
                "text_source": ts_by_rid.get(rid, ""),
                "criterios_ref": _CRITERIOS_REF,
            })
    return pd.DataFrame(rows, columns=ELEG_COLS)


def _build_aud_sheet(corpus: pd.DataFrame, extraction: pd.DataFrame,
                     sample: pd.DataFrame) -> pd.DataFrame:
    inc_ids = set(sample.loc[sample["tipo"] == "inclusao", "review_id"])
    corp = corpus.copy()
    corp["review_id"] = corp.apply(
        lambda r: custom_id(cache_key(r)), axis=1,
    )
    corp_idx = corp.set_index("review_id")

    ext = extraction.rename(columns={"titulo": "title", "ano": "year"}).copy()
    ext["review_id"] = ext.apply(
        lambda r: custom_id(cache_key(r)), axis=1,
    )
    ext_idx = ext.set_index("review_id")

    rows = []
    for rid in sample["review_id"]:
        if rid not in inc_ids:
            continue
        row = {
            "review_id": rid,
            "year": corp_idx.loc[rid, "year"] if rid in corp_idx.index else "",
            "title": corp_idx.loc[rid, "title"] if rid in corp_idx.index else "",
            "doi": corp_idx.loc[rid, "doi"] if rid in corp_idx.index
                   and "doi" in corp_idx.columns else "",
            "text_source": ext_idx.loc[rid, "text_source"] if rid in ext_idx.index else "",
        }
        for c in CAMPOS_CRITICOS:
            row[f"{c}_llm"] = ext_idx.loc[rid, c] if rid in ext_idx.index else ""
            row[f"{c}_auditoria"] = ""
            row[f"{c}_correto"] = ""
        row["nota_auditoria"] = ""
        rows.append(row)
    cols = ["review_id", "year", "title", "doi", "text_source"]
    for c in CAMPOS_CRITICOS:
        cols += [f"{c}_llm", f"{c}_auditoria", f"{c}_correto"]
    cols.append("nota_auditoria")
    return pd.DataFrame(rows, columns=cols)


def run(extraction: Path, corpus: Path, sample: Path,
        sheet_eleg: Path, sheet_aud: Path) -> None:
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    ext_df = pd.read_csv(extraction, encoding="utf-8", keep_default_na=False)
    corp_df = pd.read_csv(corpus, encoding="utf-8", keep_default_na=False)
    sample_df = pd.read_csv(sample, encoding="utf-8", keep_default_na=False)

    fresh_eleg = _build_eleg_sheet(corp_df, ext_df, sample_df)
    fresh_aud = _build_aud_sheet(corp_df, ext_df, sample_df)

    eleg_human_cols = ["decisao_humana", "nota_humana"]
    aud_human_cols = [f"{c}_auditoria" for c in CAMPOS_CRITICOS] \
        + [f"{c}_correto" for c in CAMPOS_CRITICOS] \
        + ["nota_auditoria"]

    prior_e = _load_prior_decided(sheet_eleg)
    prior_a = _load_prior_decided(sheet_aud)

    merged_eleg = _merge_preserve(fresh_eleg, sheet_eleg, eleg_human_cols)
    merged_aud = _merge_preserve(fresh_aud, sheet_aud, aud_human_cols)

    cur_e = _decided_eleg(merged_eleg)
    cur_a = _decided_aud(merged_aud)
    lost_e = sorted(prior_e - cur_e)
    lost_a = sorted(prior_a - cur_a)

    _backup(sheet_eleg, ts)
    _backup(sheet_aud, ts)
    sheet_eleg.parent.mkdir(parents=True, exist_ok=True)
    sheet_aud.parent.mkdir(parents=True, exist_ok=True)
    merged_eleg.to_csv(sheet_eleg, index=False, encoding="utf-8")
    merged_aud.to_csv(sheet_aud, index=False, encoding="utf-8")

    _state_path(sheet_eleg).write_text(
        json.dumps({
            "exportado_em": ts,
            "n_linhas": len(merged_eleg),
            "decided_review_ids": sorted(cur_e),
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _state_path(sheet_aud).write_text(
        json.dumps({
            "exportado_em": ts,
            "n_linhas": len(merged_aud),
            "decided_review_ids": sorted(cur_a),
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Verify export: eleg {len(merged_eleg)} | aud {len(merged_aud)}")
    print(f"  → {sheet_eleg}\n  → {sheet_aud}")
    print("Instruções: auditoria ∈ {ok, erro}; vazio = pendente; "
          "correto = valor que deveria estar; nota_auditoria = comentário livre.")
    if lost_e:
        print(f"  ⚠ ATENÇÃO: {len(lost_e)} decisão(ões) de elegibilidade "
              f"registradas no último export sumiram da planilha "
              f"(review_id: {lost_e[:5]}{' …' if len(lost_e) > 5 else ''}). "
              f"Backups em {sheet_eleg.parent}/{sheet_eleg.stem}.bak-*.csv — "
              f"recupere de um anterior ao sumiço e re-exporte.")
    if lost_a:
        print(f"  ⚠ ATENÇÃO: {len(lost_a)} auditoria(s) de campos sumiram "
              f"da planilha (review_id: {lost_a[:5]}{' …' if len(lost_a) > 5 else ''}). "
              f"Backups em {sheet_aud.parent}/{sheet_aud.stem}.bak-*.csv — "
              f"recupere de um anterior ao sumiço e re-exporte.")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Exporta planilhas da verificação humana (4b-ii).")
    p.add_argument("--extraction", type=Path, required=True)
    p.add_argument("--corpus", type=Path, required=True)
    p.add_argument("--sample", type=Path, required=True)
    p.add_argument("--sheet-eleg", type=Path, required=True)
    p.add_argument("--sheet-aud", type=Path, required=True)
    a = p.parse_args(argv)
    run(extraction=a.extraction, corpus=a.corpus, sample=a.sample,
        sheet_eleg=a.sheet_eleg, sheet_aud=a.sheet_aud)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
