from pathlib import Path

import pandas as pd

from scripts.analysis import descritivas_corpus


def _sample_extraction() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"id": f"s-{i:03d}", "ano": y, "janela": j, "pre_pos_chatgpt": p,
             "tipo_estudo": t}
            for i, (y, j, p, t) in enumerate([
                (2015, "2013-2017", "pre", "exposição ocupacional"),
                (2016, "2013-2017", "pre", "teórico/modelo"),
                (2020, "2018-2022", "pre", "evidência macro/setorial"),
                (2023, "2022-2025", "pos", "exposição ocupacional"),
                (2024, "2022-2025", "pos", "firma/freelancer"),
            ], start=1)
        ]
    )


def test_descritivas_writes_year_histogram(tmp_path: Path) -> None:
    df = _sample_extraction()
    ext = tmp_path / "ext.csv"
    df.to_csv(ext, index=False)
    out_dir = tmp_path / "figs"
    descritivas_corpus.run(input=ext, output_dir=out_dir)
    assert (out_dir / "corpus_anos.pdf").exists()
    assert (out_dir / "corpus_janelas.pdf").exists()
    assert (out_dir / "corpus_tipo_estudo.pdf").exists()
