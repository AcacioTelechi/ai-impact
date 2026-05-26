import pandas as pd

from scripts.analysis.sintese_janelas import run


def _csv(tmp_path):
    rows = []
    spec = [
        ("2013-2017", "automação", "exposição ocupacional", "negativo", "baixa-quali em risco", "sim", "não"),
        ("2013-2017", "automação", "exposição ocupacional", "negativo", "baixa-quali em risco", "sim", "não"),
        ("2022-2026", "IA generativa/LLMs", "firma/freelancer", "ambíguo", "alta-quali em risco", "não", "sim"),
    ]
    for jan, tec, tipo, sinal, pol, desl, compl in spec:
        rows.append({"elegivel": "incluir", "nota_extracao": "ok", "janela": jan,
                     "tecnologia_focada": tec, "tipo_estudo": tipo, "sinal_efeito": sinal,
                     "polarizacao": pol, "mec_deslocamento": desl, "mec_reinstalacao": "não",
                     "mec_complementaridade": compl, "mec_demanda_agregada": "não",
                     "score_qualidade": "3", "magnitude_normalizada": ""})
    p = tmp_path / "06_extraction.csv"
    pd.DataFrame(rows).to_csv(p, index=False, encoding="utf-8")
    return p


def test_tabela_tem_3_janelas_e_N(tmp_path):
    out_tab = tmp_path / "sintese_janelas.tex"
    out_fig = tmp_path / "mecanismos_janela.pdf"
    run(_csv(tmp_path), out_tab, out_fig)
    tex = out_tab.read_text(encoding="utf-8")
    assert "2013-2017" in tex and "2018-2022" in tex and "2022-2026" in tex
    assert "n=2" in tex  # janela 1 tem 2 estudos
    # mecanismos devem RENDERIZAR (não começar a linha com %, que é comentário LaTeX)
    assert "Deslocamento" in tex and "Complementaridade" in tex
    for linha in tex.splitlines():
        assert not linha.lstrip().startswith("%"), f"linha vira comentário LaTeX: {linha!r}"
    assert out_fig.exists() and out_fig.stat().st_size > 0


def test_determinismo(tmp_path):
    csv = _csv(tmp_path)
    a, b = tmp_path / "a.tex", tmp_path / "b.tex"
    run(csv, a, tmp_path / "f1.pdf")
    run(csv, b, tmp_path / "f2.pdf")
    assert a.read_text(encoding="utf-8") == b.read_text(encoding="utf-8")
