"""End-to-end pipeline test on synthetic data."""
from pathlib import Path

import pandas as pd

from scripts.screening.consolidate import run as consolidate
from scripts.screening.dedup import run as dedup
from scripts.screening.screening_ta import run as screening_ta


FIXTURES = Path(__file__).parent / "fixtures"


def test_pipeline_consolidate_dedup_screen(tmp_path: Path) -> None:
    # 1. Consolidate
    bruto = tmp_path / "01_bruto.csv"
    consolidate(
        sources=[FIXTURES / "sample_wos.csv", FIXTURES / "sample_scopus.csv"],
        output=bruto,
    )
    assert pd.read_csv(bruto).shape[0] == 9

    # 2. Dedup
    deduped = tmp_path / "02_dedup.csv"
    log = tmp_path / "02_log.csv"
    dedup(input=bruto, output=deduped, log=log, use_embeddings=False)
    assert pd.read_csv(deduped).shape[0] == 7  # 2 duplicates removed

    # 3. Screening (mock mode)
    screened = tmp_path / "03_screening.csv"
    incl = tmp_path / "03_incluidos.csv"
    screening_ta(input=deduped, output=screened, incluidos=incl, mock=True)
    df = pd.read_csv(screened)
    assert {"decisao_llm", "justificativa_llm", "confianca_llm"} <= set(df.columns)
    # At least 1 record should be marked include or duvida (mock heuristic)
    assert (df["decisao_llm"].isin(["incluir", "duvida"])).sum() >= 1
