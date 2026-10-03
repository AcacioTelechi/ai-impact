import json

import pandas as pd
import pytest

from scripts.analysis import aprofundamento as ap


def _df(n_por_celula: int = 6) -> pd.DataFrame:
    """Corpus sintético: alta-quali só aparece no pós e concentra-se em IA generativa."""
    rows = []
    tipos = ["exposição ocupacional", "evidência macro/setorial", "firma/freelancer",
             "teórico/modelo", "survey/revisão"]
    i = 0
    for ano in (2019, 2021, 2022, 2023, 2024, 2025):
        for tipo in tipos:
            for k in range(n_por_celula):
                i += 1
                pos = ano >= 2023
                genai = pos and k < 2
                alta = (genai and k == 0) or (pos and k == 5 and tipo == "firma/freelancer") \
                    or (not pos and k == 5 and tipo == "exposição ocupacional" and ano == 2022)
                rows.append({
                    "ano": ano, "pre_pos_chatgpt": "pos" if pos else "pre",
                    "pre_pos_chatgpt_llm": "pre" if k == 1 else ("pos" if pos else "pre"),
                    "tecnologia_focada": "IA generativa/LLMs" if genai else
                                         ("automação" if k % 2 else "geral"),
                    "tipo_estudo": tipo,
                    "polarizacao": "n/a" if k == 3 else
                                   ("alta-quali em risco" if alta else
                                    ("ambos" if k == 4 else "baixa-quali em risco")),
                    "sinal_efeito": ["negativo", "positivo", "ambíguo", "nulo"][(i + k) % 4],
                    "horizonte": ["curto prazo", "médio prazo", "longo prazo", "projeção"][i % 4],
                    "mec_deslocamento": "sim" if k != 2 else "não",
                    "mec_reinstalacao": "sim" if i % 2 else "não",
                    "mec_complementaridade": "sim" if (pos or k < 3) else "não",
                    "mec_demanda_agregada": "sim" if i % 5 == 0 else "não",
                    "pais_estudo": "China" if i % 7 == 0 else "multipais",
                    "score_qualidade": 4.0 if i % 3 == 0 else 3.0,
                    "text_source": "pdf" if i % 4 == 0 else "abstract",
                    "revisado_por_pares": "sim" if i % 6 else "não",
                    "metodo_empirico": ["IV", "descritivo", "OLS"][i % 3],
                })
    return ap.preparar(pd.DataFrame(rows))


def test_fisher_pre_pos_orienta_rc_como_pos_sobre_pre():
    sub = pd.DataFrame({"pre_pos_chatgpt": ["pre"] * 10 + ["pos"] * 10})
    alvo = pd.Series([True] + [False] * 9 + [True] * 5 + [False] * 5)
    r = ap.fisher_pre_pos(sub, alvo)
    assert (r["k_pre"], r["n_pre"], r["k_pos"], r["n_pos"]) == (1, 10, 5, 10)
    assert r["or"] == pytest.approx(9.0)  # (5/5)/(1/9)


def test_h1_especificacoes_exclui_na_e_cobre_sensibilidades():
    specs = dict(ap.h1_especificacoes(_df()))
    principal = specs["Principal: ano de publicação (pós = 2023+)"]
    # k==3 é n/a: 5 de 6 por célula entram no denominador
    assert principal["n_pre"] == 3 * 5 * 5 and principal["n_pos"] == 3 * 5 * 5
    assert principal["k_pos"] > principal["k_pre"]
    assert specs["Classificação original do LLM"]["n_pre"] > principal["n_pre"]
    assert specs["Excluindo estudos de IA generativa/LLMs"]["n_pos"] < principal["n_pos"]


def test_perfis_e_familia_de_testes():
    d = _df()
    tex, _ = ap.perfis_mecanismos(d)
    assert "Só deslocamento" in tex and "Só compensação" in tex
    fam = ap.familia_testes(d)
    assert len(fam) == 9
    assert all(0 <= p <= 1 for _, p in fam)


def test_run_gera_artefatos_em_virgula_decimal(tmp_path):
    d = _df()
    d = d.assign(elegivel="incluir", nota_extracao="ok", magnitude_normalizada="",
                 janela="")
    src = tmp_path / "06_extraction.csv"
    d.to_csv(src, index=False, encoding="utf-8")
    nums = ap.run(src, tmp_path / "tab", tmp_path / "fig", tmp_path / "n.json")
    esperadas = {"h1_sensibilidade", "polarizacao_tecnologia", "logit_h1", "sinal_por_tipo",
                 "composicao_ajuste", "perfis_mecanismos", "multiplos_testes", "validade_fonte",
                 "placebo_tecnologia", "robos_vs_genai"}
    assert {p.stem for p in (tmp_path / "tab").glob("*.tex")} == esperadas
    assert (tmp_path / "fig" / "h1_tendencia_anual.pdf").stat().st_size > 0
    assert json.loads((tmp_path / "n.json").read_text("utf-8"))["n"] == nums["n"] == len(d)
    tex = (tmp_path / "tab" / "h1_sensibilidade.tex").read_text("utf-8")
    assert r"\toprule" in tex and "2{,}" in tex or "{,}" in tex


def test_placebo_compara_pre_pos_dentro_do_objeto():
    d = _df()
    res = ap.placebo_tecnologia(d)
    assert [r["rotulo"] for r in res][0] == "Risco na alta qualificação"
    rob = res[0]["Robótica e automação"]
    # no sintético, 'automação' é k ímpar e não-genai: existe nos dois períodos
    assert rob["n_pre"] > 0 and rob["n_pos"] > 0
    tex = ap.tabela_placebo(res)
    assert r"\multicolumn{3}{c}{Robótica e automação}" in tex and r"\cmidrule" in tex
