-- =====================================================================
-- schema.sql : creates every table and view used by the project.
-- Executed by src/ingest.py (via sqlite3's executescript).
--
-- Design notes
--   * complaints_raw stores EVERY column as TEXT, exactly as it appeared in
--     the CSV (only an empty CSV field is stored as NULL). If we let the
--     database convert types on load, a bad date such as "2024-13-45" could be
--     silently changed and our validation rules would never see it.
--   * row_id is a surrogate key we add so every record can be pointed at
--     (complaint_id itself may be missing or duplicated - that is what we test).
--   * Audit tables (ingestion_log, pipeline_runs, validation_results,
--     validation_samples) keep an evidence trail of every run.
-- =====================================================================

DROP VIEW  IF EXISTS v_complaints;
DROP TABLE IF EXISTS complaints_raw;
DROP TABLE IF EXISTS ref_states;
DROP TABLE IF EXISTS ref_valid_values;

CREATE TABLE complaints_raw (
    row_id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    date_received                 TEXT,
    product                       TEXT,
    sub_product                   TEXT,
    issue                         TEXT,
    sub_issue                     TEXT,
    consumer_complaint_narrative  TEXT,
    company_public_response       TEXT,
    company                       TEXT,
    state                         TEXT,
    zip_code                      TEXT,
    tags                          TEXT,
    consumer_consent_provided     TEXT,
    submitted_via                 TEXT,
    date_sent_to_company          TEXT,
    company_response_to_consumer  TEXT,
    timely_response               TEXT,
    consumer_disputed             TEXT,
    complaint_id                  TEXT,
    -- Exact text of the two date columns as found in the CSV. date_received and
    -- date_sent_to_company above hold the same value, except that a real ISO
    -- timestamp (2024-12-23T11:23:45.000Z) or US-style date (MM/DD/YYYY, MM/DD/YY)
    -- is rewritten as plain ISO YYYY-MM-DD so SQL date
    -- functions work. Anything that is not a real calendar date is left unchanged.
    date_received_original        TEXT,
    date_sent_to_company_original TEXT
);

-- Reference data (loaded from data/reference/*.csv by ingest.py)
CREATE TABLE ref_states (
    code      TEXT PRIMARY KEY,
    name      TEXT NOT NULL,
    category  TEXT NOT NULL      -- STATE, DISTRICT, TERRITORY, ASSOCIATED_STATE, MILITARY
);

CREATE TABLE ref_valid_values (
    column_name  TEXT NOT NULL,
    valid_value  TEXT NOT NULL,
    PRIMARY KEY (column_name, valid_value)
);

-- Audit / results tables (kept across re-ingests)
CREATE TABLE IF NOT EXISTS ingestion_log (
    ingestion_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ingested_at         TEXT NOT NULL,
    source_file         TEXT NOT NULL,
    source_sha256       TEXT,
    file_size_bytes     INTEGER,
    columns_in_file     INTEGER,
    rows_read           INTEGER NOT NULL,
    rows_loaded         INTEGER NOT NULL,
    narrative_included  INTEGER NOT NULL,
    chunk_size          INTEGER,
    duration_seconds    REAL,
    notes               TEXT
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at        TEXT NOT NULL,
    finished_at       TEXT,
    duration_seconds  REAL,
    status            TEXT NOT NULL,         -- RUNNING, SUCCESS, FAILED
    source_file       TEXT,
    dataset_label     TEXT,                  -- e.g. 'CFPB extract' or 'SYNTHETIC TEST DATA'
    total_rows        INTEGER,
    rules_total       INTEGER,
    rules_passed      INTEGER,
    rules_failed      INTEGER,
    rules_errored     INTEGER,
    pass_pct          REAL,
    stage_timings     TEXT,                  -- JSON: seconds per stage
    error_message     TEXT
);

CREATE TABLE IF NOT EXISTS validation_results (
    run_id          INTEGER NOT NULL,
    rule_id         TEXT NOT NULL,
    rule_name       TEXT NOT NULL,
    category        TEXT NOT NULL,
    severity        TEXT NOT NULL,
    threshold_pct   REAL NOT NULL,
    total_records   INTEGER NOT NULL,
    failing_count   INTEGER,
    failing_pct     REAL,
    status          TEXT NOT NULL,           -- PASS, FAIL, ERROR
    description     TEXT,
    explanation     TEXT,
    execution_ms    REAL,
    error_message   TEXT,
    PRIMARY KEY (run_id, rule_id)
);

CREATE TABLE IF NOT EXISTS validation_samples (
    run_id    INTEGER NOT NULL,
    rule_id   TEXT NOT NULL,
    row_id    INTEGER,
    detail    TEXT
);

-- ---------------------------------------------------------------------
-- v_complaints: a cleaned, query-friendly VIEW over complaints_raw.
--   * TRIM removes stray spaces; NULLIF turns '' into NULL.
--   * Dates are kept ONLY if they are real ISO dates (YYYY-MM-DD); an
--     invalid date becomes NULL so analysis never trips over it.
-- The raw table is never modified. Validation rules query complaints_raw
-- directly (they need to see the bad values); analysis queries use this view.
-- ---------------------------------------------------------------------
CREATE VIEW v_complaints AS
SELECT
    row_id,
    NULLIF(TRIM(complaint_id), '')                  AS complaint_id,
    CASE WHEN date_received GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
              AND date(date_received) = date_received
         THEN date_received END                     AS date_received,
    CASE WHEN date_sent_to_company GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
              AND date(date_sent_to_company) = date_sent_to_company
         THEN date_sent_to_company END              AS date_sent_to_company,
    NULLIF(TRIM(product), '')                       AS product,
    NULLIF(TRIM(sub_product), '')                   AS sub_product,
    NULLIF(TRIM(issue), '')                         AS issue,
    NULLIF(TRIM(company), '')                       AS company,
    NULLIF(TRIM(state), '')                         AS state,
    NULLIF(TRIM(submitted_via), '')                 AS submitted_via,
    NULLIF(TRIM(company_response_to_consumer), '')  AS company_response_to_consumer,
    NULLIF(TRIM(timely_response), '')               AS timely_response,
    NULLIF(TRIM(consumer_disputed), '')             AS consumer_disputed
FROM complaints_raw;
