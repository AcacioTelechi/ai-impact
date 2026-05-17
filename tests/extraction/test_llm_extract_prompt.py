# tests/extraction/test_llm_extract_prompt.py
from scripts.extraction.llm_extract_prompt import build_extract_system_block


def test_extract_block_cacheable_stable():
    a = build_extract_system_block()
    b = build_extract_system_block()
    assert a == b
    assert isinstance(a, list) and len(a) == 1
    blk = a[0]
    assert blk["type"] == "text" and blk["cache_control"] == {"type": "ephemeral"}
    t = blk["text"]
    for code in ("E1", "E2", "E3", "E4", "E5"):
        assert code in t
    for f in ("janela", "pre_pos_chatgpt", "tipo_estudo", "metodo_empirico",
              "mec_deslocamento", "sinal_efeito", "score_qualidade",
              "limitacoes_declaradas", "nota_extracao"):
        assert f in t
    assert "1" in t and "5" in t
    assert '"elegivel"' in t and '"extracao"' in t and '"confianca_extracao"' in t
    assert "n/a" in t.lower()
    assert "não inven" in t.lower()
    assert "2022-2026" in t and "2022-2025" not in t   # janela corrigida
    assert "IA generativa/LLMs" in t
    assert "alta-quali em risco" in t and "baixa-quali em risco" in t
    assert "curto prazo" in t and "projeção" in t
    assert "<inteiro 1-5>" in t
