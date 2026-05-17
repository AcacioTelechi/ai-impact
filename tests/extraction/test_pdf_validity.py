from pathlib import Path

from pypdf import PdfWriter

from scripts.extraction.pdf_validity import pdf_is_extractable


def _valid_pdf(p: Path) -> Path:
    w = PdfWriter()
    w.add_blank_page(width=72, height=72)
    with open(p, "wb") as f:
        w.write(f)
    return p


def _encrypted_pdf(p: Path) -> Path:
    w = PdfWriter()
    w.add_blank_page(width=72, height=72)
    w.encrypt("segredo")
    with open(p, "wb") as f:
        w.write(f)
    return p


def test_valid_pdf_is_extractable(tmp_path):
    assert pdf_is_extractable(_valid_pdf(tmp_path / "ok.pdf")) is True


def test_junk_bytes_not_extractable(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"<html>paywall</html>")
    assert pdf_is_extractable(bad) is False


def test_encrypted_pdf_not_extractable(tmp_path):
    assert pdf_is_extractable(_encrypted_pdf(tmp_path / "enc.pdf")) is False


def test_missing_path_not_extractable(tmp_path):
    assert pdf_is_extractable(tmp_path / "nope.pdf") is False
