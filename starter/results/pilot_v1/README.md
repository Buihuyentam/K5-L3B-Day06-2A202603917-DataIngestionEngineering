# Pilot v1 archive — exploratory only

These are the initial results from the 15/5 benchmark before the test split was reviewed. The test results were inspected and led to a code fix: paragraph-aware chunking had emitted heading-only chunks when the next paragraph exceeded the size limit. The benchmark was therefore revised with five new test questions and the final reported test run is version 2.

Do not treat this pilot's test metrics as an independent holdout. The archive is retained to make the revision and its failures auditable.
