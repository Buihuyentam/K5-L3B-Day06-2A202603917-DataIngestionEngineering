# Pre-registered benchmark and selection protocol

**Locked before the first retrieval run:** 2026-11-14. The 20 questions and their 15/5 split are in `questions.json`; evidence is keyed to the 1-based physical PDF page, not the printed page number. The corpus, model, query set, and ranking metric stay fixed across A/B/C. After the first test was viewed, the test questions were replaced for the corrected run; see `test_set_history.md`. The selection rule and dev questions remained fixed.

## Selection using dev only

1. Compare Evidence Hit@3 as the primary measure (count out of 15).
2. Break a tie with Hit@1 (count out of 15).
3. If still tied, prefer the strategy with the higher mean manually audited coherence score across the same 10 source locations.
4. If still tied, prefer the metadata-filtered strategy only when its filter inputs are explicit in the question and all returned rows obey them; otherwise prefer lower measured ingestion/index time, then fewer chunks.
5. Record the chosen strategy and rationale in `results/selection.json` **before** running the test split. Test metrics do not affect selection.

The test set is a five-question illustrative holdout, not a basis for broad claims. Exact evidence matching is a conservative single-chunk retrieval measure; it is not answer generation or LLM accuracy. The three filters use the section names visible in the source and carried as page metadata.
