"""Cross-check test top-3 metadata against the extracted PDF page records."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.ingestion import load_pdf

PDF = ROOT / "data" / "NIST.SP.800-63b-4.pdf"
QUESTIONS = ROOT / "benchmark" / "questions.json"
TRACES = ROOT / "results" / "traces.jsonl"
OUTPUT = ROOT / "results" / "metadata_audit.json"
DOCUMENT_ID = "nist-sp-800-63b-4"
SOURCE = "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-63b-4.pdf"


def main() -> None:
    questions = {
        row["id"]: row
        for row in json.loads(QUESTIONS.read_text(encoding="utf-8"))
        if row["split"] == "test"
    }
    pages = load_pdf(PDF, DOCUMENT_ID, SOURCE)
    page_metadata = {page.page: page.metadata for page in pages}
    traces = [
        json.loads(line)
        for line in TRACES.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    audit_rows = []
    for trace in traces:
        if trace["split"] != "test":
            continue
        question = questions[trace["question_id"]]
        for rank, hit in enumerate(trace["hits"], start=1):
            expected_page = page_metadata.get(hit["page"], {})
            source_ok = (
                hit["document_id"] == DOCUMENT_ID
                and hit["source"] == SOURCE
                and hit["metadata"].get("source_id") == DOCUMENT_ID
            )
            page_ok = hit["page"] in page_metadata and hit["page"] > 0
            section_ok = (
                page_ok
                and hit["metadata"].get("section") == expected_page.get("section")
            )
            filter_value = (question.get("filter") or {}).get("section")
            filter_ok = (
                trace["strategy"] != "C"
                or not filter_value
                or hit["metadata"].get("section") == filter_value
            )
            audit_rows.append(
                {
                    "strategy": trace["strategy"],
                    "question_id": trace["question_id"],
                    "rank": rank,
                    "chunk_id": hit["chunk_id"],
                    "source_ok": source_ok,
                    "physical_page": hit["page"],
                    "page_present": page_ok,
                    "section": hit["metadata"].get("section"),
                    "section_matches_source_page": section_ok,
                    "filter": filter_value,
                    "filter_compliant": filter_ok,
                }
            )
    result = {
        "audit_method": (
            "Compare every source_id, source URL, physical page, and section in the "
            "five-question test top-3 against pypdf-extracted source-page records."
        ),
        "records_checked": len(audit_rows),
        "metadata_correct": sum(
            row["source_ok"] and row["page_present"] and row["section_matches_source_page"]
            for row in audit_rows
        ),
        "filter_compliant_records": sum(
            row["filter_compliant"] and row["strategy"] == "C" and row["filter"] is not None
            for row in audit_rows
        ),
        "filter_records_checked": sum(
            row["strategy"] == "C" and row["filter"] is not None for row in audit_rows
        ),
        "filter_questions_compliant": {
            "A": None,
            "B": None,
            "C": sum(
                all(
                    row["filter_compliant"]
                    for row in audit_rows
                    if row["strategy"] == "C" and row["question_id"] == qid
                )
                for qid, question in questions.items()
                if question.get("filter")
            ),
        },
        "rows": audit_rows,
    }
    if result["metadata_correct"] != len(audit_rows):
        raise RuntimeError("One or more retrieved metadata rows do not match the source")
    if result["filter_compliant_records"] != result["filter_records_checked"]:
        raise RuntimeError("One or more C results violate a requested section filter")
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "metadata {}/{}; filter-compliant C questions {}/{}".format(
            result["metadata_correct"],
            result["records_checked"],
            result["filter_questions_compliant"]["C"],
            len(questions),
        )
    )


if __name__ == "__main__":
    main()
