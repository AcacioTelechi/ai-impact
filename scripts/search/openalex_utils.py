"""Utilities for parsing OpenAlex API responses and boolean search queries."""
from __future__ import annotations

import re


def reconstruct_abstract(inverted_index: dict[str, list[int]] | None) -> str:
    """Rebuild a text abstract from OpenAlex's `abstract_inverted_index`.

    OpenAlex stores abstracts as `{word: [positions]}`. This function inverts
    the mapping to a position-ordered list of words and joins them.

    Missing positions (gaps in the indices) are silently skipped — only words
    that have an explicit position are rendered.
    """
    if not inverted_index:
        return ""
    by_position: dict[int, str] = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            by_position[pos] = word
    ordered = [by_position[p] for p in sorted(by_position)]
    return " ".join(ordered)


def parse_query_blocks(query: str) -> list[list[str]]:
    """Extract token lists from a WoS-style boolean query.

    Input format (lines starting with `#` are ignored):
        ( "a" OR "b" ) AND ( "c" OR "d" ) AND ( "e" )

    Returns a list of blocks, each block a list of quoted tokens (without
    quotes, without trailing wildcards).
    """
    # Strip comments
    cleaned = "\n".join(
        line for line in query.splitlines() if not line.strip().startswith("#")
    )
    # Split by AND first, then extract quoted terms per block
    parts = re.split(r"\bAND\b", cleaned, flags=re.IGNORECASE)
    blocks: list[list[str]] = []
    for part in parts:
        tokens = re.findall(r'"([^"]+)"', part)
        # strip trailing wildcards (OpenAlex doesn't use *)
        tokens = [t.rstrip("*").strip() for t in tokens if t.strip()]
        if tokens:
            blocks.append(tokens)
    return blocks
