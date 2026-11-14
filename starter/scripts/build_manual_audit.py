"""Build auditable manual-review tables from fixed source locations and traces."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.chunking import by_paragraph, fixed_size
from src.ingestion import load_pdf

PDF = ROOT / "data" / "NIST.SP.800-63b-4.pdf"
TRACE_FILE = ROOT / "results" / "traces.jsonl"
QUESTIONS_FILE = ROOT / "benchmark" / "questions.json"
OUTPUT = ROOT / "results" / "manual_audit.json"
DOCUMENT_ID = "nist-sp-800-63b-4"
SOURCE = "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-63b-4.pdf"

COHERENCE_SCORES = {
    "A": {12: 1, 13: 1, 14: 1, 15: 1, 16: 1, 17: 1, 18: 1, 19: 1, 20: 1, 21: 1},
    "B": {12: 2, 13: 1, 14: 2, 15: 1, 16: 1, 17: 1, 18: 1, 19: 1, 20: 1, 21: 1},
    "C": {12: 2, 13: 1, 14: 2, 15: 1, 16: 1, 17: 1, 18: 1, 19: 1, 20: 1, 21: 1},
}
COHERENCE_REASONS = {
    "A": {
        12: "The definition is readable, but the chunk ends with a dangling 'The'.",
        13: "The summary begins mid-page and ends mid-clause after 'the'.",
        14: "The notations and structure remain recognizable, but the final list item is cut.",
        15: "The normative AAL context is clear; the last sentence is cut before its explanation.",
        16: "The AAL1 list is understandable but ends in the middle of a bullet.",
        17: "The AAL1 timeout and AAL2 heading are readable, but the next clause is cut.",
        18: "The biometric paragraph is coherent; the following heading is truncated.",
        19: "The AAL3 description is clear, but the authenticator-combination list is incomplete.",
        20: "A PDF continuation fragment appears at the start and the final AAL3 clause is cut.",
        21: "The privacy requirements begin mid-page and end inside a numbered requirement.",
    },
    "B": {
        12: "Heading and definition form a complete, self-contained passage.",
        13: "The summary starts mid-page and ends in a partial possession statement.",
        14: "The terminology and section map are understandable; the section map is complete.",
        15: "The AAL context is coherent, but a sentence continues beyond the chunk boundary.",
        16: "Most of the AAL1 list is readable, but the final bullet is incomplete.",
        17: "The requirements are clear until the next permitted-types clause is truncated.",
        18: "The biometric explanation is complete; the following AAL2 requirements are cut.",
        19: "The AAL3 requirements are understandable, but the combination list is incomplete.",
        20: "The AAL3 timeout passage is clear; the general-controls passage is cut.",
        21: "The privacy context is readable, but a numbered requirement continues beyond it.",
    },
    "C": {
        12: "Same paragraph-aware chunk as B; heading and definition form a complete passage.",
        13: "Same paragraph-aware chunk as B; it begins mid-page and ends mid-clause.",
        14: "Same paragraph-aware chunk as B; the terminology and section map are complete.",
        15: "Same paragraph-aware chunk as B; a sentence continues beyond the boundary.",
        16: "Same paragraph-aware chunk as B; the final AAL1 list item is incomplete.",
        17: "Same paragraph-aware chunk as B; the next permitted-types clause is truncated.",
        18: "Same paragraph-aware chunk as B; the following AAL2 requirements are cut.",
        19: "Same paragraph-aware chunk as B; the combination list is incomplete.",
        20: "Same paragraph-aware chunk as B; the general-controls passage is cut.",
        21: "Same paragraph-aware chunk as B; a numbered requirement continues beyond it.",
    },
}
GROUNDING = {
    "A": {
        "q16": (2, "Top-3 contains the requested one-in-10,000 FMR threshold."),
        "q17": (2, "Top-3 contains the independent-notification requirement for a new binding."),
        "q18": (2, "Top-3 contains all three recommended responses to detected session fraud."),
        "q19": (2, "Top-3 contains the requested prompt to act before the inactivity timeout."),
        "q20": (2, "Top-3 contains the required AAL3 biometric comparison and collection context."),
    },
    "B": {
        "q16": (1, "Top-3 discusses biometric error rates but misses the requested FMR threshold."),
        "q17": (2, "Top-3 contains the independent-notification requirement for a new binding."),
        "q18": (2, "Top-3 contains all three recommended responses to detected session fraud."),
        "q19": (1, "Top-3 retrieves timeout definitions, but not the requested user prompt."),
        "q20": (2, "Top-3 contains the required AAL3 biometric comparison and collection context."),
    },
    "C": {
        "q16": (1, "Filtered top-3 discusses FMR but misses the requested one-in-10,000 threshold."),
        "q17": (2, "Top-3 contains the independent-notification requirement for a new binding."),
        "q18": (2, "Top-3 contains all three recommended responses to detected session fraud."),
        "q19": (2, "Filtered top-3 contains the requested prompt before an inactivity timeout."),
        "q20": (2, "Top-3 contains the required AAL3 biometric comparison and collection context."),
    },
}


def main() -> None:
    pages = load_pdf(PDF, DOCUMENT_ID, SOURCE)
    sample_pages = [page for page in pages if 12 <= page.page <= 21]
    if len(sample_pages) != 10:
        raise RuntimeError(f"Expected 10 coherence pages, found {len(sample_pages)}")
    coherence_rows = []
    for page in sample_pages:
        chunk_sets = {
            "A": fixed_size(page, size=700, overlap=100),
            "B": by_paragraph(page, max_size=900),
            "C": by_paragraph(page, max_size=900),
        }
        for strategy, chunks in chunk_sets.items():
            chunk = chunks[0]
            coherence_rows.append(
                {
                    "strategy": strategy,
                    "source_page_physical": page.page,
                    "sample_location": "first content chunk on the page",
                    "chunk_id": chunk.chunk_id,
                    "chunk_text": chunk.text,
                    "score_0_to_2": COHERENCE_SCORES[strategy][page.page],
                    "reason": COHERENCE_REASONS[strategy][page.page],
                }
            )

    questions = {
        row["id"]: row
        for row in json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
        if row["split"] == "test"
    }
    traces = [
        json.loads(line)
        for line in TRACE_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    grounding_rows = []
    for trace in traces:
        if trace["split"] != "test":
            continue
        score, reason = GROUNDING[trace["strategy"]][trace["question_id"]]
        grounding_rows.append(
            {
                "strategy": trace["strategy"],
                "question_id": trace["question_id"],
                "question": questions[trace["question_id"]]["question"],
                "score_0_to_2": score,
                "reason": reason,
                "evidence_hit3_automatic": trace["evidence_hit3"],
                "trace_ranks": [
                    {"rank": rank, "chunk_id": hit["chunk_id"], "page": hit["page"]}
                    for rank, hit in enumerate(trace["hits"], start=1)
                ],
            }
        )

    coherence_summary = {
        strategy: {
            "count": sum(row["strategy"] == strategy for row in coherence_rows),
            "mean": round(
                sum(
                    row["score_0_to_2"]
                    for row in coherence_rows
                    if row["strategy"] == strategy
                )
                / 10,
                2,
            ),
        }
        for strategy in ("A", "B", "C")
    }
    grounding_summary = {}
    for strategy in ("A", "B", "C"):
        scores = [
            row["score_0_to_2"]
            for row in grounding_rows
            if row["strategy"] == strategy
        ]
        grounding_summary[strategy] = {
            "count": len(scores),
            "score_0": scores.count(0),
            "score_1": scores.count(1),
            "score_2": scores.count(2),
            "mean": round(sum(scores) / len(scores), 2),
        }
    result = {
        "auditor": (
            "AI-assisted review of the actual chunks and source evidence; labels are "
            "not an independent blind human annotation and should be confirmed by the student."
        ),
        "rubric": {
            "coherence": "0=cut/unclear; 1=partly understandable or missing context; 2=self-contained.",
            "grounding": "0=no useful support; 1=partial support; 2=sufficient evidence and context.",
        },
        "coherence_sample_rule": (
            "First content chunk on each of physical pages 12-21, chosen before scoring; "
            "same page-start location for A/B/C. Full chunk text is included."
        ),
        "coherence_summary": coherence_summary,
        "coherence_rows": coherence_rows,
        "grounding_summary": grounding_summary,
        "grounding_rows": grounding_rows,
        "metadata_audit": "metadata_audit.json",
        "retrieval_trace": "traces.jsonl",
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"coherence": coherence_summary, "grounding": grounding_summary}, indent=2))


if __name__ == "__main__":
    main()
