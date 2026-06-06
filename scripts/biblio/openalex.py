"""Cliente OpenAlex para aquisição de referências (Plano 6).

Fronteira de rede isolada: as funções recebem um `get(url)->dict` injetável,
testável sem rede. `make_http_get` devolve o `get` real (requests + polite pool
via mailto + retry). Identidade de referência sempre via DOI normalizado.
"""
from __future__ import annotations

from urllib.parse import quote

from scripts.biblio.dois import norm_doi

API = "https://api.openalex.org"


def _short_id(openalex_id: str) -> str:
    return (openalex_id or "").rstrip("/").rsplit("/", 1)[-1]


def referenced_works(doi: str, get, *, mailto: str) -> list[str]:
    # DOIs podem conter (), <>, ; etc. — encode o segmento p/ não gerar URL malformada
    url = f"{API}/works/https://doi.org/{quote(doi, safe='/')}?mailto={mailto}"
    obj = get(url)
    return [_short_id(w) for w in (obj.get("referenced_works") or [])]


def resolve_ids_to_dois(ids, get, *, mailto: str, batch: int = 50) -> dict[str, str]:
    ids = list(dict.fromkeys(ids))  # únicos, ordem preservada
    out: dict[str, str] = {}
    for i in range(0, len(ids), batch):
        chunk = ids[i:i + batch]
        filt = "openalex_id:" + "|".join(chunk)
        url = (f"{API}/works?filter={filt}&select=id,doi"
               f"&per-page={batch}&mailto={mailto}")
        for r in get(url).get("results", []):
            d = norm_doi(r.get("doi") or "")
            if d:
                out[_short_id(r.get("id", ""))] = d
    return out


def make_http_get(mailto: str):
    """`get(url)->dict` real, com retry/backoff em erros transitórios (5xx/rede);
    4xx (ex.: 404 = DOI não indexado) sobem na hora. Só usado em produção."""
    import requests
    from tenacity import (retry, retry_if_exception, stop_after_attempt,
                          wait_exponential)

    def _transient(e: BaseException) -> bool:
        if isinstance(e, requests.HTTPError) and e.response is not None:
            return e.response.status_code >= 500
        return isinstance(e, requests.RequestException)

    @retry(stop=stop_after_attempt(4),
           wait=wait_exponential(multiplier=2, min=2, max=30),
           retry=retry_if_exception(_transient))
    def get(url: str) -> dict:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()

    return get
