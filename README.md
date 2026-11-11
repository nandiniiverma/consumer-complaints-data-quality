# SQL-Based Data Quality and Validation Pipeline for Consumer Financial Complaints

A beginner-friendly but industry-relevant project that loads the public **CFPB Consumer Complaint Database**
into SQLite, profiles it with SQL, runs **23 documented data quality rules**, produces CSV/Markdown reports
and shows everything in a **Streamlit dashboard** - all runnable locally on Windows with one command.

> **Scope note.** This is a portfolio project on public data. It demonstrates SQL, data validation and Python
> automation skills. It does **not** establish regulatory compliance, formal data governance, or cloud experience.

## Contents
1. [Project overview](#1-project-overview) - 2. [Business problem](#2-business-problem) - 3. [Why data quality matters](#3-why-data-quality-matters-in-financial-and-regulatory-reporting) - 4. [Dataset](#4-dataset-source-and-description) - 5. [Tech stack](#5-technology-stack) - 6. [Architecture](#6-project-architecture) - 7. [Folder structure](#7-folder-structure) - 8. [Installation](#8-installation) - 9. [Running](#9-running-the-pipeline) - 10. [SQL concepts](#10-sql-concepts-demonstrated) - 11. [Validation rules](#11-data-validation-rules) - 12. [Results](#12-actual-results-and-findings) - 13. [Screenshots](#13-dashboard-screenshots) - 14. [Limitations](#14-limitations) - 15. [Future work](#15-future-improvements) - [Data dictionary](#data-dictionary)

---

## 1. Project overview
| Stage | What happens | Code |
|---|---|---|
| 1. Ingest | CSV -> SQLite table `complaints_raw` (chunked, all text, row count verified) | `src/ingest.py` |
| 2. Profile | SQL discovery: counts, missing values, date range, distributions, duplicates | `sql/profiling.sql` |
| 3. Validate | 23 SQL rules -> failing counts -> PASS/FAIL against documented thresholds | `sql/validation.sql`, `src/validate_data.py` |
| 4. Analyse | SQL reports: products, daily trend, top companies, states, response mix, timely % | `sql/analysis.sql` |
| 5. Automate | One command runs everything, times it, exports CSV + Markdown | `src/run_pipeline.py` |
| 6. Visualise | Read-only Streamlit dashboard | `dashboard/app.py` |

## 2. Business problem
Organisations that report on customer complaints need to trust the numbers behind those reports. Raw extracts often
contain missing identifiers, duplicate records, impossible dates, inconsistent category spellings and values outside
the allowed lists. This project answers: *can we detect these problems automatically, repeatably and transparently,
and show exactly which records are affected?*

## 3. Why data quality matters in financial and regulatory reporting
* Counts of complaints by product, company or period are only meaningful if every record is present, unique and correctly dated.
* A duplicated complaint inflates a company's volume; a mis-spelled product splits one category into two; an impossible date drops a record from a trend chart.
* Reviewers and auditors need **evidence**: which checks ran, on which data, with what outcome. This pipeline records every run, the exact row count, per-rule results and sample failing records.

## 4. Dataset source and description
* **Source:** CFPB Consumer Complaint Database - https://www.consumerfinance.gov/data-research/consumer-complaints/
* One row per complaint about a consumer financial product or service that the CFPB sent to a company for response (published after the company responds or after 15 days, whichever comes first, with personal information removed).
* The full database is very large (tens of millions of rows in the "all data" download), so this project uses a **documented filtered extract**.
* **Export type:** filtered CSV extract (*Export data -> CSV -> Filtered results*). The CFPB tool limits filtered downloads to about 100,000 complaints, so the date-received range was narrowed until the extract fit under that cap. That limit, not any sampling design, is the reason for the extract size.
* **Date received:** 20 December to 31 December 2024 (as confirmed by the MIN/MAX `date_received` in `reports/profiling/`).
* **Download date:** 11 November 2026.
* **Total records ingested:** 99,350.
* **File layout:** this export has 15 columns. It does not include *Consumer complaint narrative*, *Consumer consent provided?* or *Consumer disputed?*; ingestion stores those as blank, so they show as 100 % missing and rule DQ-023 passes only because there is nothing to check. Dates are ISO 8601 timestamps such as `2024-12-23T11:23:45.000Z`.

**Download steps** (to reproduce)
1. Open the page above and click *Filter the full data set before you download*.
2. Set **Date received** to 20 Dec - 31 Dec 2024 (or any range that keeps the filtered count at or below 100,000).
3. *Export data -> CSV -> Filtered results*; save as `data/raw/complaints_sample.csv`. Do not open it in Excel.
4. Complete the log below so anyone can reproduce your run.

**Dataset log**
| Item | Value |
|---|---|
| Source | CFPB Consumer Complaint Database (filtered CSV export) |
| Download date | 2026-11-11 |
| Date-received range filter | 2024-12-20 to 2024-12-31 |
| Other filters | none |
| Records ingested | 99,350 (the pipeline's actual count; re-check in `reports/data_quality_summary.md`) |
| File name / size | `complaints_sample.csv`, `[size in MB - fill in]` |
| File SHA-256 | `[from table ingestion_log - fill in]` |

The raw CSV and the database are **git-ignored** (see `.gitignore`) - never commit them.

## 5. Technology stack
Python 3.10+, SQLite (bundled with Python), SQL, Pandas, NumPy (installed as a Pandas dependency), Plotly, Streamlit, pytest, Git/GitHub.
No paid services, no cloud, no APIs.

## 6. Project architecture
```
CFPB CSV (data/raw/)
   | ingest.py  (Pandas, chunked, dtype=str)
   v
SQLite database/complaints.db
   complaints_raw   <- 18 TEXT columns + row_id (+ 2 *_original date columns)
   v_complaints     <- cleaned VIEW (trimmed text, invalid dates -> NULL)
   ref_states, ref_valid_values   <- reference data (data/reference/*.csv)
   |
   +-- profiling.sql  --> reports/profiling/*.csv
   +-- validation.sql --> validation_results, validation_samples
   +-- analysis.sql   --> reports/analysis/*.csv
   |
   +-- pipeline_runs, ingestion_log   <- audit trail (row counts, timings, file hash)
   v
reports/*.csv, *.md   and   dashboard/app.py (read-only)
```
Key design choices: raw data kept as text; the only transformation is that real ISO timestamps (`2024-12-23T11:23:45.000Z`) and MM/DD/YYYY or MM/DD/YY dates are rewritten to a plain ISO date (YYYY-MM-DD) at ingestion, with the exact original text kept in `date_received_original` / `date_sent_to_company_original`, and impossible dates left as written so the rules still flag them (the date in a timestamp is taken as written, with no time-zone conversion and the time of day dropped; for slash dates the order is assumed to be US, month first); rules are plain SQL files readable by analysts;
each rule has an ID, severity, threshold and explanation; every run is logged; synthetic test data is strictly separate.

## 7. Folder structure
```
consumer-complaints-data-quality/
├── data/
│   ├── raw/                 # put the CFPB CSV here (git-ignored)
│   ├── processed/           # (reserved, git-ignored)
│   └── reference/           # us_states.csv, valid_categories.csv (committed)
├── database/                # complaints.db is created here (git-ignored)
├── sql/                     # schema.sql, indexes.sql, profiling.sql, validation.sql, analysis.sql
├── src/                     # config, db_utils, ingest, profile_data, validate_data, analysis,
│                            #   generate_report, run_pipeline
├── dashboard/app.py
├── reports/                 # generated CSV / Markdown
├── tests/                   # pytest suite + SYNTHETIC test data (clearly labelled)
├── docs/                    # SQL guide, code guide, setup, interview guide, publishing
├── requirements.txt  pytest.ini  .gitignore  README.md
```
Additions to the suggested layout, each with a reason: `sql/indexes.sql` (indexes are built *after* the bulk load for speed),
`src/config.py` and `src/db_utils.py` (one definition of paths/columns and shared helpers), `src/analysis.py` (Stage 4 as code, reused by the dashboard),
`data/reference/` (lists needed to validate states and categories), `docs/` (teaching material).

## 8. Installation
```powershell
cd consumer-complaints-data-quality
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest -q                      # 55 tests on synthetic data - should all pass
```
Details and troubleshooting: [docs/SETUP_WINDOWS.md](docs/SETUP_WINDOWS.md).

## 9. Running the pipeline
```powershell
python src/run_pipeline.py --csv data/raw/complaints_sample.csv
streamlit run dashboard/app.py
```
Outputs: `database/complaints.db`, `reports/validation_results.csv`, `reports/validation_failure_samples.csv`,
`reports/data_quality_summary.md`, `reports/readme_results_snippet.md`, `reports/profiling/*.csv`, `reports/analysis/*.csv`.
Options: `--skip-ingest`, `--chunk-size N`, `--include-narrative`, `--strict` (exit code 2 if any rule fails).
Stage-by-stage commands are in [docs/CODE_GUIDE.md](docs/CODE_GUIDE.md).

## 10. SQL concepts demonstrated
`SELECT`, `WHERE`, `DISTINCT`, `COUNT/SUM/AVG/MIN/MAX`, `GROUP BY`, `HAVING`, `ORDER BY`, `LIMIT`, `CASE WHEN`, `COALESCE/NULLIF`,
`INNER JOIN`, `LEFT JOIN` (incl. anti-join), `UNION ALL`, subqueries, CTEs (`WITH`), window functions (`ROW_NUMBER`),
date functions (`strftime`, `date`, `julianday`), `GLOB`, views, indexes, named query parameters.
Every query is explained with syntax, purpose, example output and common mistakes in **[docs/SQL_GUIDE.md](docs/SQL_GUIDE.md)**.

## 11. Data validation rules
A rule's SQL returns the **failing records**. Status is **PASS** when the % of failing records is at or below the rule's
threshold, otherwise **FAIL**; **ERROR** if the rule could not run. *Pass percentage = rules passed / rules executed.*
*Mandatory* columns (blank = failure): complaint_id, date_received, product, issue, company, submitted_via, date_sent_to_company,
company_response_to_consumer, timely_response. *Optional* columns (blank is legitimate): sub-product, sub-issue, narrative, public response, ZIP, tags, consent, consumer_disputed.

| ID | Rule | Category | Severity | Threshold |
|---|---|---|---|---|
| DQ-001 | Missing complaint ID | Completeness | Critical | 0 % |
| DQ-002 | Non-numeric complaint ID | Validity | High | 0 % |
| DQ-003 | Duplicate complaint IDs (surplus records) | Uniqueness | Critical | 0 % |
| DQ-004 | Missing company name | Completeness | Critical | 0 % |
| DQ-005 | Missing / invalid date received | Validity | Critical | 0 % |
| DQ-006 | Date received outside plausible range | Validity | High | 0 % |
| DQ-007 | Missing / invalid date sent to company | Validity | High | 0 % |
| DQ-008 | Date sent earlier than date received | Consistency | High | 0 % |
| DQ-009 | Invalid state code (non-blank, not in reference list) | Validity | Medium | 0 % |
| DQ-010 | Missing state (tolerance-based) | Completeness | Low | 5 % |
| DQ-011 | Missing product | Completeness | High | 0 % |
| DQ-012 | Missing issue | Completeness | High | 0 % |
| DQ-013 | Missing submission channel | Completeness | Medium | 0 % |
| DQ-014 | Missing company response | Completeness | Medium | 0 % |
| DQ-015 | Missing timely-response flag | Completeness | Medium | 0 % |
| DQ-016 | Inconsistent product spellings | Consistency | Medium | 0 % |
| DQ-017 | Inconsistent issue spellings | Consistency | Medium | 0 % |
| DQ-018 | Inconsistent company spellings | Consistency | Medium | 0 % |
| DQ-019 | Leading/trailing spaces in product, issue, company | Consistency | Low | 0 % |
| DQ-020 | Invalid submission channel | Validity | Medium | 0 % |
| DQ-021 | Invalid company response value | Validity | Medium | 0 % |
| DQ-022 | Invalid timely-response value | Validity | High | 0 % |
| DQ-023 | Invalid consumer-disputed value | Validity | Low | 0 % |

Thresholds and severities are **project policy choices**, set in the `@threshold_pct` / `@severity` lines of `sql/validation.sql`.
Valid-value lists live in `data/reference/valid_categories.csv`; if the CFPB introduces a new category, review failing samples before treating it as bad data.

## 12. Actual results and findings

> **PLACEHOLDER - no real results are included in this repository yet.**
> Run the pipeline on your downloaded CFPB extract, then replace this block with the contents of
> `reports/readme_results_snippet.md` (generated from your real run; every number is read from the database).
> Do not type numbers by hand and do not paste results from the synthetic test file.

## 13. Dashboard screenshots
Add screenshots from the **real** run to `docs/images/` (see [docs/PUBLISHING.md](docs/PUBLISHING.md)), then enable these lines:

<!--
![Overview](docs/images/dashboard_overview.png)
![Missing values](docs/images/dashboard_missing_values.png)
![Trends](docs/images/dashboard_trends.png)
![Products and companies](docs/images/dashboard_products_companies.png)
-->
*Screenshots pending.*

## 14. Limitations
* Complaints are consumer-reported and published after company response; the data is **not** a statistically representative sample of all consumer experience.
* **All findings apply only to this 12-day extract** (20-31 December 2024, 99,350 records). They must not be generalised to the full CFPB database or to any company.
* **The late-December holiday period may not represent typical complaint patterns.** Volumes, product mix and response timing in these 12 days could differ from other times of year.
* **Credit reporting dominates this sample** (credit bureaus account for most records), so product and company charts and the overall timely-response % mostly describe credit reporting complaints.
* **A 12-day window is too short for monthly or seasonal trends**, so the dashboard shows complaints per day.
* This extract is not described as representative of all consumer complaints.
* Rule thresholds and the optional/mandatory split are judgement calls made for this project; reference lists (states, allowed categories) may lag the CFPB's current values.
* `consumer_disputed` is not populated for newer complaints; ZIP codes are partly masked; narratives are only present when the consumer consented and are not loaded by default.
* Ingestion recognises ISO timestamps (`2024-12-23T11:23:45.000Z`), `YYYY-MM-DD`, `MM/DD/YYYY` and `MM/DD/YY` dates (month first). Timestamps are reduced to their written calendar date (UTC as exported), so the response-date check (DQ-008) compares dates, not times of day. A file using another format (for example day first) would fail DQ-005/007, which then signals a format problem rather than bad data.
* SQLite is single-user and file-based; there is no scheduling, alerting, lineage or access control.
* Passing these checks says nothing about regulatory compliance, and the project is not a data governance framework.

## 15. Future improvements
Scheduled runs; trend of quality scores across extracts; statistical outlier checks (e.g. sudden volume spikes); fuzzy matching for company-name variants; configurable thresholds in a YAML file; run against a server database (PostgreSQL); CI with GitHub Actions running `pytest`.

---

## Data dictionary
Column names in the database are the CSV headers in lower snake_case (`Timely response?` -> `timely_response`). Descriptions follow the CFPB's public field documentation; confirm against the current CFPB field reference.

| Database column | CSV header | Description | Required here? |
|---|---|---|---|
| `date_received` | Date received | Date the CFPB received the complaint | Mandatory |
| `product` | Product | Type of product the consumer identified | Mandatory |
| `sub_product` | Sub-product | More specific product type | Optional |
| `issue` | Issue | The issue the consumer identified | Mandatory |
| `sub_issue` | Sub-issue | More specific issue | Optional |
| `consumer_complaint_narrative` | Consumer complaint narrative | Consumer's description, only if consent given (not loaded by default) | Optional |
| `company_public_response` | Company public response | Company's optional public-facing response | Optional |
| `company` | Company | Company the complaint is about | Mandatory |
| `state` | State | Consumer's state (2-letter code) | Optional (5 % tolerance) |
| `zip_code` | ZIP code | Consumer's ZIP, possibly truncated/masked | Optional |
| `tags` | Tags | e.g. older American / servicemember flags | Optional |
| `consumer_consent_provided` | Consumer consent provided? | Whether the consumer agreed to publish the narrative | Optional |
| `submitted_via` | Submitted via | Channel used (Web, Phone, Referral, Postal mail, Fax, Email) | Mandatory |
| `date_sent_to_company` | Date sent to company | Date the CFPB forwarded the complaint | Mandatory |
| `company_response_to_consumer` | Company response to consumer | How the company responded | Mandatory |
| `timely_response` | Timely response? | Whether the company responded on time (Yes/No) | Mandatory |
| `consumer_disputed` | Consumer disputed? | Whether the consumer disputed the response (Yes/No/N/A) | Optional |
| `complaint_id` | Complaint ID | Unique CFPB identifier | Mandatory |
| `row_id` | *(added by this project)* | Surrogate key for pointing at individual records | - |

## More documentation
[SQL guide](docs/SQL_GUIDE.md) - [Python code guide](docs/CODE_GUIDE.md) - [Windows setup](docs/SETUP_WINDOWS.md) - [Interview guide](docs/INTERVIEW_GUIDE.md) - [Testing & publishing](docs/PUBLISHING.md)

## Data attribution
Data: Consumer Financial Protection Bureau, Consumer Complaint Database (public). This project is independent and is not affiliated with or endorsed by the CFPB or American Express.
