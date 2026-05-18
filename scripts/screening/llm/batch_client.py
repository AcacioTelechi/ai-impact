"""Cliente de screening em lote (Anthropic Message Batches API).

Funções puras (parse/cache_key/custom_id/build_requests) são testáveis sem
rede. A única fronteira de I/O — submeter o batch e coletar resultados — fica
isolada em `anthropic_submit_fn`, injetável via parâmetro `submit_fn`.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

from scripts.screening.llm.prompt import build_system_block, build_user_block
from scripts.screening.screening_ta import _mock_judge

load_dotenv()

_VALID = {"incluir", "excluir", "duvida"}

_FALLBACK = {
    "decisao": "duvida",
    "justificativa": "parse_fail",
    "confianca": 0.0,
    "criterio": None,
}


def parse_response(text: str) -> dict:
    """Parse tolerante. JSON irrecuperável → duvida/0 (nunca exclui por falha)."""
    if not text:
        return dict(_FALLBACK)
    s = text.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s.lstrip().lower().startswith("json"):
            s = s.lstrip()[4:]
        s = s.strip()
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", s, re.DOTALL)
        if not m:
            return dict(_FALLBACK)
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError:
            return dict(_FALLBACK)
    if not isinstance(obj, dict) or obj.get("decisao") not in _VALID:
        out = dict(_FALLBACK)
        out["justificativa"] = str(obj.get("justificativa", "parse_fail"))[:300] \
            if isinstance(obj, dict) else "parse_fail"
        return out
    try:
        conf = float(obj.get("confianca", 0.0))
    except (TypeError, ValueError):
        conf = 0.0
    return {
        "decisao": obj["decisao"],
        "justificativa": str(obj.get("justificativa", ""))[:300],
        "confianca": max(0.0, min(1.0, conf)),
        "criterio": obj.get("criterio") or None,
    }


def cache_key(row: pd.Series) -> str:
    """Chave de cache estável e idempotente. DOI normalizado → fallback título+ano."""
    doi = str(row.get("doi") or "").strip().lower()
    if doi and doi != "nan":
        return f"doi:{doi}"
    title = str(row.get("title") or "").strip().lower()
    year = str(row.get("year") or "").strip()
    return f"ty:{title}|{year}"


def custom_id(key: str) -> str:
    """custom_id seguro para a Batch API (≤64 chars, [A-Za-z0-9_-])."""
    return "r" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:32]


MAX_TOKENS = 400

_MODEL_LABELS = {
    "claude-sonnet-4-6": "Sonnet 4.6",
    "claude-haiku-4-5-20251001": "Haiku 4.5",
    "claude-opus-4-7": "Opus 4.7",
}


def _label(model: str) -> str:
    return _MODEL_LABELS.get(model, model)


def _fmt_elapsed(secs: float) -> str:
    secs = int(secs)
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def build_requests(df, model: str, cached: dict | None = None,
                   system_block: list[dict] | None = None,
                   user_content_fn=None,
                   max_tokens: int = MAX_TOKENS) -> list[dict]:
    """Um request por registro ainda não cacheado. system = bloco estável
    (screening por default; injetável p/ árbitro via system_block).
    user_content_fn(row)->str|list injetável (default: build_user_block)."""
    cached = cached or {}
    system = system_block if system_block is not None else build_system_block()
    content_fn = user_content_fn if user_content_fn is not None else build_user_block
    out: list[dict] = []
    for _, row in df.iterrows():
        cid = custom_id(cache_key(row))
        if cid in cached:
            continue
        out.append({
            "custom_id": cid,
            "params": {
                "model": model,
                "max_tokens": max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": content_fn(row)}],
            },
        })
    return out


def _load_cache(path: Path | None) -> dict:
    if path and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _save_cache(path: Path | None, cache: dict) -> None:
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, ensure_ascii=False, indent=2),
                        encoding="utf-8")


def screen_with_model(
    df,
    model: str,
    *,
    cache_path: Path | None = None,
    submit_fn=None,
    mock: bool = False,
    system_block: list[dict] | None = None,
    user_content_fn=None,
    parse_fn=None,
    max_tokens: int = MAX_TOKENS,
) -> list[dict]:
    """Rotula todos os registros do df com um modelo. Idempotente via cache.

    mock=True → usa _mock_judge (sem API). Caso contrário, submit_fn(requests)
    deve devolver {custom_id: texto_bruto}. Ordem do retorno segue o df.
    submit_fn deve devolver None p/ um custom_id cujo request errou na API
    (não cacheado → reprocessado numa nova execução); qualquer string,
    inclusive "", é resposta da API e vira fallback terminal cacheado. O
    anthropic_submit_fn real passa a emitir esse None numa etapa seguinte.
    """
    label = _label(model)
    if mock:
        print(f"[{label}] modo mock — {len(df)} registros (sem API, sem custo)")
        return [_mock_judge(row) for _, row in df.iterrows()]

    if submit_fn is None:
        submit_fn = anthropic_submit_fn(model)

    cache = _load_cache(cache_path)
    pending = build_requests(df, model=model, cached=cache,
                             system_block=system_block,
                             user_content_fn=user_content_fn,
                             max_tokens=max_tokens)
    n_total = len(df)
    n_pending = len(pending)
    print(
        f"[{label}] {n_total} registros | {n_total - n_pending} em cache | "
        f"{n_pending} a processar"
    )
    if pending:
        raw_by_cid = submit_fn(pending)
        n_skipped = 0
        for req in pending:
            cid = req["custom_id"]
            v = raw_by_cid.get(cid)            # None = API-errored / ausente
            if v is None:
                n_skipped += 1
                continue                       # NÃO cacheia → re-rodada reprocessa
            cache[cid] = (parse_fn or parse_response)(v)
        _save_cache(cache_path, cache)
        print(f"[{label}] {n_pending - n_skipped} processados e gravados em cache")
        if n_skipped:
            print(
                f"[{label}] {n_skipped} requests erraram na API e NÃO foram "
                f"cacheados — re-rode após resolver a causa (ex.: crédito)"
            )
    else:
        print(f"[{label}] nada a fazer → pulando (0 chamadas, $0)")

    _fallback = parse_fn or parse_response
    out: list[dict] = []
    for _, row in df.iterrows():
        cid = custom_id(cache_key(row))
        out.append(cache[cid] if cid in cache else _fallback(""))
    return out


POLL_INTERVAL_S = 15
POLL_TIMEOUT_S = 24 * 3600


def anthropic_submit_fn(model: str, client=None, poll_interval: float = POLL_INTERVAL_S):
    """Devolve submit_fn(requests)->{custom_id: str|None} via Message Batches API.

    client injetável para teste; em produção usa anthropic.Anthropic()
    (ANTHROPIC_API_KEY via .env). Retry/backoff na submissão.
    custom_id cujo request errou na API → None (não cacheado, reprocessado);
    sucesso → texto (string, podendo ser "").
    """
    if client is None:
        from anthropic import Anthropic
        client = Anthropic()

    @retry(stop=stop_after_attempt(4),
           wait=wait_exponential(multiplier=2, min=2, max=30))
    def _create(requests):
        return client.messages.batches.create(requests=requests)

    def submit_fn(requests: list[dict]) -> dict[str, str | None]:
        total = len(requests)
        batch = _create(requests)
        print(
            f"  [{_label(model)}] batch {batch.id} criado — {total} requests; "
            f"processamento assíncrono (minutos a horas)",
            flush=True,
        )
        start = time.monotonic()
        deadline = start + POLL_TIMEOUT_S
        while True:
            b = client.messages.batches.retrieve(batch.id)
            status = b.processing_status
            elapsed = _fmt_elapsed(time.monotonic() - start)
            rc = getattr(b, "request_counts", None)
            if rc is not None:
                done = (
                    getattr(rc, "succeeded", 0) + getattr(rc, "errored", 0)
                    + getattr(rc, "canceled", 0) + getattr(rc, "expired", 0)
                )
                print(
                    f"  [{_label(model)}] {batch.id}: {status} — "
                    f"{done}/{total} processados "
                    f"({getattr(rc, 'succeeded', 0)} ok, "
                    f"{getattr(rc, 'errored', 0)} erro, "
                    f"{getattr(rc, 'processing', 0)} na fila) — "
                    f"decorrido {elapsed}",
                    flush=True,
                )
            else:
                print(
                    f"  [{_label(model)}] {batch.id}: {status} — "
                    f"decorrido {elapsed}",
                    flush=True,
                )
            if status == "ended":
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Batch {batch.id} excedeu 24h")
            time.sleep(poll_interval)
        out: dict[str, str | None] = {}
        n_ok = n_err = n_empty = 0
        for entry in client.messages.batches.results(batch.id):
            if getattr(entry.result, "type", None) == "succeeded":
                blocks = entry.result.message.content
                txt = next(
                    (b.text for b in blocks if getattr(b, "type", None) == "text"),
                    "",
                )
                out[entry.custom_id] = txt
                if txt:
                    n_ok += 1
                else:
                    n_empty += 1
            else:
                out[entry.custom_id] = None  # API-errored → não cacheia (RC2)
                n_err += 1
        print(
            f"  [{_label(model)}] coletado: {n_ok} sucesso, "
            f"{n_err} erro (não cacheados), {n_empty} sem texto",
            flush=True,
        )
        return out

    return submit_fn
