# Interview guide - American Express Regulatory Data Products Internship

Use this after you have run the pipeline on the **real** CFPB extract. Anything in
`[brackets]` must be filled from your own `reports/data_quality_summary.md`.
Do not quote numbers you have not generated yourself.

## 1. The 30-second version
"I built an SQL-based data quality pipeline on the public CFPB Consumer Complaint Database. Python loads a
CSV extract into SQLite untouched, SQL queries profile it and run 23 validation rules - completeness,
uniqueness, date validity, consistency and valid values - and a Python runner records PASS/FAIL against
documented thresholds, exports CSV and Markdown reports and feeds a Streamlit dashboard. I tested the
rules against a synthetic file with known injected defects, so I know each rule finds exactly what it should."

## 2. The 2-minute walkthrough
1. **Problem:** reporting is only as trustworthy as the data under it; regulatory-style reporting needs
   evidence that data was checked, and checks that can be repeated.
2. **Ingest:** everything loaded as text, so bad values are preserved rather than silently converted.
   Row counts verified (`rows_read == COUNT(*)`) and logged with a file hash.
3. **Profile:** SQL to learn the data first - counts, missing values, distributions, duplicates.
4. **Validate:** each rule is one SQL query returning failing records; Python counts them, applies a
   threshold, saves the result and sample records.
5. **Report / dashboard:** every figure read from the database.
6. **Testing:** synthetic data with injected defects and exact expected counts; a clean file where all rules pass.

## 3. Design decisions you should be able to defend
| Decision | Reason |
|---|---|
| Raw table is all TEXT | Preserves original values so validation can detect them; types are checked by SQL, not assumed |
| Separate **raw table** and **cleaned view** | Raw data is evidence; the view is for analysis. Never overwrite the source |
| Rules live in `.sql` files with metadata | Readable by analysts, version-controlled, testable independently of Python |
| Thresholds per rule | Not every defect is equal: a missing complaint ID is critical; a missing optional state may be tolerable. Thresholds are documented policy choices, not facts |
| Mandatory vs optional columns | Blank sub-product or narrative is normal; counting it as failure would drown real problems |
| `ERROR` status | A rule that cannot run must never look like a pass |
| Spelling rule uses normalisation, not a hard-coded list | Works when new products appear |
| Synthetic data kept apart, labelled | Avoids mixing test numbers with real results |

## 4. Questions you may be asked
**SQL**
* *WHERE vs HAVING?* WHERE filters rows before grouping; HAVING filters groups after aggregates (A07).
* *INNER vs LEFT JOIN?* LEFT keeps unmatched left rows; I used it to find states missing from the reference list (DQ-009, A10).
* *How did you find duplicates?* `ROW_NUMBER() OVER (PARTITION BY complaint_id ...)` and keep occurrence > 1, so only surplus copies are counted (DQ-003).
* *What is a NULL trap you hit?* `NOT (a AND b)` is NULL when `b` is NULL, so invalid dates escaped; I rewrote the date rule as separate `OR` conditions (DQ-005).
* *Why `100.0 *` in percentages?* Integer division truncates.
* *How did you validate dates?* Shape with `GLOB`, real calendar day with `date(x) = x`.

**Data quality**
* *Why not delete bad rows?* A pipeline should detect and report; deletion is a business decision and loses evidence.
* *How did you choose thresholds?* Per rule, by how harmful the defect is; they are in the SQL metadata and easy to change. [Explain any you changed after seeing real data, and why.]
* *What if the CFPB adds a new valid category?* DQ-020..023 and DQ-009 depend on reference files; failing samples should be reviewed before concluding the data is wrong.
* *Which rules failed on the real data?* [From your report.] *What would you do next?* [e.g. investigate the sample records, ask the data owner, adjust the reference list.]

**Engineering**
* *How does it scale?* Chunked loading, indexes built after load, set-based SQL. Beyond a few million rows I would move to a server database / columnar engine and schedule runs - outside this project's scope.
* *How do you know the rules are correct?* Tests compare each rule's count with defects I deliberately injected, plus a clean file where everything passes; I also mutation-tested the suite by weakening a rule and confirming tests failed.
* *Why SQLite?* Zero-install, ships with Python, enough to demonstrate relational SQL; it is not a production warehouse.

## 5. Mapping to the role
| Internship requirement | Where in the project |
|---|---|
| Data ingestion | `src/ingest.py` (CSV -> SQLite, chunked, verified, logged) |
| Data discovery | `sql/profiling.sql` |
| Data validation | `sql/validation.sql` + `src/validate_data.py` |
| Data quality | missing values, duplicates, invalid dates/values, inconsistencies |
| Reporting | `sql/analysis.sql`, `reports/` |
| Automation | `src/run_pipeline.py` (one command) |
| Documentation | README, data dictionary, SQL and code guides |
| Visualisation | Streamlit dashboard |

## 6. Say / don't say
* **Say:** "demonstrates SQL, data validation and automation skills on public data", "documented thresholds", "tested with synthetic data".
* **Don't say:** that it ensures regulatory compliance, implements data governance, or uses cloud services - it does none of these. Don't call the CFPB data "Amex data" or claim it represents all consumer complaints.
