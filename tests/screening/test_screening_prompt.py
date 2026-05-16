import pandas as pd

from scripts.screening.llm.prompt import build_system_block, build_user_block


def test_system_block_is_cacheable_and_stable():
    a = build_system_block()
    b = build_system_block()
    assert a == b  # determinístico → cacheável
    assert isinstance(a, list) and len(a) == 1
    blk = a[0]
    assert blk["type"] == "text"
    assert blk["cache_control"] == {"type": "ephemeral"}
    txt = blk["text"]
    # janela corrigida (era 2013-2025) e os cinco critérios E1-E5
    assert "2013-01-01" in txt and "2026-06-30" in txt
    for code in ("E1", "E2", "E3", "E4", "E5"):
        assert code in txt
    # E4 explicitamente não-aplicável em título/resumo
    assert "E4" in txt and "não" in txt.lower() and "texto completo" in txt.lower()
    # contrato JSON estrito
    assert '"decisao"' in txt and '"confianca"' in txt and '"criterio"' in txt


def test_user_block_contains_record_fields_only():
    row = pd.Series({
        "title": "AI and Jobs", "authors": "Smith, J.", "year": 2020,
        "venue": "AER", "abstract": "We study AI exposure.",
    })
    u = build_user_block(row)
    assert "AI and Jobs" in u and "Smith, J." in u and "2020" in u
    assert "We study AI exposure." in u
    # o bloco do registro NÃO repete os critérios (eles vão no system cacheado)
    assert "E1" not in u and "CRITÉRIOS" not in u
