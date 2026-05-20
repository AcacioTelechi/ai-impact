"""Congela o quadro amostral da verificação humana (4b-ii) e sorteia a amostra.

Idempotente: se os snapshots já existem, recarrega-os e não re-sorteia. Isso
sobrevive à re-rodada idempotente de `make extract-llm` que recuperará os 61
estudos sem extração — o frame fica nos 790 da 1ª rodada por decisão da spec.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.screening.llm.batch_client import cache_key, custom_id

_FRAME_COLS = ["review_id", "text_source", "confianca_extracao",
               "elegivel", "motivo_exclusao"]


def _conf_bin(x: float) -> str:
    if x < 0.6:
        return "baixa"
    if x <= 0.8:
        return "media"
    return "alta"


def _build_frame(extraction_csv: Path) -> pd.DataFrame:
    df = pd.read_csv(extraction_csv, encoding="utf-8", keep_default_na=False)
    df = df[df["nota_extracao"] != "parse_fail"].copy()
    # cache_key/custom_id são definidos sobre {doi,title,year}; aqui o corpus
    # de extração usa {doi, titulo, ano} → adaptamos as colunas.
    df_kk = df.rename(columns={"titulo": "title", "ano": "year"})
    df["review_id"] = df_kk.apply(
        lambda r: custom_id(cache_key(r)), axis=1,
    )
    df["confianca_extracao"] = pd.to_numeric(
        df["confianca_extracao"], errors="coerce",
    ).fillna(0.0)
    return df[_FRAME_COLS].reset_index(drop=True)


_INCLUIDO_VALUES = {"sim", "incluir"}


def _stratify_inclusoes(frame: pd.DataFrame, rng: np.random.Generator,
                        fracao: float = 0.10) -> pd.DataFrame:
    inc = frame[
        frame["elegivel"].isin(_INCLUIDO_VALUES)
        & (frame["motivo_exclusao"] == "")
    ].copy()
    inc["confianca_bin"] = inc["confianca_extracao"].apply(_conf_bin)
    # Coerce to str to avoid Arrow-backed dtype mismatches em concat str+str
    inc["estrato"] = inc["text_source"].astype(str) + "_" + inc["confianca_bin"].astype(str)
    out = []
    for est, g in inc.groupby("estrato", sort=True):
        n = len(g)
        alvo = max(math.ceil(fracao * n), min(5, n))
        idx = rng.choice(g.index.to_numpy(), size=alvo, replace=False)
        out.append(g.loc[idx, ["review_id", "estrato"]])
    res = pd.concat(out, ignore_index=True) if out else pd.DataFrame(
        columns=["review_id", "estrato"],
    )
    res["tipo"] = "inclusao"
    return res


def _all_exclusoes(frame: pd.DataFrame) -> pd.DataFrame:
    excl = frame[
        ~frame["elegivel"].isin(_INCLUIDO_VALUES)
        | (frame["motivo_exclusao"] != "")
    ]
    out = pd.DataFrame({
        "review_id": excl["review_id"].values,
        "estrato": "excluir",
        "tipo": "exclusao",
    })
    return out


def run(extraction: Path, frame: Path, sample: Path, seed: int = 42) -> None:
    # Frame: snapshot
    if frame.exists():
        frame_df = pd.read_csv(frame, encoding="utf-8", keep_default_na=False)
        print(f"  frame carregado de {frame} ({len(frame_df)} linhas)")
    else:
        frame_df = _build_frame(extraction)
        frame.parent.mkdir(parents=True, exist_ok=True)
        frame_df.to_csv(frame, index=False, encoding="utf-8")
        print(f"  frame gravado em {frame} ({len(frame_df)} linhas)")

    # Amostra: snapshot
    if sample.exists():
        sdf = pd.read_csv(sample, encoding="utf-8", keep_default_na=False)
        print(f"  amostra carregada de {sample} ({len(sdf)} linhas)")
        return

    rng = np.random.default_rng(seed)
    exc = _all_exclusoes(frame_df)
    inc = _stratify_inclusoes(frame_df, rng)
    sdf = pd.concat([exc, inc], ignore_index=True)
    sample.parent.mkdir(parents=True, exist_ok=True)
    sdf.to_csv(sample, index=False, encoding="utf-8")
    print(
        f"  amostra gravada em {sample}: "
        f"{(sdf['tipo'] == 'exclusao').sum()} exclusões (100%) + "
        f"{(sdf['tipo'] == 'inclusao').sum()} inclusões (estratificado, seed={seed})"
    )


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Sorteia a amostra de verificação humana (4b-ii).")
    p.add_argument("--extraction", type=Path, required=True)
    p.add_argument("--frame", type=Path, required=True)
    p.add_argument("--sample", type=Path, required=True)
    p.add_argument("--seed", type=int, default=42)
    a = p.parse_args(argv)
    run(extraction=a.extraction, frame=a.frame, sample=a.sample, seed=a.seed)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
