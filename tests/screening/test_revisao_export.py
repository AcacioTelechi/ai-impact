from __future__ import annotations

import pandas as pd

from scripts.screening.revisao_export import soft_includes


def _row(s, h, final):
    return {
        "source": "wos", "doi": "", "title": "T", "authors": "A",
        "year": 2020, "abstract": "x", "venue": "V", "language": "en",
        "decisao_sonnet": s, "justificativa_sonnet": "js", "confianca_sonnet": 0.5,
        "decisao_haiku": h, "justificativa_haiku": "jh", "confianca_haiku": 0.5,
        "decisao_final": final, "concordancia": "x", "criterio_exclusao": "",
    }


def test_soft_includes_excludes_both_incluir_and_both_excluir():
    df = pd.DataFrame([
        _row("incluir", "incluir", "incluir"),   # ambos-incluir → fora
        _row("excluir", "excluir", "excluir"),    # ambos-excluir → fora
        _row("incluir", "duvida", "incluir"),     # soft → dentro
        _row("duvida", "excluir", "incluir"),     # soft → dentro
        _row("incluir", "excluir", "incluir"),    # divergência → dentro
        _row("duvida", "duvida", "incluir"),      # soft → dentro
    ])
    sel = soft_includes(df)
    assert len(sel) == 4
    # nenhum ambos-incluir nem qualquer excluir-final no resultado
    assert ((sel["decisao_sonnet"] == "incluir") & (sel["decisao_haiku"] == "incluir")).sum() == 0
    assert (sel["decisao_final"] == "excluir").sum() == 0
