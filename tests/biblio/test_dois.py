from scripts.biblio.dois import norm_doi


def test_bare_doi_lowercased():
    assert norm_doi("10.1257/AER.20160696") == "10.1257/aer.20160696"


def test_strips_url_prefix():
    assert norm_doi("https://doi.org/10.3982/ECTA19815") == "10.3982/ecta19815"


def test_extracts_doi_from_wos_ref_string():
    ref = "Acemoglu D, 2022, ECONOMETRICA, V90, P1973, DOI 10.3982/ECTA19815."
    assert norm_doi(ref) == "10.3982/ecta19815"


def test_strips_trailing_punctuation():
    assert norm_doi("10.1016/j.frl.2025.109145.") == "10.1016/j.frl.2025.109145"


def test_no_doi_returns_empty():
    assert norm_doi("Acemoglu D, 2019, J ECON PERSPECT, V33, P3") == ""
    assert norm_doi("") == ""
    assert norm_doi("nan") == ""
