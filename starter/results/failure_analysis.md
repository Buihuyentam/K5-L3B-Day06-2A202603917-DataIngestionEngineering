# Retrieval failures and interpretation

The automatic Evidence Hit@3 requires one top-3 chunk to contain the verified quote on the gold physical page. A relevant neighboring chunk, an answer split across chunks, or a semantically equivalent passage can therefore be a miss. These are retrieval-evidence misses, not LLM answer-accuracy failures.

## Corrected run: dev misses

| Strategy | Misses | Observed trace pattern |
|---|---|---|
| A | q02, q04, q07, q08, q11, q13 | q02 ranked pages 13/49/13 instead of the AAL2 requirement on page 17. q04 retrieved password-strength appendix pages 83/98 rather than the password-verifier requirement on page 25. q08 favored account-recovery pages 61-62 over physical-authenticator loss handling on page 41. q07 and q13 included topical pages but not a single chunk with the full gold quote. |
| B | q01, q04, q08 | q01 ranked pages 21/78/92 instead of page 15. q04 again favored Appendix A pages 98/101 over page 25. q08 favored recovery pages 61-62 over page 41. |
| C | q04, q08 | The section filter raised dev Evidence Hit@3 to 13/15, but did not distinguish the password-strength appendix from password-verifier requirements for q04, or section 4 account recovery from the page-41 physical-authenticator requirement for q08. |

## Corrected run: revised test v2 misses

- **B / q16 (biometric FMR):** top-3 pages were 42, 42, and 43; they discuss biometric error rates and conditions, but the chunk containing the exact one-in-10,000 threshold was not retrieved.
- **B / q19 (timeout usability prompt):** top-3 pages 16 and 67 contain timeout definitions, not the requested user prompt from page 82.
- **C / q16:** filtering to section 3 kept the top-3 on topic (pages 42-43), but did not recover the threshold-bearing chunk. This is a chunk/ranking miss despite a correct filter.
- A retrieved all five exact evidence quotes on v2, while C retrieved four and B three. The dev-selected C is therefore not a universal winner; the five v2 questions are exploratory and not an independent holdout.

## Pilot v1

The first test set was reviewed and revealed heading-only paragraph chunks. That implementation defect was fixed and regression-tested; pilot traces, metrics, selection, and test questions are retained in `pilot_v1/`. Pilot v1 is not reported as an independent test result. The revised v2 test set and reason for revision are documented in `../benchmark/test_set_history.md`.
