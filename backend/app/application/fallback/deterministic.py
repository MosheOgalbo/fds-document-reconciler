from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from app.domain.entities.document import ComparisonReport, DiffItem, MatchItem, MissingItem, Citation


_SPLIT_RE = re.compile(r"[\\n\\r]+|(?<=[\\.!\\?])\\s+")


def _norm(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"\\s+", " ", s)
    s = re.sub(r"[^a-z0-9 %\\-_/\\.]+", "", s)
    return s


def _token_set(s: str) -> set[str]:
    return {t for t in re.split(r"\\W+", _norm(s)) if t and len(t) > 2}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)

def _numbers(s: str) -> list[str]:
    return re.findall(r"\\b\\d+(?:\\.\\d+)?%?\\b", s)


@dataclass(frozen=True)
class _Chunk:
    chunk_id: str
    document: str
    version: str
    section: str
    page: int
    content: str

    @property
    def source_label(self) -> str:
        return f"{self.document} ({self.version}) | {self.section} | page {self.page}"


def _chunks_by_doc(retrieved_chunks: list[dict]) -> dict[str, list[_Chunk]]:
    out: dict[str, list[_Chunk]] = {}
    for hit in retrieved_chunks:
        meta = hit.get("metadata", {}) or {}
        doc = str(meta.get("document") or "")
        version = str(meta.get("version") or "")
        section = str(meta.get("section") or "")
        page = int(meta.get("page") or 0)
        chunk_id = str(meta.get("chunk_id") or hit.get("chunk_id") or "")
        content = str(meta.get("content") or "")
        if not doc or not chunk_id or not content:
            continue
        out.setdefault(doc, []).append(_Chunk(chunk_id=chunk_id, document=doc, version=version, section=section, page=page, content=content))
    return out


def _sentences(chunk: _Chunk, limit: int = 25) -> list[str]:
    parts = [p.strip() for p in _SPLIT_RE.split(chunk.content) if p.strip()]
    # Keep only meaningful lines
    parts = [p for p in parts if len(p) >= 40][:limit]
    return parts


def deterministic_compare(retrieved_chunks: list[dict]) -> ComparisonReport:
    """
    LLM-free fallback: approximate MATCH/DIFF/MISSING from retrieved chunk text.
    Still produces citations via the chunk metadata.
    """
    by_doc = _chunks_by_doc(retrieved_chunks)
    docs = list(by_doc.keys())
    if len(docs) < 2:
        return ComparisonReport(missing=[], diff=[], match=[])

    doc_a, doc_b = docs[0], docs[1]
    chunks_a = by_doc[doc_a]
    chunks_b = by_doc[doc_b]

    # 1) Chunk-level alignment by section name (best signal we have without an LLM)
    match: list[MatchItem] = []
    diff: list[DiffItem] = []
    missing: list[MissingItem] = []

    sec_a = {c.section: c for c in chunks_a if c.section}
    sec_b = {c.section: c for c in chunks_b if c.section}
    common_sections = [s for s in sec_a.keys() if s in sec_b]

    for s in common_sections[:8]:
        ca, cb = sec_a[s], sec_b[s]
        ta = _token_set(ca.content[:4000])
        tb = _token_set(cb.content[:4000])
        sim = _jaccard(ta, tb)
        if sim >= 0.88:
            a0 = _sentences(ca, limit=1)
            b0 = _sentences(cb, limit=1)
            match.append(
                MatchItem(
                    textA=(a0[0] if a0 else ca.content[:200]),
                    textB=(b0[0] if b0 else cb.content[:200]),
                    source=f"{ca.source_label} + {cb.source_label}",
                )
            )
        elif sim >= 0.30:
            a0 = _sentences(ca, limit=1)
            b0 = _sentences(cb, limit=1)
            diff.append(
                DiffItem(
                    docA_text=(a0[0] if a0 else ca.content[:260]),
                    docB_text=(b0[0] if b0 else cb.content[:260]),
                    reason=f"Same section '{s}' but content changed (similarity={sim:.2f}, deterministic fallback).",
                    sourceA=ca.source_label,
                    sourceB=cb.source_label,
                )
            )

    sent_a: list[tuple[str, _Chunk]] = [(s, c) for c in chunks_a for s in _sentences(c, limit=60)]
    sent_b: list[tuple[str, _Chunk]] = [(s, c) for c in chunks_b for s in _sentences(c, limit=60)]

    # Pairwise best-match alignment (A -> B)
    b_items = [(_token_set(s), s, c) for s, c in sent_b]
    used_b: set[int] = set()

    MATCH_T = 0.90
    DIFF_T = 0.25

    for s_a, c_a in sent_a[:160]:
        ta = _token_set(s_a)
        best_score = 0.0
        best_idx: int | None = None
        best_s_b: str | None = None
        best_c_b: _Chunk | None = None

        for idx, (tb, s_b, c_b) in enumerate(b_items):
            if idx in used_b:
                continue
            score = _jaccard(ta, tb)
            if score > best_score:
                best_score, best_idx, best_s_b, best_c_b = score, idx, s_b, c_b

        if best_idx is None or best_s_b is None or best_c_b is None:
            continue

        # Classify by similarity threshold
        nums_a = _numbers(s_a)
        nums_b = _numbers(best_s_b)

        if best_score >= MATCH_T and _norm(s_a) == _norm(best_s_b):
            used_b.add(best_idx)
            match.append(
                MatchItem(
                    textA=s_a,
                    textB=best_s_b,
                    source=f"{c_a.source_label} + {best_c_b.source_label}",
                )
            )
        elif best_score >= DIFF_T and nums_a and nums_b and nums_a != nums_b:
            used_b.add(best_idx)
            diff.append(
                DiffItem(
                    docA_text=s_a,
                    docB_text=best_s_b,
                    reason=f"Similar content but numeric/value change ({nums_a} → {nums_b}, similarity={best_score:.2f}, deterministic fallback).",
                    sourceA=c_a.source_label,
                    sourceB=best_c_b.source_label,
                )
            )
        elif best_score >= DIFF_T:
            used_b.add(best_idx)
            diff.append(
                DiffItem(
                    docA_text=s_a,
                    docB_text=best_s_b,
                    reason=f"Similar topic but changed (similarity={best_score:.2f}, deterministic fallback).",
                    sourceA=c_a.source_label,
                    sourceB=best_c_b.source_label,
                )
            )
        else:
            missing.append(MissingItem(text=s_a, source_file=c_a.document, location=c_a.source_label))

        if len(match) >= 8 and len(diff) >= 8 and len(missing) >= 8:
            break

    # Anything in B that never matched A becomes missing-on-A
    if len(missing) < 12:
        for idx, (_tb, s_b, c_b) in enumerate(b_items):
            if idx in used_b:
                continue
            missing.append(MissingItem(text=s_b, source_file=c_b.document, location=c_b.source_label))
            if len(missing) >= 12:
                break

    # If we still couldn't produce DIFF rows, emit a few best-effort diffs from chunk pairs.
    if not diff:
        scored: list[tuple[float, _Chunk, _Chunk]] = []
        for ca in chunks_a[:10]:
            ta = _token_set(ca.content[:4000])
            for cb in chunks_b[:10]:
                tb = _token_set(cb.content[:4000])
                scored.append((_jaccard(ta, tb), ca, cb))
        scored.sort(key=lambda x: x[0], reverse=True)
        for sim, ca, cb in scored[:3]:
            a0 = _sentences(ca, limit=1)
            b0 = _sentences(cb, limit=1)
            diff.append(
                DiffItem(
                    docA_text=(a0[0] if a0 else ca.content[:260]),
                    docB_text=(b0[0] if b0 else cb.content[:260]),
                    reason=f"Best-effort diff between top retrieved sections (similarity={sim:.2f}, deterministic fallback).",
                    sourceA=ca.source_label,
                    sourceB=cb.source_label,
                )
            )

    return ComparisonReport(
        missing=missing[:12],
        diff=diff[:12],
        match=match[:12],
    )


