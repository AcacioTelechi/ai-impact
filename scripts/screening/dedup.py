"""Pipeline step 02: deduplicate the raw corpus in three passes.

Pass 1: exact DOI match (normalized).
Pass 2: dedup_key match (first-author surname + year + normalized title).
Pass 3: embedding similarity on titles (cos-sim >= threshold), only over remaining
        candidates without DOI. Skipped if --no-embeddings.

CLI:
    python -m scripts.screening.dedup \
        --input data/processed/01_corpus_bruto.csv \
        --output data/processed/02_corpus_dedup.csv \
        --log data/processed/02_dedup_decisions.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from scripts.utils.normalization import dedup_key, normalize_doi, normalize_title


def _embedding_pass(df: pd.DataFrame, threshold: float = 0.95) -> tuple[pd.DataFrame, list[dict]]:
    """Mark near-duplicate titles via sentence embeddings. Returns (df_kept, log_rows)."""
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity

    model = SentenceTransformer("all-MiniLM-L6-v2")
    titles = df["title"].fillna("").tolist()
    if not titles:
        return df, []
    emb = model.encode(titles, show_progress_bar=False, convert_to_numpy=True)
    sim = cosine_similarity(emb)
    keep = [True] * len(df)
    log: list[dict] = []
    for i in range(len(df)):
        if not keep[i]:
            continue
        for j in range(i + 1, len(df)):
            if keep[j] and sim[i, j] >= threshold:
                keep[j] = False
                log.append(
                    dict(
                        removed_doi=df.iloc[j]["doi"],
                        kept_doi=df.iloc[i]["doi"],
                        rule="embedding",
                        kept_source=df.iloc[i]["source"],
                        similarity=float(sim[i, j]),
                    )
                )
    return df[keep].reset_index(drop=True), log


def run(input: Path, output: Path, log: Path, use_embeddings: bool = True) -> None:
    df = pd.read_csv(input, encoding="utf-8")
    df["doi_norm"] = df["doi"].fillna("").apply(normalize_doi)
    # Empty BibTeX fields arrive as NaN floats; dedup_key needs strings.
    for col in ("authors", "year", "title"):
        df[col] = df[col].fillna("").astype(str)
    df["dkey"] = df.apply(
        lambda r: dedup_key(authors=r["authors"], year=r["year"], title=r["title"]),
        axis=1,
    )

    decisions: list[dict] = []

    # Pass 1: DOI
    seen_doi: dict[str, int] = {}
    keep = [True] * len(df)
    for idx, row in df.iterrows():
        if not row["doi_norm"]:
            continue
        if row["doi_norm"] in seen_doi:
            keep[idx] = False
            kept_idx = seen_doi[row["doi_norm"]]
            decisions.append(
                dict(
                    removed_doi=row["doi"],
                    kept_doi=df.iloc[kept_idx]["doi"],
                    rule="doi",
                    kept_source=df.iloc[kept_idx]["source"],
                    similarity=1.0,
                )
            )
        else:
            seen_doi[row["doi_norm"]] = idx
    df_p1 = df[keep].reset_index(drop=True)

    # Pass 2: dedup_key (only meaningful when DOI is missing on at least one side)
    seen_key: dict[str, int] = {}
    keep = [True] * len(df_p1)
    for idx, row in df_p1.iterrows():
        k = row["dkey"]
        if not k:
            continue
        if k in seen_key:
            keep[idx] = False
            kept_idx = seen_key[k]
            decisions.append(
                dict(
                    removed_doi=row["doi"],
                    kept_doi=df_p1.iloc[kept_idx]["doi"],
                    rule="dedup_key",
                    kept_source=df_p1.iloc[kept_idx]["source"],
                    similarity=1.0,
                )
            )
        else:
            seen_key[k] = idx
    df_p2 = df_p1[keep].reset_index(drop=True)

    # Pass 3: embeddings (only on rows without DOI)
    if use_embeddings:
        mask_no_doi = df_p2["doi_norm"] == ""
        no_doi = df_p2[mask_no_doi].reset_index(drop=True)
        rest = df_p2[~mask_no_doi].reset_index(drop=True)
        no_doi_kept, emb_log = _embedding_pass(no_doi)
        decisions.extend(emb_log)
        df_final = pd.concat([rest, no_doi_kept], ignore_index=True)
    else:
        df_final = df_p2

    df_final = df_final.drop(columns=["doi_norm", "dkey"])
    output.parent.mkdir(parents=True, exist_ok=True)
    df_final.to_csv(output, index=False, encoding="utf-8")

    log.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(decisions).to_csv(log, index=False, encoding="utf-8")
    print(f"Dedup: {len(df)} → {len(df_final)} rows; log: {log}")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--log", type=Path, required=True)
    p.add_argument("--no-embeddings", action="store_true")
    args = p.parse_args(argv)
    run(args.input, args.output, args.log, use_embeddings=not args.no_embeddings)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
