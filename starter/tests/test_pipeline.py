import unittest

from src.chunking import by_paragraph, fixed_size
from src.evaluation import evaluate_query, summarize
from src.ingestion import normalize_text
from src.models import DocumentPage


class PipelineUnitTests(unittest.TestCase):
    def setUp(self):
        self.page = DocumentPage(
            document_id="doc",
            source="https://example.test/doc.pdf",
            page=8,
            text="First paragraph with enough detail.\n\nSecond paragraph has more detail.",
            metadata={"section": "8. Example"},
        )

    def test_normalization_preserves_paragraphs_and_cleans_spacing(self):
        self.assertEqual(
            normalize_text("  first   line \nsecond line\n\n• item  "),
            "first line second line\n\n• item",
        )

    def test_chunkers_preserve_source_metadata_and_enforce_bounds(self):
        fixed = fixed_size(self.page, size=24, overlap=5)
        paragraphs = by_paragraph(self.page, max_size=40)
        self.assertGreater(len(fixed), 1)
        self.assertGreater(len(paragraphs), 1)
        self.assertTrue(all(len(chunk.text) <= 24 for chunk in fixed))
        self.assertTrue(all(len(chunk.text) <= 40 for chunk in paragraphs))
        for chunk in fixed + paragraphs:
            self.assertEqual(chunk.page, self.page.page)
            self.assertEqual(chunk.metadata, self.page.metadata)
            self.assertEqual(len(chunk.chunk_id), 64)

    def test_paragraph_chunker_keeps_a_heading_with_following_text(self):
        page = DocumentPage(
            document_id="doc",
            source="source",
            page=1,
            text="2. Authentication Assurance Levels\n\nThe next paragraph explains the section.",
        )
        chunks = by_paragraph(page, max_size=40)
        self.assertNotEqual(chunks[0].text, "2. Authentication Assurance Levels")
        self.assertTrue(chunks[0].text.startswith("2. Authentication Assurance Levels"))

    def test_evidence_hit_requires_matching_source_page_and_quote(self):
        question = {
            "id": "q",
            "split": "dev",
            "question": "What is required?",
            "gold_source_id": "doc",
            "gold_page": 8,
            "evidence_quote": "required evidence",
        }
        hit = {
            "document_id": "doc",
            "page": 8,
            "text": "The required evidence is stated here.",
        }
        trace = evaluate_query(question, [hit])
        self.assertTrue(trace["hit1"])
        self.assertTrue(trace["evidence_hit3"])
        self.assertFalse(evaluate_query(question, [{**hit, "page": 9}])["evidence_hit3"])
        self.assertFalse(
            evaluate_query(question, [{**hit, "text": "related but insufficient"}])[
                "evidence_hit3"
            ]
        )

    def test_summary_separates_strategy_and_split(self):
        rows = [
            {"strategy": "A", "split": "dev", "hit1": True, "evidence_hit3": True},
            {"strategy": "A", "split": "dev", "hit1": False, "evidence_hit3": True},
            {"strategy": "B", "split": "test", "hit1": False, "evidence_hit3": False},
        ]
        result = summarize(rows)
        self.assertEqual(result["A"]["dev"]["hit1"], 1)
        self.assertEqual(result["A"]["dev"]["evidence_hit3"], 2)
        self.assertEqual(result["B"]["test"]["questions"], 1)


if __name__ == "__main__":
    unittest.main()
