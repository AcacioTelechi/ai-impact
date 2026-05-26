from pathlib import Path

import pytest

from scripts.analysis.corpus import load_corpus
from scripts.analysis.stats import NA_VALORES
from scripts.analysis.texkit import CANON

REAL = Path("data/processed/06_extraction.csv")


@pytest.mark.skipif(not REAL.exists(), reason="corpus real ausente")
@pytest.mark.parametrize("dim", sorted(CANON))
def test_canon_cobre_valores_reais(dim):
    df = load_corpus(REAL).df
    if dim not in df.columns:
        pytest.skip(f"coluna {dim} ausente no corpus")
    observados = {
        v.strip()
        for v in df[dim].fillna("").astype(str)
        if v.strip().lower() not in NA_VALORES
    }
    faltando = observados - set(CANON[dim])
    assert not faltando, f"{dim}: valores reais fora do CANON: {faltando}"