def deterministic_answer(question: str, retrieved_chunks: list[dict]) -> tuple[str, list[Citation]]:
    by_doc = _chunks_by_doc(retrieved_chunks)
    chunks: list[_Chunk] = [c for cs in by_doc.values() for c in cs]
    q_terms = _token_set(question)

    def score(chunk: _Chunk) -> float:
        terms = _token_set(chunk.content[:2000])
        return _jaccard(q_terms, terms)

    chunks.sort(key=score, reverse=True)
    top = chunks[:2]
    if not top:
        return "I don't have enough information in the retrieved documents to answer this reliably.", []

    snippets: list[str] = []
    citations: list[Citation] = []
    for c in top:
        sents = _sentences(c, limit=6)
        if sents:
            snippets.append(f"- {sents[0]}")
        citations.append(
            Citation(
                document_name=c.document,
                version=c.version,
                page_number=c.page,
                section=c.section,
                chunk_id=c.chunk_id,
                confidence=0.45,
                quoted_snippet=(sents[0] if sents else c.content[:200]),
            )
        )

    answer = "Based on the retrieved sections, here are the most relevant excerpts:\n" + "\n".join(snippets)
    return answer, citations


def deterministic_executive_summary(report: ComparisonReport) -> dict:
    changes = []
    rank = 1
    for d in report.diff[:7]:
        changes.append(
            {
                "rank": rank,
                "title": "Changed content",
                "description": d.reason,
                "severity": "medium",
                "ranking_rationale": "Deterministic fallback: ranked by retrieval order and similarity strength.",
            }
        )
        rank += 1
    for m in report.missing[: max(0, 10 - len(changes))]:
        changes.append(
            {
                "rank": rank,
                "title": "Added/Removed content",
                "description": m.text[:160],
                "severity": "low",
                "ranking_rationale": "Deterministic fallback: content appears only in one document.",
            }
        )
        rank += 1

    return {
        "top_important_changes": changes,
        "business_impact": "Deterministic fallback: unable to assess business impact without LLM reasoning.",
        "architecture_impact": "Deterministic fallback: unable to assess architecture impact without LLM reasoning.",
        "workflow_impact": "Deterministic fallback: unable to assess workflow impact without LLM reasoning.",
    }

