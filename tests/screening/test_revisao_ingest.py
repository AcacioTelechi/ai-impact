# tests/screening/test_revisao_ingest.py
import numpy as np
import pandas as pd
import pytest

from scripts.screening.revisao_ingest import normalize_decisao


@pytest.mark.parametrize("raw,exp", [
    ("i", "incluir"), ("I", "incluir"), ("incluir", "incluir"),
    ("INCLUIR", "incluir"), (" e ", "excluir"), ("excluir", "excluir"),
    ("", "pendente"), ("   ", "pendente"), (None, "pendente"),
    (float("nan"), "pendente"), (np.nan, "pendente"), (pd.NA, "pendente"),
])
def test_normalize_valid_and_empty(raw, exp):
    assert normalize_decisao(raw) == exp


@pytest.mark.parametrize("bad", ["x", "talvez", "1", "sim", "yes", "s", "n", "nao", "não"])
def test_normalize_invalid_raises(bad):
    with pytest.raises(ValueError):
        normalize_decisao(bad)
