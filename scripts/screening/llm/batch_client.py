"""Cliente de screening em lote (Anthropic Message Batches API).

Funções puras (parse/cache_key/custom_id/build_requests) são testáveis sem
rede. A única fronteira de I/O — submeter o batch e coletar resultados — fica
isolada em `anthropic_submit_fn`, injetável via parâmetro `submit_fn`.
"""
from __future__ import annotations

import hashlib
import json
import re

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
