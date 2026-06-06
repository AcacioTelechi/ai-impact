from scripts.biblio.openalex import referenced_works, resolve_ids_to_dois


def fake_get_factory(responses):
    def get(url):
        return responses[url]
    return get


def test_referenced_works_returns_ids():
    url = "https://api.openalex.org/works/https://doi.org/10.1/x?mailto=e@x"
    get = fake_get_factory({url: {"referenced_works": ["https://openalex.org/W1",
                                                        "https://openalex.org/W2"]}})
    assert referenced_works("10.1/x", get, mailto="e@x") == ["W1", "W2"]


def test_resolve_ids_to_dois_batches():
    calls = []

    def get(url):
        calls.append(url)
        return {"results": [{"id": "https://openalex.org/W1", "doi": "https://doi.org/10.1000/A"},
                            {"id": "https://openalex.org/W2", "doi": None}]}

    out = resolve_ids_to_dois(["W1", "W2"], get, mailto="e@x", batch=50)
    assert out == {"W1": "10.1000/a"}   # W2 sem DOI é omitido
    assert len(calls) == 1            # um único lote
