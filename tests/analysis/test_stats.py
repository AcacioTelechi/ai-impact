import math

import pandas as pd
import pytest

from scripts.analysis.stats import (
    RESSALVA,
    assoc_chi2,
    assoc_fisher_2x2,
    prop_por_periodo,
    wilson95,
)


def _df():
    # pre: 2 baixa, 1 n/a ; pos: 1 baixa, 1 alta
    return pd.DataFrame(
        {
            "pre_pos_chatgpt": ["pre", "pre", "pre", "pos", "pos"],
            "polarizacao": [
                "baixa-quali em risco",
                "baixa-quali em risco",
                "n/a",
                "baixa-quali em risco",
                "alta-quali em risco",
            ],
        }
    )


def test_prop_exclui_na_do_denominador():
    r = prop_por_periodo(_df(), "polarizacao")
    assert r.n_classif["pre"] == 2          # n/a fora
    assert r.n_na["pre"] == 1
    assert r.counts["pre"]["baixa-quali em risco"] == 2
    assert r.pct("pre", "baixa-quali em risco") == pytest.approx(1.0)
    assert r.pct("pos", "alta-quali em risco") == pytest.approx(0.5)


def test_chi2_confere_com_contingencia_conhecida():
    # associação perfeita -> p pequeno
    df = pd.DataFrame(
        {
            "pre_pos_chatgpt": ["pre"] * 20 + ["pos"] * 20,
            "polarizacao": ["baixa-quali em risco"] * 20 + ["alta-quali em risco"] * 20,
        }
    )
    res = assoc_chi2(prop_por_periodo(df, "polarizacao"))
    assert res.p < 0.001
    assert res.dof == 1


def test_fisher_independencia_p_alto():
    df = pd.DataFrame(
        {
            "pre_pos_chatgpt": ["pre"] * 10 + ["pos"] * 10,
            "polarizacao": (["alta-quali em risco", "baixa-quali em risco"] * 5) * 2,
        }
    )
    r = assoc_fisher_2x2(df, "polarizacao", foco="alta-quali em risco")
    assert r.p > 0.5
    assert r.k_pre == 5 and r.n_pre == 10
    assert r.k_pos == 5 and r.n_pos == 10


def test_wilson95_valor_conhecido():
    low, high = wilson95(5, 10)
    assert low == pytest.approx(0.2366, abs=1e-3)
    assert high == pytest.approx(0.7634, abs=1e-3)


def test_ressalva_menciona_nao_amostra():
    assert "amostra" in RESSALVA.lower()
    assert "explorat" in RESSALVA.lower()


def test_chi2_low_expected_em_celulas_pequenas():
    df = pd.DataFrame(
        {
            "pre_pos_chatgpt": ["pre", "pre", "pre", "pos", "pos", "pos"],
            "polarizacao": [
                "baixa-quali em risco", "baixa-quali em risco", "alta-quali em risco",
                "baixa-quali em risco", "alta-quali em risco", "alta-quali em risco",
            ],
        }
    )
    res = assoc_chi2(prop_por_periodo(df, "polarizacao"))
    assert res.low_expected is True


def test_chi2_periodo_sem_classificados_levanta():
    df = pd.DataFrame(
        {
            "pre_pos_chatgpt": ["pre", "pre", "pos"],
            "polarizacao": ["n/a", "n/a", "baixa-quali em risco"],
        }
    )
    with pytest.raises(ValueError, match="sem linhas classificadas"):
        assoc_chi2(prop_por_periodo(df, "polarizacao"))
