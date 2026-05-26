from scripts.analysis.texkit import (
    CANON,
    escape,
    fmt_ci,
    fmt_p,
    fmt_pct,
    tabela_booktabs,
)


def test_escape_underscore_e_amp():
    assert escape("a_b & c") == r"a\_b \& c"


def test_fmt_pct_virgula_pt_br():
    assert fmt_pct(0.123) == r"12,3\%"


def test_fmt_p_ramos():
    assert fmt_p(0.0004) == r"$p<0{,}001$"
    assert fmt_p(0.042) == r"$p=0{,}0420$"


def test_fmt_ci():
    assert fmt_ci(0.236, 0.763) == "[23,6; 76,3]"


def test_tabela_booktabs_estrutura_e_notas():
    tex = tabela_booktabs(
        "ll",
        ["A", "B"],
        [["x", "y"], ["z", "w"]],
        notas=["nota de teste"],
    )
    assert r"\toprule" in tex and r"\midrule" in tex and r"\bottomrule" in tex
    assert r"A & B \\" in tex
    assert r"x & y \\" in tex
    assert "nota de teste" in tex and r"\footnotesize" in tex


def test_canon_tem_dimensoes_chave():
    for dim in ("polarizacao", "sinal_efeito", "janela", "tecnologia_focada"):
        assert dim in CANON and len(CANON[dim]) >= 2
    assert CANON["janela"] == ["2013-2017", "2018-2022", "2022-2026"]
