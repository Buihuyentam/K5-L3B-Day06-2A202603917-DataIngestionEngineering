"""Reproducible, staged A/B/C retrieval experiment."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import time

from dotenv import load_dotenv

from .chunking import by_paragraph, fixed_size
from .embeddings import MyEmbedder
from .evaluation import _match_text, evaluate_query, summarize
from .ingestion import load_pdf
from .store import PgVectorStore

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RESULTS = ROOT / "results"
BENCHMARK = ROOT / "benchmark" / "questions.json"
PDF = DATA / "NIST.SP.800-63b-4.pdf"
DOCUMENT_ID = "nist-sp-800-63b-4"
SOURCE_URL = "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-63b-4.pdf"
FIRST_CONTENT_PAGE = 12
LAST_CONTENT_PAGE = 109
MODEL_DEFAULT = "sentence-transformers/all-MiniLM-L6-v2"
STRATEGIES = {"A": "fixed", "B": "paragraph", "C": "paragraph+filter"}


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _pages_and_manifest():
    pages = load_pdf(PDF, DOCUMENT_ID, SOURCE_URL)
    included = [page for page in pages if FIRST_CONTENT_PAGE <= page.page <= LAST_CONTENT_PAGE]
    useful = [page for page in included if page.text and len(page.text) >= 200]
    if len(useful) < 30:
        raise RuntimeError(f"Only {len(useful)} useful content pages were extracted; need at least 30")
    issues = [
        {
            "page": page.page,
            "status": page.metadata.get("extraction_status"),
            "error": page.metadata.get("extraction_error"),
            "replacement_characters": page.metadata.get("replacement_characters", 0),
        }
        for page in included
        if page.metadata.get("extraction_status") != "ok"
        or page.metadata.get("replacement_characters", 0)
    ]
    manifest = {
        "source_id": DOCUMENT_ID,
        "title": "Digital Identity Guidelines: Authentication and Authenticator Management",
        "version": "NIST SP 800-63B-4, final, July 2025",
        "source_path_or_url": SOURCE_URL,
        "permission": (
            "The PDF's p. 3 states that nongovernmental organizations may use this "
            "publication voluntarily and that it is not subject to U.S. copyright. "
            "NIST's technical-series policy provides worldwide reprint rights for "
            "NIST-employee-authored works."
        ),
        "permission_source": "https://www.nist.gov/open/copyright-fair-use-and-licensing-statements-srd-data-software-and-technical-series-publications",
        "rights_caveat": (
            "NIST notes that some technical-series publications contain third-party "
            "authorship and may be subject to copyright. This publication lists contractor "
            "coauthors; confirm applicable jurisdiction and reuse terms before reuse beyond "
            "this educational experiment. Attribution is provided; this is not legal advice."
        ),
        "publication_record": "https://csrc.nist.gov/pubs/sp/800/63/b/4/final",
        "accessed_at": "2026-11-14",
        "sha256": hashlib.sha256(PDF.read_bytes()).hexdigest(),
        "pdf_physical_page_count": len(pages),
        "content_page_rule": (
            "Only physical PDF pages 12-109 inclusive: main text and normative/informative "
            "Appendices A-B. Excludes cover/front matter, contents, acronym list, glossary, "
            "change log, and reference pages. Counts pages with >=200 extracted characters."
        ),
        "included_physical_pages": [page.page for page in useful],
        "content_page_count": len(useful),
        "page_character_counts": {str(page.page): len(page.text) for page in useful},
        "empty_pages": [page.page for page in included if not page.text],
        "failed_pages": [
            {"page": page.page, "error": page.metadata.get("extraction_error")}
            for page in included
            if page.metadata.get("extraction_status") == "failed"
        ],
        "extraction_warnings": [
            {"page": page.page, "replacement_characters": page.metadata["replacement_characters"]}
            for page in included
            if page.metadata.get("replacement_characters", 0)
        ],
        "extractor": "pypdf",
    }
    _write_json(DATA / "manifest.json", manifest)
    _write_json(
        RESULTS / "ingestion_report.json",
        {
            "pdf_physical_pages": len(pages),
            "included_content_pages": len(useful),
            "included_page_range": [FIRST_CONTENT_PAGE, LAST_CONTENT_PAGE],
            "empty_pages": manifest["empty_pages"],
            "failed_pages": manifest["failed_pages"],
            "extraction_warnings": manifest["extraction_warnings"],
        },
    )
    return useful, manifest


def _validate_questions(questions, pages):
    page_text = {page.page: _match_text(page.text) for page in pages}
    if len(questions) < 20:
        raise ValueError(f"Benchmark has {len(questions)} questions; at least 20 are required")
    splits = {split: sum(q["split"] == split for q in questions) for split in ("dev", "test")}
    if splits != {"dev": 15, "test": 5}:
        raise ValueError(f"Expected a fixed 15/5 split, got {splits}")
    filter_questions = [question for question in questions if question.get("filter")]
    if len(filter_questions) < 3 or not any(q["split"] == "test" for q in filter_questions):
        raise ValueError("Benchmark needs at least 3 metadata-filter questions, including a test question")
    for question in questions:
        if question["gold_source_id"] != DOCUMENT_ID:
            raise ValueError(f"{question['id']} refers to an unexpected source")
        quote = _match_text(question["evidence_quote"])
        if quote not in page_text.get(question["gold_page"], ""):
            raise ValueError(
                f"Evidence for {question['id']} is not present on physical page {question['gold_page']}"
            )
        filters = question.get("filter") or {}
        if filters and filters.get("section") != next(
            page.metadata["section"] for page in pages if page.page == question["gold_page"]
        ):
            raise ValueError(f"Filter metadata for {question['id']} disagrees with source page")
    return splits


def _make_chunks(pages):
    return {
        "A": [chunk for page in pages for chunk in fixed_size(page, size=700, overlap=100)],
        "B": [chunk for page in pages for chunk in by_paragraph(page, max_size=900)],
    }


def _load_existing_traces(path: Path):
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one stage of the fixed A/B/C experiment.")
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    selected_split = args.split
    if selected_split == "test":
        selection_path = RESULTS / "selection.json"
        if not selection_path.exists():
            raise RuntimeError(
                "Test is locked until dev selection is recorded in results/selection.json"
            )
        selection = _read_json(selection_path)
        if selection.get("strategy") not in STRATEGIES or not selection.get("rationale"):
            raise ValueError("selection.json must record strategy A/B/C and a rationale")
        benchmark_hash = hashlib.sha256(BENCHMARK.read_bytes()).hexdigest()
        if selection.get("benchmark_sha256") != benchmark_hash:
            raise ValueError("selection.json does not match the current benchmark version")
        dev_traces = [
            row for row in _load_existing_traces(RESULTS / "traces.jsonl")
            if row.get("split") == "dev"
        ]
        if selection.get("dev_metrics") != summarize(dev_traces):
            raise ValueError("selection.json does not match the current dev retrieval results")

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is missing; configure it in starter/.env")
    model_name = os.getenv("EMBEDDING_MODEL", MODEL_DEFAULT)
    pages, manifest = _pages_and_manifest()
    questions = _read_json(BENCHMARK)
    split_counts = _validate_questions(questions, pages)
    embedder = MyEmbedder(model_name)

    document_probe = embedder.embed_documents(["dimension verification probe"])
    query_probe = embedder.embed_query("query compatibility verification probe")
    if len(document_probe[0]) != len(query_probe) or len(query_probe) != embedder.dimensions:
        raise RuntimeError("Embedding document/query dimensions are incompatible")

    store = PgVectorStore(database_url, embedder.dimensions)
    store.create_schema()
    db_info = store.server_info()
    chunk_sets = _make_chunks(pages)
    chunk_sets["C"] = chunk_sets["B"]
    vector_cache: dict[str, list[float]] = {}
    strategy_runs = {}

    for strategy, chunks in chunk_sets.items():
        start = time.perf_counter()
        missing = [chunk for chunk in chunks if chunk.chunk_id not in vector_cache]
        embedding_start = time.perf_counter()
        new_vectors = embedder.embed_documents([chunk.text for chunk in missing])
        embedding_seconds = time.perf_counter() - embedding_start
        vector_cache.update(
            (chunk.chunk_id, vector) for chunk, vector in zip(missing, new_vectors)
        )
        vectors = [vector_cache[chunk.chunk_id] for chunk in chunks]

        before = store.count(strategy)
        store.upsert(strategy, chunks, vectors)
        after_first = store.count(strategy)
        store.upsert(strategy, chunks, vectors)
        after_repeat = store.count(strategy)
        if after_first != len(chunks) or after_repeat != len(chunks):
            raise RuntimeError(
                f"{strategy} store count mismatch: expected {len(chunks)}, "
                f"got {after_first} then {after_repeat}"
            )
        strategy_runs[strategy] = {
            "chunk_count": len(chunks),
            "chunk_chars": sum(len(chunk.text) for chunk in chunks),
            "mean_chunk_chars": round(
                sum(len(chunk.text) for chunk in chunks) / len(chunks), 2
            ),
            "embedding_seconds": round(embedding_seconds, 3),
            "ingest_and_index_seconds": round(time.perf_counter() - start, 3),
            "embedding_cost_usd": 0.0,
            "records_before": before,
            "records_after_first_upsert": after_first,
            "records_after_repeat_upsert": after_repeat,
            "idempotent_reingest": after_first == after_repeat == len(chunks),
            "embedding_vectors_reused": len(chunks) - len(missing),
        }

    query_cache: dict[str, list[float]] = {}
    stage_traces = []
    for question in questions:
        if question["split"] != selected_split:
            continue
        query_vector = query_cache.setdefault(
            question["question"], embedder.embed_query(question["question"])
        )
        for strategy in STRATEGIES:
            filters = question.get("filter") if strategy == "C" else None
            hits = store.search(strategy, query_vector, top_k=3, filters=filters)
            trace = evaluate_query(question, hits)
            trace["strategy"] = strategy
            stage_traces.append(trace)

    trace_path = RESULTS / "traces.jsonl"
    previous = [
        row for row in _load_existing_traces(trace_path)
        if row.get("split") != selected_split
    ]
    all_traces = previous + stage_traces
    trace_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in all_traces),
        encoding="utf-8",
    )
    _write_json(RESULTS / "metrics.json", summarize(all_traces))
    run_metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "split_run": selected_split,
        "benchmark_split_counts": split_counts,
        "source_sha256": manifest["sha256"],
        "source_content_pages": manifest["content_page_count"],
        "model": model_name,
        "dimensions": embedder.dimensions,
        "document_probe_dimensions": len(document_probe[0]),
        "query_probe_dimensions": len(query_probe),
        "query_document_encoder": "same MiniLM encoder and mean pooling; no query prefix",
        "embedding_cost_usd": 0.0,
        "vector_store": "PostgreSQL + pgvector, exact cosine distance (<=>)",
        **db_info,
        "python": platform.python_version(),
        "strategies": {
            key: {"chunking": value, **strategy_runs[key]}
            for key, value in STRATEGIES.items()
        },
        "trace_file": "results/traces.jsonl",
        "selected_strategy_before_test": (
            _read_json(RESULTS / "selection.json").get("strategy")
            if selected_split == "test"
            else None
        ),
    }
    _write_json(RESULTS / "run_metadata.json", run_metadata)
    print(json.dumps({"split": selected_split, "metrics": summarize(all_traces)}, indent=2))


if __name__ == "__main__":
    main()
