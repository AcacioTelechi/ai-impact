import pandas as pd

from scripts.analysis.comparacao_pre_pos import run


def _csv(tmp_path):
    rows = []
    # pré: maioria baixa-quali; pós: mais alta-quali (desloca o risco)
    spec = (
        [("pre", "baixa-quali em risco", "negativo", "4")] * 12
        + [("pre", "alta-quali em risco", "ambíguo", "3")] * 2
        + [("pos", "baixa-quali em risco", "negativo", "5")] * 7
        + [("pos", "alta-quali em risco", "ambíguo", "4")] * 9
    )
    for per, pol, sinal, score in spec:
        rows.append({"elegivel": "incluir", "nota_extracao": "ok",
                     "pre_pos_chatgpt": per, "polarizacao": pol, "sinal_efeito": sinal,
                     "tipo_estudo": "exposição ocupacional", "horizonte": "médio prazo",
                     "mec_deslocamento": "sim", "mec_reinstalacao": "não",
                     "mec_complementaridade": "não", "mec_demanda_agregada": "não",
                     "score_qualidade": score, "magnitude_normalizada": ("0.1" if per == "pre" else "")})
    p = tmp_path / "06_extraction.csv"
    pd.DataFrame(rows).to_csv(p, index=False, encoding="utf-8")
    return p


def _run(tmp_path):
    d = tmp_path / "tabs"
    run(_csv(tmp_path), d)
    return d


def _no_comment_lines(tex):
    for linha in tex.splitlines():
        assert not linha.lstrip().startswith("%"), f"linha vira comentário LaTeX: {linha!r}"


def test_tabela_central_tem_p_e_ressalva(tmp_path):
    tex = (_run(tmp_path) / "comparacao_pre_pos.tex").read_text(encoding="utf-8")
    assert "$p" in tex                  # algum p-valor
    assert "amostra" in tex.lower()     # ressalva injetada
    _no_comment_lines(tex)


def test_polarizacao_2x2_com_fisher_e_wilson(tmp_path):
    tex = (_run(tmp_path) / "polarizacao_pre_pos.tex").read_text(encoding="utf-8")
    assert "alta-quali em risco" in tex
    assert "Fisher" in tex
    assert "[" in tex and ";" in tex    # IC Wilson formatado
    _no_comment_lines(tex)


def test_robustez_usa_score_ge_4(tmp_path):
    tex = (_run(tmp_path) / "robustez_qualidade.tex").read_text(encoding="utf-8")
    assert "score" in tex.lower() and "4" in tex
    assert "n=12" in tex  # 2 linhas pré com score 3 foram excluídas (senão n=14)
    _no_comment_lines(tex)


def test_magnitude_sem_teste(tmp_path):
    tex = (_run(tmp_path) / "magnitude_cobertura.tex").read_text(encoding="utf-8")
    assert "Cobertura" in tex or "cobertura" in tex
    assert "$p" not in tex              # NÃO há teste de hipótese
    _no_comment_lines(tex)
