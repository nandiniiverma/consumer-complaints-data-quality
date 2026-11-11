# Python code guide

For each file: **purpose**, **how it touches the database**, **how to run it**.
Every runnable file adds the project root to `sys.path`, so both
`python src/ingest.py` and `python -m src.ingest` work from the project root.

## src/config.py - settings
* **Purpose:** the single place for paths (`pathlib.Path`, so Windows-safe), the 18 database
  column names, which columns are MANDATORY vs OPTIONAL, the earliest valid date, chunk size.
* **Database:** none.
* **Run:** not run directly; imported by everything else.

## src/db_utils.py - shared helpers
* **Purpose:** `connect()` (optionally read-only - the dashboard uses this),
  `parse_sql_blocks()` (splits a `.sql` file into queries tagged `-- @id:`),
  `run_query_blocks()` (runs them all and returns DataFrames), `create_run()` / `finish_run()`
  (the `pipeline_runs` audit row).
* **Database:** opens connections and executes whatever SQL it is given.
* **Why the tag format:** keeping SQL in `.sql` files (not buried in Python strings) means you can
  paste any query into DB Browser and read it like normal SQL, while Python still knows each
  rule's id, name, severity and threshold.

## src/ingest.py - Stage 1
* **Purpose:** inspect the header, create the database, load the CSV into `complaints_raw` in chunks,
  load the two reference tables, verify the row count, write `ingestion_log`.
* **Key decisions:** `dtype=str` and `keep_default_na=False` so nothing is converted (IDs, ZIPs and
  dates stay exactly as written; "N/A" stays text); only an empty field becomes NULL.
  Required columns are checked; a missing one stops the run with a clear message.
* **Database:** runs `sql/schema.sql` (drops and recreates `complaints_raw` and reference tables),
  bulk-inserts with `executemany`, then runs `sql/indexes.sql`. Audit tables are kept.
* **Run:** `python src/ingest.py --csv data/raw/complaints_sample.csv [--inspect] [--chunk-size N] [--include-narrative]`
* **Expect:** `chunk 1: ... rows loaded so far` lines, then `Done: N rows loaded ... (verified with COUNT(*))`.

## src/profile_data.py - Stage 2
* **Purpose:** run `sql/profiling.sql` (9 discovery queries) and export each to `reports/profiling/*.csv`.
* **Database:** read-only SELECTs.
* **Run:** `python src/profile_data.py` -> prints each result table.

## src/validate_data.py - Stage 3
* **Purpose:** load the 23 rules from `sql/validation.sql`, run each, count failing records, convert to a
  percentage of all records, compare to the rule's threshold, keep up to 5 sample failing records.
* **Status logic:** `PASS` if failing % <= threshold, `FAIL` otherwise, `ERROR` if the SQL itself fails
  (an ERROR is never counted as a pass). An empty table is refused rather than "passing" everything.
* **Database:** each rule is wrapped as `SELECT COUNT(*) FROM (<rule sql>)` with **named parameters**
  (`:min_date`, `:today`, `:sample_limit`); results are written to `validation_results` and `validation_samples`.
* **Run:** `python src/validate_data.py` (normally called by the pipeline).

## src/analysis.py - Stage 4
* **Purpose:** run `sql/analysis.sql` (11 reporting queries) with parameters `:top_n` and `:min_complaints`
  and export to `reports/analysis/*.csv`. The dashboard re-uses the same function.
* **Database:** read-only SELECTs on the view `v_complaints` and `ref_states`.
* **Run:** `python src/analysis.py [--top-n 10] [--min-complaints 100]`

## src/generate_report.py - Stage 5 (reports)
* **Purpose:** read a stored run and write `validation_results.csv`, `validation_failure_samples.csv`,
  `data_quality_summary.md`, and `readme_results_snippet.md` (a paste-ready results section).
* **Database:** read-only. Every figure is read from the database; none is typed in.
* **Run:** `python src/generate_report.py [--run-id N]`

## src/run_pipeline.py - Stage 5 (orchestration)
* **Purpose:** the one-command runner: ingest -> profile -> validate -> analyse -> report. Times every
  stage, records the actual row count and rule totals in `pipeline_runs`, catches errors, prints a summary.
* **Exit codes:** 0 success, 1 pipeline error, 2 (only with `--strict`) when any rule did not pass.
* **Run:** `python src/run_pipeline.py --csv data/raw/complaints_sample.csv`

## dashboard/app.py - Stage 6
* **Purpose:** Streamlit dashboard: KPIs, validation table, missing values, trend, product, company, issue explanations.
* **Database:** opened **read-only**; results cached per database file version. Shows a warning banner when the run is labelled synthetic.
* **Run:** `streamlit run dashboard/app.py`

## tests/
* `synthetic_data.py` builds the synthetic CSVs and the table of expected defect counts.
* `test_ingest.py`, `test_validation.py`, `test_reports.py` - 55 tests; run with `pytest -q`.
* Tests use temporary databases and never touch `database/complaints.db`.
