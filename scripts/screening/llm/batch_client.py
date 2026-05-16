"""Cliente de screening em lote (Anthropic Message Batches API).

Funções puras (parse/cache_key/custom_id/build_requests) são testáveis sem
rede. A única fronteira de I/O — submeter o batch e coletar resultados — fica
isolada em `anthropic_submit_fn`, injetável via parâmetro `submit_fn`.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pandas as pd

from scripts.screening.llm.prompt import build_system_block, build_user_block
from scripts.screening.screening_ta import _mock_judge

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


def build_requests(df, model: str, cached: dict | None = None) -> list[dict]:
    """Um request por registro ainda não cacheado. system = bloco estável."""
    cached = cached or {}
    system = build_system_block()
    out: list[dict] = []
    for _, row in df.iterrows():
        cid = custom_id(cache_key(row))
        if cid in cached:
            continue
        out.append({
            "custom_id": cid,
            "params": {
                "model": model,
                "max_tokens": MAX_TOKENS,
                "system": system,
                "messages": [{"role": "user", "content": build_user_block(row)}],
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
) -> list[dict]:
    """Rotula todos os registros do df com um modelo. Idempotente via cache.

    mock=True → usa _mock_judge (sem API). Caso contrário, submit_fn(requests)
    deve devolver {custom_id: texto_bruto}. Ordem do retorno segue o df.
    """
    if mock:
        return [_mock_judge(row) for _, row in df.iterrows()]

    if submit_fn is None:
        submit_fn = anthropic_submit_fn(model)

    cache = _load_cache(cache_path)
    pending = build_requests(df, model=model, cached=cache)
    if pending:
        raw_by_cid = submit_fn(pending)
        for req in pending:
            cid = req["custom_id"]
            cache[cid] = parse_response(raw_by_cid.get(cid, ""))
        _save_cache(cache_path, cache)

    return [cache[custom_id(cache_key(row))] for _, row in df.iterrows()]
