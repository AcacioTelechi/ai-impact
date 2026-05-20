"""Testes do verify_sample: frame snapshot + amostragem estratificada determinística."""
from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd
import pytest


def _mk_extraction(n_inc_pdf_alta=20, n_inc_pdf_baixa=10,
                   n_inc_abs_media=30, n_excl=5,
                   n_parse_fail=3, tmp_path: Path | None = None) -> Path:
    """Fabrica um 06_extraction.csv mínimo com mix controlado de estratos."""
    rows = []
    counter = 0

    def add(elegivel, motivo, text_source, confianca, nota_extracao):
        nonlocal counter
        counter += 1
        rows.append({
            "id": f"s-{counter}", "doi": f"d{counter}",
            "titulo": f"t{counter}", "autores": "x",
            "ano": "2024", "periodico": "j", "tipo_pub": "j",
            "pais_estudo": "", "periodo_dados": "", "janela": "",
            "pre_pos_chatgpt": "", "tecnologia_focada": "",
            "tipo_estudo": "", "metodo_empirico": "",
            "unidade_analise": "", "fonte_dados": "",
            "mec_deslocamento": "", "mec_reinstalacao": "",
            "mec_complementaridade": "", "mec_demanda_agregada": "",
            "mec_outros": "", "sinal_efeito": "",
            "magnitude_reportada": "", "magnitude_normalizada": "",
            "ocupacoes_afetadas": "", "polarizacao": "",
            "horizonte": "", "score_qualidade": "",
            "limitacoes_declaradas": "", "replicavel": "",
            "revisado_por_pares": "",
            "nota_extracao": nota_extracao,
            "citacoes_chave": "", "revisto_humano": "",
            "elegivel": elegivel, "motivo_exclusao": motivo,
            "text_source": text_source,
            "confianca_extracao": str(confianca),
        })

    for _ in range(n_inc_pdf_alta):
        add("sim", "", "pdf", 0.90, "")
    for _ in range(n_inc_pdf_baixa):
        add("sim", "", "pdf", 0.40, "")
    for _ in range(n_inc_abs_media):
        add("sim", "", "abstract", 0.70, "")
    for _ in range(n_excl):
        add("nao", "fora do escopo", "abstract", 0.80, "")
    for _ in range(n_parse_fail):
        add("sim", "", "abstract", 0.0, "parse_fail")

    p = (tmp_path or Path("/tmp")) / "06_extraction.csv"
    pd.DataFrame(rows).to_csv(p, index=False, encoding="utf-8")
    return p


def test_frame_exclui_parse_fail(tmp_path):
    from scripts.extraction import verify_sample as V
    ext = _mk_extraction(tmp_path=tmp_path)
    frame = tmp_path / "frame.csv"
    sample = tmp_path / "sample.csv"
    V.run(extraction=ext, frame=frame, sample=sample, seed=42)

    df = pd.read_csv(frame, encoding="utf-8", keep_default_na=False)
    assert len(df) == 65  # 60 inc + 5 excl, 3 parse_fail excluídos
    assert "nota_extracao" not in df.columns  # filtrado, não preservado
    assert set(df.columns) == {
        "review_id", "text_source", "confianca_extracao",
        "elegivel", "motivo_exclusao",
    }


def test_amostra_100pct_exclusoes(tmp_path):
    from scripts.extraction import verify_sample as V
    ext = _mk_extraction(n_excl=5, tmp_path=tmp_path)
    frame = tmp_path / "frame.csv"
    sample = tmp_path / "sample.csv"
    V.run(extraction=ext, frame=frame, sample=sample, seed=42)

    sdf = pd.read_csv(sample, encoding="utf-8", keep_default_na=False)
    exclusoes = sdf[sdf["tipo"] == "exclusao"]
    assert len(exclusoes) == 5
    assert (exclusoes["estrato"] == "excluir").all()


def test_amostra_inclusoes_estratificada_com_piso(tmp_path):
    """Estrato pdf_alta tem 20 → ceil(0.10*20)=2, piso min(5,20)=5 → 5."""
    from scripts.extraction import verify_sample as V
    ext = _mk_extraction(n_inc_pdf_alta=20, n_inc_pdf_baixa=10,
                         n_inc_abs_media=30, n_excl=0, n_parse_fail=0,
                         tmp_path=tmp_path)
    frame = tmp_path / "frame.csv"
    sample = tmp_path / "sample.csv"
    V.run(extraction=ext, frame=frame, sample=sample, seed=42)

    sdf = pd.read_csv(sample, encoding="utf-8", keep_default_na=False)
    inc = sdf[sdf["tipo"] == "inclusao"]
    counts = inc["estrato"].value_counts().to_dict()
    # 20 → piso 5; 10 → piso 5; 30 → ceil(3) vs min(5,30)=5 → 5
    assert counts.get("pdf_alta") == 5
    assert counts.get("pdf_baixa") == 5
    assert counts.get("abstract_media") == 5


def test_idempotencia_snapshot(tmp_path):
    """Se frame/sample já existem, nova chamada não muda nada."""
    from scripts.extraction import verify_sample as V
    ext = _mk_extraction(tmp_path=tmp_path)
    frame = tmp_path / "frame.csv"
    sample = tmp_path / "sample.csv"
    V.run(extraction=ext, frame=frame, sample=sample, seed=42)
    h1 = frame.read_bytes(), sample.read_bytes()
    # Simula re-rodada do extract: muda nota_extracao em 2 linhas
    df = pd.read_csv(ext, encoding="utf-8", keep_default_na=False)
    df.loc[df["nota_extracao"] == "parse_fail", "nota_extracao"] = ""
    df.to_csv(ext, index=False, encoding="utf-8")
    V.run(extraction=ext, frame=frame, sample=sample, seed=42)
    h2 = frame.read_bytes(), sample.read_bytes()
    assert h1 == h2  # byte-idêntico


def test_seed_determinismo(tmp_path):
    """Mesma seed em executions limpas → mesma amostra (em diretórios separados)."""
    from scripts.extraction import verify_sample as V
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    ext_a = _mk_extraction(tmp_path=a)
    ext_b = _mk_extraction(tmp_path=b)
    V.run(extraction=ext_a, frame=a / "f.csv", sample=a / "s.csv", seed=42)
    V.run(extraction=ext_b, frame=b / "f.csv", sample=b / "s.csv", seed=42)
    assert (a / "s.csv").read_bytes() == (b / "s.csv").read_bytes()
