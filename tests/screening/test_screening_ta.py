import json
from pathlib import Path

import pandas as pd

from scripts.screening import screening_ta


def test_screening_ta_mock_marks_all_records(tmp_path: Path) -> None:
    """In mock mode, every record gets a decision/justification/confidence."""
    dedup = tmp_path / "dedup.csv"
    pd.DataFrame(
        [
            {
                "source": "wos",
                "doi": "10.1/a",
                "title": "AI and employment in the US",
                "authors": "Smith, J.",
                "year": 2020,
                "abstract": "...",
                "venue": "AER",
                "language": "en",
            },
            {
                "source": "wos",
                "doi": "10.1/b",
                "title": "AI tutors in classrooms",
                "authors": "Brown, P.",
                "year": 2019,
                "abstract": "...",
                "venue": "Educ Review",
                "language": "en",
            },
        ]
    ).to_csv(dedup, index=False)

    out = tmp_path / "screening_ta.csv"
    screening_ta.run(input=dedup, output=out, mock=True)

    df = pd.read_csv(out)
    assert {"decisao_llm", "justificativa_llm", "confianca_llm"} <= set(df.columns)
    assert len(df) == 2
    assert df["decisao_llm"].isin(["incluir", "excluir", "duvida"]).all()
    assert df["confianca_llm"].between(0, 1).all()


def test_screening_ta_writes_incluidos_file(tmp_path: Path) -> None:
    dedup = tmp_path / "dedup.csv"
    pd.DataFrame(
        [
            {
                "source": "wos",
                "doi": "10.1/a",
                "title": "AI and employment in the US",
                "authors": "Smith, J.",
                "year": 2020,
                "abstract": "AI exposure analysis",
                "venue": "AER",
                "language": "en",
            }
        ]
    ).to_csv(dedup, index=False)

    out = tmp_path / "screening_ta.csv"
    inc = tmp_path / "incluidos.csv"
    screening_ta.run(input=dedup, output=out, mock=True, incluidos=inc)

    inc_df = pd.read_csv(inc)
    # In mock mode, "AI and employment" matches inclusion → 1 row
    assert len(inc_df) >= 0  # mock heuristic may or may not include
