# Test-set revision history

The initial 15/5 set was fixed before the first run. After selecting C from the initial dev metrics, the first test results were opened. Review showed paragraph-aware chunking could isolate a heading from its following oversized paragraph. The full pilot evidence is retained in `results/pilot_v1/`.

The chunker was corrected and unit-tested. To avoid reporting the already-seen five test questions as a holdout, they were replaced by five evidence-verified questions on different physical pages (43, 55, 61, 68, 82) before the corrected run. The dev questions, corpus, model, and pre-registered strategy-selection rule were not changed.

Because the replacement test questions were authored after the pilot test was seen, v2 is **exploratory and not an independent holdout**. No v2 test result was used to modify code or choose a strategy. Report this limitation; do not claim independent test validation.
