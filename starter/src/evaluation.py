"""Evidence-based retrieval evaluation and JSONL trace helpers."""
import re
import unicodedata
from typing import Any


def _match_text(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip().casefold()


def _is_evidence_hit(question: dict[str, Any], hit: dict[str, Any]) -> bool:
    return (
        hit.get("document_id") == question["gold_source_id"]
        and hit.get("page") == question["gold_page"]
        and _match_text(question["evidence_quote"]) in _match_text(hit.get("text", ""))
    )


def evaluate_query(
    question: dict[str, Any], hits: list[dict[str, Any]]
) -> dict[str, Any]:
    """Mark a hit only when one returned chunk contains the verified page evidence."""
    hit_flags = [_is_evidence_hit(question, hit) for hit in hits]
    return {
        "question_id": question["id"],
        "split": question["split"],
        "question": question["question"],
        "filter": question.get("filter"),
        "gold_source_id": question["gold_source_id"],
        "gold_page": question["gold_page"],
        "evidence_quote": question["evidence_quote"],
        "hit1": bool(hit_flags and hit_flags[0]),
        "evidence_hit3": any(hit_flags[:3]),
        "evidence_hit1": bool(hit_flags and hit_flags[0]),
        "hits": hits[:3],
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate Hit@1 and Evidence Hit@3 independently by strategy and split."""
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for trace in traces:
        groups.setdefault((trace["strategy"], trace["split"]), []).append(trace)
    summary: dict[str, Any] = {}
    for (strategy, split), rows in sorted(groups.items()):
        total = len(rows)
        hit1 = sum(bool(row["hit1"]) for row in rows)
        hit3 = sum(bool(row["evidence_hit3"]) for row in rows)
        summary.setdefault(strategy, {})[split] = {
            "questions": total,
            "hit1": hit1,
            "hit1_rate": hit1 / total if total else 0.0,
            "evidence_hit3": hit3,
            "evidence_hit3_rate": hit3 / total if total else 0.0,
        }
    return summary
