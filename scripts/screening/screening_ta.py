"""Pipeline step 03: title/abstract screening — dual-LLM (Sonnet + Haiku).

Cada registro é rotulado independentemente por dois modelos; a decisão final
é a união conservadora (excluir só se AMBOS excluírem — ver merge_conservative).
Em --mock usa heurística rule-based (testes/dry-run, sem custo de API).

NÃO importe scripts.screening.llm.batch_client no topo deste módulo:
batch_client importa `_mock_judge` daqui em nível de módulo; o uso de
screen_with_model abaixo é feito por import TARDIO dentro de run() para
manter o ciclo acíclico.

Colunas adicionadas a 02_corpus_dedup.csv: decisao_sonnet/haiku,
justificativa_sonnet/haiku, confianca_sonnet/haiku, decisao_final,
concordancia, criterio_exclusao.

CLI:
    python -m scripts.screening.screening_ta \\
        --input data/processed/02_corpus_dedup.csv \\
        --output data/processed/03_screening_ta.csv \\
        --incluidos data/processed/03_incluidos_ta.csv \\
        --cache-dir data/processed [--mock]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


def _mock_judge(row: pd.Series) -> dict:
    """Rule-based mock: include if title mentions AI + (employment OR labor OR jobs)."""
    text = f"{row['title']} {row['abstract']}".lower()
    has_ai = any(t in text for t in ["ai", "artificial intelligence", "machine learning", "llm", "gpt"])
    has_labor = any(
        t in text for t in ["employment", "labor", "labour", "jobs", "wages", "occupation"]
    )
    if has_ai and has_labor:
        return dict(decisao="incluir", justificativa="Mock: AI + labor keywords.", confianca=0.85, criterio=None)
    if has_ai:
        return dict(decisao="duvida", justificativa="Mock: AI mention but no labor.", confianca=0.5, criterio=None)
    return dict(decisao="excluir", justificativa="Mock: no AI keyword.", confianca=0.9, criterio="E1")


def merge_conservative(sonnet: dict, haiku: dict) -> dict:
    """União conservadora: excluir sse AMBOS = excluir.

    criterio_exclusao vem do modelo de maior confiança (só quando exclui).
    """
    both_exclude = sonnet["decisao"] == "excluir" and haiku["decisao"] == "excluir"
    final = "excluir" if both_exclude else "incluir"
    if both_exclude:
        winner = sonnet if sonnet["confianca"] >= haiku["confianca"] else haiku
        criterio = winner.get("criterio") or ""
    else:
        criterio = ""
    return {
        "decisao_sonnet": sonnet["decisao"],
        "justificativa_sonnet": sonnet["justificativa"],
        "confianca_sonnet": sonnet["confianca"],
        "decisao_haiku": haiku["decisao"],
        "justificativa_haiku": haiku["justificativa"],
        "confianca_haiku": haiku["confianca"],
        "decisao_final": final,
        "concordancia": "concordam" if sonnet["decisao"] == haiku["decisao"] else "divergem",
        "criterio_exclusao": criterio,
    }


SONNET = "claude-sonnet-4-6"
HAIKU = "claude-haiku-4-5-20251001"  # ID datado é o oficial do Haiku 4.5 (não é typo)


def run(
    input: Path,
    output: Path,
    incluidos: Path | None = None,
    mock: bool = False,
    cache_dir: Path | None = None,
) -> None:
    # Import tardio: batch_client importa _mock_judge deste módulo em nível
    # de módulo; importar aqui dentro mantém o ciclo acíclico.
    from scripts.screening.llm.batch_client import screen_with_model

    df = pd.read_csv(input, encoding="utf-8")

    cs = (cache_dir / "03_cache_sonnet.json") if cache_dir else None
    ch = (cache_dir / "03_cache_haiku.json") if cache_dir else None
    res_s = screen_with_model(df, model=SONNET, cache_path=cs, mock=mock)
    res_h = screen_with_model(df, model=HAIKU, cache_path=ch, mock=mock)

    merged = [merge_conservative(s, h) for s, h in zip(res_s, res_h)]
    mdf = pd.DataFrame(merged)
    out_df = pd.concat([df.reset_index(drop=True), mdf], axis=1)

    output.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(output, index=False, encoding="utf-8")

    if incluidos:
        inc = out_df[out_df["decisao_final"] == "incluir"]
        inc.to_csv(incluidos, index=False, encoding="utf-8")

    n_inc = int((out_df["decisao_final"] == "incluir").sum())
    n_div = int((out_df["concordancia"] == "divergem").sum())
    print(f"Screening: {len(out_df)} → {n_inc} incluir, "
          f"{len(out_df) - n_inc} excluir; {n_div} divergências")


def _cli(argv: list[str]) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--incluidos", type=Path)
    p.add_argument("--mock", action="store_true")
    p.add_argument("--cache-dir", type=Path, default=Path("data/processed"))
    a = p.parse_args(argv)
    run(a.input, a.output, incluidos=a.incluidos, mock=a.mock, cache_dir=a.cache_dir)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
