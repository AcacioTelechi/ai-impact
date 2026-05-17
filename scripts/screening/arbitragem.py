"""Arbitragem por 3º LLM (Opus 4.7) dos soft-includes do screening.

Substitui a revisão humana: os 865 casos não-unânimes (decisão final
"incluir" não unânime) são decididos por um árbitro cego e independente,
forçado a binário. Ver docs/superpowers/specs/2026-05-17-arbitragem-3o-llm-design.md
e protocolo §7 (versão 1.1, emenda 2026-05-17).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from scripts.screening.agreement import cohen_kappa
from scripts.screening.llm.batch_client import cache_key, custom_id, screen_with_model
from scripts.screening.llm.prompt import build_arbiter_system_block
from scripts.screening.revisao_export import soft_includes

ARBITRO = "claude-opus-4-7"

_ARB_COLS = ["decisao_arbitro", "justificativa_arbitro", "confianca_arbitro",
             "decisao_final_arbitrada", "origem_decisao"]


def fundir(screening: pd.DataFrame, arb_by_rid: dict[str, dict]) -> pd.DataFrame:
    """Funde concordância LLM + veredito do árbitro nos 865.

    arb_by_rid: review_id → {decisao, justificativa, confianca}.
    Regra (spec §5): ambos-incluir/ambos-excluir → llm_concordante;
    soft-include → veredito binário do árbitro (origem 'arbitro'); veredito
    ∉ {incluir,excluir} → 'incluir' conservador (origem 'arbitro_falha').
    """
    out = screening.copy().reset_index(drop=True)
    d_arb, j_arb, c_arb, finais, origens = [], [], [], [], []
    for _, row in out.iterrows():
        s, h = row["decisao_sonnet"], row["decisao_haiku"]
        if s == "incluir" and h == "incluir":
            d_arb.append("")
            j_arb.append("")
            c_arb.append("")
            finais.append("incluir")
            origens.append("llm_concordante")
        elif s == "excluir" and h == "excluir":
            d_arb.append("")
            j_arb.append("")
            c_arb.append("")
            finais.append("excluir")
            origens.append("llm_concordante")
        else:
            a = arb_by_rid.get(custom_id(cache_key(row)), {})
            dec = a.get("decisao")
            d_arb.append(dec if dec is not None else "")
            j_arb.append(a.get("justificativa", ""))
            c_arb.append(a.get("confianca", ""))
            if dec == "incluir":
                finais.append("incluir")
                origens.append("arbitro")
            elif dec == "excluir":
                finais.append("excluir")
                origens.append("arbitro")
            else:
                finais.append("incluir")
                origens.append("arbitro_falha")
    out["decisao_arbitro"] = d_arb
    out["justificativa_arbitro"] = j_arb
    out["confianca_arbitro"] = c_arb
    out["decisao_final_arbitrada"] = finais
    out["origem_decisao"] = origens
    return out
