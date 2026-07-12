"""
Lightweight heuristic prompt-injection screening.

This is deliberately NOT a silver bullet — no regex list stops a determined
attacker. Its real job in this architecture is defense-in-depth alongside
the Validation/Grounding agent: even if injected text makes it into a
retrieved chunk (e.g. someone embeds "ignore previous instructions" inside
a spec document), the system prompt structure keeps instructions and
retrieved content in clearly separated, labeled blocks, and the grounding
check refuses to emit claims not tied to real citations — so an injected
instruction has no path to becoming an ungrounded, unchecked action.
"""
from __future__ import annotations

import re

_INJECTION_PATTERNS = [
    re.compile(r"ignore (?:all |any |previous |prior )*instructions", re.IGNORECASE),
    re.compile(r"disregard (the|your) (system|previous) prompt", re.IGNORECASE),
    re.compile(r"you are now (in )?(dan|developer mode|jailbreak)", re.IGNORECASE),
    re.compile(r"reveal (your|the) system prompt", re.IGNORECASE),
    re.compile(r"act as (if you (were|are) )?(an? )?unrestricted", re.IGNORECASE),
    re.compile(r"</?system>", re.IGNORECASE),
]


def screen_for_injection(text: str) -> list[str]:
    """Returns a list of matched pattern descriptions (empty = clean)."""
    hits = []
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            hits.append(pattern.pattern)
    return hits


def wrap_untrusted_content(label: str, content: str) -> str:
    """
    Wraps retrieved document content in explicit delimiters so the LLM
    treats it as DATA to analyze, never as INSTRUCTIONS to follow — this is
    the primary defense against injected text hiding inside source documents.
    """
    return f"<untrusted_document_content source=\"{label}\">\n{content}\n</untrusted_document_content>"
