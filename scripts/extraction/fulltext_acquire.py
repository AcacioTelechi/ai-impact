"""Plano 4a: aquisição de texto completo dos estudos pós-arbitragem.

Resolve PDFs via drop-in manual (prioridade) → Unpaywall OA → senão
abstract. Armazena o PDF nativo (o 4b o envia direto ao Claude; sem
extração de texto aqui). Emite um manifesto de cobertura.

Ver docs/superpowers/specs/2026-05-17-plano-4a-aquisicao-texto-design.md
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from scripts.screening.llm.batch_client import cache_key, custom_id
from scripts.screening.fetch_fulltext import _unpaywall_lookup

MAX_PDF_BYTES = 32 * 1024 * 1024  # 32 MB — guard p/ limite prático da API no 4b


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), reraise=True)
def _http_get_bytes(url: str) -> bytes | None:
    """GET com retry/backoff (apenas 5xx). None se 4xx/empty (sem retry)."""
    r = requests.get(url, timeout=30)
    if r.status_code >= 500:
        r.raise_for_status()  # HTTPError → tenacity re-tenta (5xx transitório)
    if r.status_code != 200 or not r.content:
        return None
    return r.content


def download_pdf(url: str, dest: Path, *, get_fn=None, max_bytes: int = MAX_PDF_BYTES) -> str:
    """Baixa atômico: grava `.part`, renomeia no sucesso. Nunca deixa parcial.

    Retorna: "ok" | "download_falhou" | "oversized".
    get_fn(url)->bytes|None injetável (default: _http_get_bytes); em teste, fake.
    """
    get = get_fn if get_fn is not None else _http_get_bytes
    try:
        data = get(url)
    except Exception:
        data = None
    if not data:
        return "download_falhou"
    if len(data) > max_bytes:
        return "oversized"
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(".pdf.part")
    part.write_bytes(data)
    part.replace(dest)  # rename atômico no mesmo filesystem
    return "ok"


def assign_ids(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona `review_id` e `id` (s-NNN) estáveis, ordenados por review_id.

    Determinístico e estável sob reordenação do CSV — `id` é a chave que
    liga 4a → 4b → extração.
    """
    out = df.copy()
    out["review_id"] = [custom_id(cache_key(r)) for _, r in out.iterrows()]
    out = out.sort_values("review_id", kind="stable").reset_index(drop=True)
    out["id"] = [f"s-{i:03d}" for i in range(1, len(out) + 1)]
    return out


def resolve(row, id_: str, manual_dir: Path, oa_dir: Path, *, email: str,
            lookup_fn, download_fn) -> dict:
    """Resolve o texto de UM registro. Precedência: manual > oa-cache >
    unpaywall+download > abstract. Retorna a linha do manifesto.

    lookup_fn(doi, email)->dict|None — injetado por run() (prod: _unpaywall_lookup).
    download_fn(url, dest)->str — injetado por run() (prod: download_pdf).
    """
    _doi = row.get("doi")
    doi = "" if pd.isna(_doi) else str(_doi).strip()
    base = {"id": id_, "review_id": row.get("review_id", ""),
            "doi": doi, "title": str(row.get("title") or "")}

    manual_pdf = manual_dir / f"{id_}.pdf"
    if manual_pdf.exists():
        return {**base, "text_source": "pdf", "fonte": "manual",
                "pdf_path": str(manual_pdf), "status": "ok_manual"}

    oa_pdf = oa_dir / f"{id_}.pdf"
    if oa_pdf.exists():  # idempotente: já baixado antes
        return {**base, "text_source": "pdf", "fonte": "unpaywall",
                "pdf_path": str(oa_pdf), "status": "ok_oa"}

    if not doi:
        return {**base, "text_source": "abstract", "fonte": "—",
                "pdf_path": "", "status": "sem_doi"}

    rec = lookup_fn(doi, email)
    if not rec or not rec.get("pdf_url"):
        return {**base, "text_source": "abstract", "fonte": "—",
                "pdf_path": "", "status": "nao_oa"}

    st = download_fn(rec["pdf_url"], oa_pdf)
    if st == "ok":
        return {**base, "text_source": "pdf", "fonte": "unpaywall",
                "pdf_path": str(oa_pdf), "status": "ok_oa"}
    return {**base, "text_source": "abstract", "fonte": "—",
            "pdf_path": "", "status": st}  # download_falhou | oversized


def run(input: Path, manifest: Path, email: str,
        manual_dir: Path, oa_dir: Path,
        lookup_fn=None, download_fn=None) -> None:
    lookup_fn = lookup_fn if lookup_fn is not None else _unpaywall_lookup
    download_fn = download_fn if download_fn is not None else download_pdf
    manual_dir.mkdir(parents=True, exist_ok=True)
    oa_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input, encoding="utf-8", keep_default_na=False)
    df = assign_ids(df)

    rows: list[dict] = []
    for _, r in df.iterrows():
        rows.append(resolve(r, r["id"], manual_dir, oa_dir, email=email,
                            lookup_fn=lookup_fn, download_fn=download_fn))
    mf = pd.DataFrame(rows).sort_values("id", kind="stable").reset_index(drop=True)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    mf.to_csv(manifest, index=False, encoding="utf-8")

    n = len(mf)
    n_pdf = int((mf["text_source"] == "pdf").sum())
    n_man = int((mf["fonte"] == "manual").sum())
    n_oa = int((mf["fonte"] == "unpaywall").sum())
    n_abs = int((mf["text_source"] == "abstract").sum())
    print(f"Aquisição: {n_pdf} pdf ({n_man} manual / {n_oa} oa) | "
          f"{n_abs} abstract — de {n}")
    print(f"  → {manifest}")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Plano 4a: aquisição de texto completo.")
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--email", default="")
    p.add_argument("--manual-dir", type=Path, default=Path("data/raw/fulltext/manual"))
    p.add_argument("--oa-dir", type=Path, default=Path("data/raw/fulltext/oa"))
    a = p.parse_args(argv)
    run(input=a.input, manifest=a.manifest, email=a.email,
        manual_dir=a.manual_dir, oa_dir=a.oa_dir)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
