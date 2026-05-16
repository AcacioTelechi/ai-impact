from pathlib import Path

import pandas as pd

from scripts.extraction import extract


def test_extract_schema_columns_are_complete() -> None:
    cols = extract.SCHEMA_COLUMNS
    assert "id" in cols
    assert "sinal_efeito" in cols
    assert "polarizacao" in cols
    assert "score_qualidade" in cols
    assert "revisto_humano" in cols
    assert len(cols) >= 27  # 7 blocks worth


def test_extract_save_appends_row(tmp_path: Path) -> None:
    out = tmp_path / "06_extraction.csv"
    row1 = {col: "" for col in extract.SCHEMA_COLUMNS}
    row1["id"] = "s-001"
    row1["titulo"] = "A"
    extract.save_row(row1, out)

    row2 = {col: "" for col in extract.SCHEMA_COLUMNS}
    row2["id"] = "s-002"
    row2["titulo"] = "B"
    extract.save_row(row2, out)

    df = pd.read_csv(out)
    assert len(df) == 2
    assert set(df["id"]) == {"s-001", "s-002"}


def test_extract_next_id_increments(tmp_path: Path) -> None:
    out = tmp_path / "06_extraction.csv"
    pd.DataFrame([{"id": "s-001"}, {"id": "s-003"}]).to_csv(out, index=False)
    assert extract.next_id(out) == "s-004"


def test_extract_next_id_empty_file(tmp_path: Path) -> None:
    assert extract.next_id(tmp_path / "nope.csv") == "s-001"
