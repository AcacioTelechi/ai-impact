"""Arbitragem por 3º LLM (Opus 4.7) dos soft-includes do screening.

Substitui a revisão humana: os 865 casos não-unânimes (decisão final
"incluir" não unânime) são decididos por um árbitro cego e independente,
forçado a binário. Ver docs/superpowers/specs/2026-05-17-arbitragem-3o-llm-design.md
e protocolo §7 (versão 1.1, emenda 2026-05-17).
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import pandas as pd

from scripts.screening.agreement import cohen_kappa
from scripts.screening.llm.batch_client import cache_key, custom_id, screen_with_model
from scripts.screening.llm.prompt import build_arbiter_system_block
from scripts.screening.revisao_export import soft_includes

ARBITRO = "claude-opus-4-7"


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
    # confianca_arbitro: "" (str) p/ concordantes/arbitro_falha-sem-rid;
    # float p/ arbitrados. Coluna object dtype intencional (sobrevive CSV).
    out["confianca_arbitro"] = c_arb
    out["decisao_final_arbitrada"] = finais
    out["origem_decisao"] = origens
    return out


def _to_binary(label: str) -> str:
    """incluir/duvida → 'incluir' (manter); excluir → 'excluir'.

    Mantém o rótulo no espaço ["incluir","excluir","duvida"] de
    agreement.cohen_kappa (o "duvida" ausente tem marginal zero e não
    altera κ → reúso DRY correto)."""
    return "excluir" if str(label) == "excluir" else "incluir"


def kappa_table(arbitrado: pd.DataFrame, output_table: Path) -> None:
    """Concordância par-a-par árbitro×Sonnet e árbitro×Haiku nos arbitrados.

    κ é calculado APENAS nas linhas onde o árbitro realmente decidiu
    (origem_decisao == "arbitro"). Linhas "arbitro_falha" (decisão ausente,
    forçadas a incluir pelo fallback conservador) são excluídas do κ mas
    contadas e divulgadas na legenda.
    """
    sub = arbitrado[arbitrado["origem_decisao"] == "arbitro"]
    n_falha = int((arbitrado["origem_decisao"] == "arbitro_falha").sum())
    n = len(sub)
    output_table.parent.mkdir(parents=True, exist_ok=True)
    if n == 0:
        output_table.write_text(
            "\\begin{tabular}{l}\\toprule Nenhum arbitrado \\\\ \\bottomrule \\end{tabular}\n",
            encoding="utf-8")
        print(f"κ árbitro = n/a (0 arbitrados reais; {n_falha} falhas técnicas); → {output_table}")
        return
    arb = [_to_binary(x) for x in sub["decisao_arbitro"]]
    son = [_to_binary(x) for x in sub["decisao_sonnet"]]
    hai = [_to_binary(x) for x in sub["decisao_haiku"]]
    k_s, k_h = cohen_kappa(arb, son), cohen_kappa(arb, hai)
    ag_s = int(sum(a == b for a, b in zip(arb, son)))
    ag_h = int(sum(a == b for a, b in zip(arb, hai)))
    k_s_str = f"{k_s:.3f}" if math.isfinite(k_s) else "n/a"
    k_h_str = f"{k_h:.3f}" if math.isfinite(k_h) else "n/a"
    tex = (
        "\\begin{table}[ht]\n\\centering\n"
        "\\caption{Concordância do árbitro (Opus 4.7) com os triadores nos "
        f"casos efetivamente arbitrados (n={n}; {n_falha} falhas técnicas "
        "excluídas do $\\kappa$ e forçadas a incluir; rótulo binário: "
        "excluir vs. manter [incluir/duvida])}\n"
        "\\label{tab:arbitragem-kappa}\n"
        "\\begin{tabular}{lcc}\n\\toprule\n"
        "Par & Concordância & $\\kappa$ de Cohen \\\\\n\\midrule\n"
        f"Árbitro × Sonnet 4.6 & {ag_s}/{n} = {ag_s / n * 100:.1f}\\% & {k_s_str} \\\\\n"
        f"Árbitro × Haiku 4.5 & {ag_h}/{n} = {ag_h / n * 100:.1f}\\% & {k_h_str} \\\\\n"
        "\\bottomrule\n\\end{tabular}\n\\end{table}\n"
    )
    output_table.write_text(tex, encoding="utf-8")
    print(f"κ árbitro×Sonnet={k_s_str}, ×Haiku={k_h_str} (n={n}; {n_falha} falhas excluídas); → {output_table}")
