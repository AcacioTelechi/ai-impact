import pandas as pd

from scripts.analysis.descritivas_corpus import run


def _csv(tmp_path):
    rows = []
    # 3 incluídos-extraídos
    for ano, jan, tipo, tec, pub, rev, met, pais in [
        (2015, "2013-2017", "exposição ocupacional", "automação", "journal", "sim", "OLS", "EUA"),
        (2020, "2018-2022", "teórico/modelo", "deep learning", "journal", "sim", "modelo teórico", "EUA"),
        (2024, "2022-2026", "firma/freelancer", "IA generativa/LLMs", "working paper", "não", "DiD", "Brasil"),
    ]:
        rows.append({"elegivel": "incluir", "nota_extracao": "ok", "ano": ano,
                     "janela": jan, "tipo_estudo": tipo, "tecnologia_focada": tec,
                     "tipo_pub": pub, "revisado_por_pares": rev, "metodo_empirico": met,
                     "pais_estudo": pais, "score_qualidade": "3", "magnitude_normalizada": ""})
    # ruído que NÃO pode contaminar as figuras
    rows.append({"elegivel": "excluir", "nota_extracao": "ok", "ano": 1999,
                 "janela": "2013-2017", "tipo_estudo": "survey/revisão", "tecnologia_focada": "geral",
                 "tipo_pub": "journal", "revisado_por_pares": "sim", "metodo_empirico": "descritivo",
                 "pais_estudo": "EUA", "score_qualidade": "1", "magnitude_normalizada": ""})
    rows.append({"elegivel": "incluir", "nota_extracao": "parse_fail", "ano": 2024,
                 "janela": "2022-2026", "tipo_estudo": "", "tecnologia_focada": "",
                 "tipo_pub": "", "revisado_por_pares": "", "metodo_empirico": "",
                 "pais_estudo": "", "score_qualidade": "", "magnitude_normalizada": ""})
    p = tmp_path / "06_extraction.csv"
    pd.DataFrame(rows).to_csv(p, index=False, encoding="utf-8")
    return p


def test_gera_4_figuras_e_tabela(tmp_path):
    figdir = tmp_path / "figs"
    tabdir = tmp_path / "tabs"
    run(_csv(tmp_path), figdir, tabdir / "descritivas_corpus.tex")
    for f in ("corpus_anos.pdf", "corpus_janelas.pdf",
              "corpus_tipo_estudo.pdf", "corpus_tecnologia.pdf"):
        assert (figdir / f).exists() and (figdir / f).stat().st_size > 0
    tex = (tabdir / "descritivas_corpus.tex").read_text(encoding="utf-8")
    assert r"\toprule" in tex
    # N descritivo = 3 incluídos-extraídos (exclui o excluir e o parse_fail)
    assert "3" in tex
    # ano de estudo excluído não vaza para a tabela
    assert "1999" not in tex


def test_determinismo_tex(tmp_path):
    csv = _csv(tmp_path)
    out1 = tmp_path / "a.tex"
    out2 = tmp_path / "b.tex"
    run(csv, tmp_path / "f1", out1)
    run(csv, tmp_path / "f2", out2)
    assert out1.read_text(encoding="utf-8") == out2.read_text(encoding="utf-8")
