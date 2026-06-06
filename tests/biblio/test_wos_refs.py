from scripts.biblio.wos_refs import parse_wos_bib, parse_wos_ref_labels, _extract_field

ENTRY = """@article{ WOS:000123,
Author = {Silva, J},
Title = {A paper},
DOI = {10.1111/AAA.111},
Cited-References = {Acemoglu D, 2022, ECONOMETRICA, V90, P1973, DOI 10.3982/ECTA19815.
   Autor X, 2019, J SEM DOI, V1, P1.
   Author B, 2018, AM ECON REV, V108, P1488, DOI 10.1257/AER.20160696.},
Number-of-Cited-References = {3},
Year = {2024},
}"""


def test_extract_field_balanced():
    cr = _extract_field(ENTRY, "cited-references")
    assert "ECTA19815" in cr and "AER.20160696" in cr
    # não vaza para o campo seguinte
    assert "Number-of-Cited-References" not in cr


def test_parse_maps_paper_doi_to_ref_dois(tmp_path):
    p = tmp_path / "wos.bib"
    p.write_text(ENTRY, encoding="utf-8")
    out = parse_wos_bib([p])
    assert "10.1111/aaa.111" in out
    refs = out["10.1111/aaa.111"]
    # refs sem DOI descartadas → ficam 2
    assert refs == ["10.3982/ecta19815", "10.1257/aer.20160696"]


def test_entry_without_doi_skipped(tmp_path):
    p = tmp_path / "wos.bib"
    p.write_text("@article{X,\nTitle = {No DOI},\nYear = {2020},\n}", encoding="utf-8")
    assert parse_wos_bib([p]) == {}


def test_parse_wos_ref_labels(tmp_path):
    p = tmp_path / "w.bib"
    p.write_text(ENTRY, encoding="utf-8")
    labels = parse_wos_ref_labels([p])
    assert labels["10.3982/ecta19815"] == "Acemoglu D, 2022"
    assert labels["10.1257/aer.20160696"] == "Author B, 2018"
