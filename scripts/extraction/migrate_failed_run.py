"""One-off: limpa o cache e corrige o manifesto após a 1ª rodada real de
extract-llm (batch 791 ok / 61 errored — ver
docs/superpowers/specs/2026-05-17-fix-extract-llm-cache-pdf-robustez-design.md).

NÃO faz extração (sem custo de modelo): só lê os resultados do batch (retidos
~29 dias) e ajusta arquivos locais. Idempotente — rodar 2× = no-op.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

DEFAULT_BATCH = "msgbatch_01Bye7bKuBLg9xjQ3pt3W9Er"
_BAD_PDF = {"pdf_protegido", "pdf_invalido"}


def _err_message(result) -> str:
    err = getattr(result, "error", None)
    if err is None:
        return ""
    inner = getattr(err, "error", err)
    return str(getattr(inner, "message", "") or "")


# Substrings abaixo são as mensagens de erro observadas empiricamente no batch
# msgbatch_01Bye7bKuBLg9xjQ3pt3W9Er (saldo insuficiente / PDF protegido / PDF inválido);
# qualquer outra mensagem → "outro".
def classify(msg: str) -> str:
    m = msg.lower()
    if "credit balance" in m:
        return "credito"
    if "password protected" in m:
        return "pdf_protegido"
    if "not valid" in m:
        return "pdf_invalido"
    return "outro"


def collect_errored(client, batch_id: str) -> dict[str, str]:
    """{custom_id: categoria} p/ entradas com result.type != 'succeeded'."""
    out: dict[str, str] = {}
    for e in client.messages.batches.results(batch_id):
        if getattr(e.result, "type", None) != "succeeded":
            out[e.custom_id] = classify(_err_message(e.result))
    return out


def run(client, batch_id: str, cache_path: Path, manifest_path: Path,
        dry_run: bool) -> dict:
    errored = collect_errored(client, batch_id)
    cache = (json.loads(Path(cache_path).read_text(encoding="utf-8"))
             if Path(cache_path).exists() else {})
    to_remove = [cid for cid in errored if cid in cache]

    man = pd.read_csv(manifest_path, encoding="utf-8", keep_default_na=False)
    pdf_before = int((man["text_source"] == "pdf").sum())
    changed = 0
    for cid, cat in errored.items():
        if cat not in _BAD_PDF:
            continue
        mask = man["review_id"] == cid
        if mask.any() and (man.loc[mask, "text_source"] == "pdf").any():
            man.loc[mask, "text_source"] = "abstract"
            man.loc[mask, "status"] = cat
            changed += int(mask.sum())
    pdf_after = int((man["text_source"] == "pdf").sum())

    report = {
        "errored_total": len(errored),
        "cache_removed": len(to_remove),
        "cache_kept": len(cache) - len(to_remove),
        "manifest_changed": changed,
        "pdf_before": pdf_before,
        "pdf_after": pdf_after,
        "by_category": {c: sum(1 for v in errored.values() if v == c)
                        for c in sorted(set(errored.values()))},
        "backups": [],
    }
    if not dry_run:
        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        for f in (Path(cache_path), Path(manifest_path)):
            if f.exists():
                bak = f.with_suffix(f.suffix + f".bak-{ts}")
                shutil.copy2(f, bak)
                report["backups"].append(str(bak))
        for cid in to_remove:
            del cache[cid]
        Path(cache_path).write_text(
            json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        man.to_csv(manifest_path, index=False, encoding="utf-8")
    return report


def _cli(argv) -> int:
    p = argparse.ArgumentParser(description="Migração pós-rodada extract-llm.")
    p.add_argument("--batch-id", default=DEFAULT_BATCH)
    p.add_argument("--cache", type=Path,
                   default=Path("data/processed/06_cache_extract.json"))
    p.add_argument("--manifest", type=Path,
                   default=Path("data/processed/04_fulltext_manifest.csv"))
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)
    from dotenv import load_dotenv
    load_dotenv()
    from anthropic import Anthropic
    rep = run(Anthropic(), a.batch_id, a.cache, a.manifest, a.dry_run)
    tag = "[DRY-RUN] " if a.dry_run else ""
    print(f"{tag}errored={rep['errored_total']} categorias={rep['by_category']}")
    print(f"{tag}cache: removidos={rep['cache_removed']} "
          f"mantidos={rep['cache_kept']}")
    print(f"{tag}manifesto: linhas alteradas={rep['manifest_changed']} | "
          f"text_source=pdf {rep['pdf_before']} → {rep['pdf_after']}")
    print(f"backups: {rep['backups']}")
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
