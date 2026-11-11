-- =====================================================================
-- validation.sql : 23 data quality rules.
--
-- HOW THIS FILE IS READ (src/validate_data.py)
--   Each rule starts with "-- @id:" followed by metadata lines, then ONE
--   SELECT statement that returns the FAILING records as two columns:
--       row_id  - which record in complaints_raw failed
--       detail  - the offending value (shown in samples)
--   Python counts the rows returned (= failing records), compares the
--   percentage of total records with @threshold_pct and assigns PASS / FAIL.
--
-- NAMED PARAMETERS supplied by Python:  :min_date  :today
--
-- DEFINITIONS
--   * "Blank" = NULL, empty, or spaces only:  col IS NULL OR TRIM(col) = ''
--   * MANDATORY columns (blank = failure): complaint_id, date_received,
--     product, issue, company, submitted_via, date_sent_to_company,
--     company_response_to_consumer, timely_response.
--   * OPTIONAL columns (blank is legitimate, NOT a failure): sub_product,
--     sub_issue, narrative, company_public_response, zip_code, tags,
--     consent, consumer_disputed. State is optional but monitored with a
--     tolerance (DQ-010).
--   * @threshold_pct = maximum % of ALL records allowed to fail while the
--     rule still PASSES. 0 means "no failing record is acceptable".
--     These are policy choices for this project - change them to suit.
--   * A "valid date" is a real ISO calendar date YYYY-MM-DD.
-- =====================================================================


-- ----------------------------- COMPLETENESS & KEYS -------------------

-- @id: DQ-001
-- @name: Missing complaint ID
-- @category: Completeness
-- @severity: Critical
-- @threshold_pct: 0
-- @description: Every complaint must carry a complaint_id; without it a record cannot be traced or de-duplicated.
SELECT row_id, '(blank)' AS detail
FROM complaints_raw
WHERE complaint_id IS NULL OR TRIM(complaint_id) = '';

-- @id: DQ-002
-- @name: Non-numeric complaint ID
-- @category: Validity
-- @severity: High
-- @threshold_pct: 0
-- @description: CFPB complaint IDs are numeric; a value containing any non-digit suggests corruption or a column shift.
SELECT row_id, complaint_id AS detail
FROM complaints_raw
WHERE TRIM(complaint_id) <> ''
  AND TRIM(complaint_id) GLOB '*[^0-9]*';

-- @id: DQ-003
-- @name: Duplicate complaint IDs
-- @category: Uniqueness
-- @severity: Critical
-- @threshold_pct: 0
-- @description: Each complaint_id should appear once. Counts the surplus records (2nd, 3rd... occurrence) of an ID that repeats.
SELECT row_id, complaint_id AS detail
FROM (
    SELECT row_id,
           complaint_id,
           ROW_NUMBER() OVER (PARTITION BY complaint_id ORDER BY row_id) AS occurrence
    FROM complaints_raw
    WHERE complaint_id IS NOT NULL AND TRIM(complaint_id) <> ''
)
WHERE occurrence > 1;

-- @id: DQ-004
-- @name: Missing company name
-- @category: Completeness
-- @severity: Critical
-- @threshold_pct: 0
-- @description: Every complaint must name the company it concerns; reporting by company is impossible otherwise.
SELECT row_id, '(blank)' AS detail
FROM complaints_raw
WHERE company IS NULL OR TRIM(company) = '';


-- ----------------------------- DATES ---------------------------------

-- @id: DQ-005
-- @name: Missing or invalid date received
-- @category: Validity
-- @severity: Critical
-- @threshold_pct: 0
-- @description: date_received must be a real calendar date; ingestion has already converted real ISO timestamps (e.g. 2024-12-23T11:23:45.000Z) and MM/DD/YYYY or MM/DD/YY dates to YYYY-MM-DD, so anything else is invalid (rejects blanks, 2024-13-45, 2024-02-30, 05-Dec-2024).
SELECT row_id, COALESCE(date_received, '(null)') AS detail
FROM complaints_raw
WHERE date_received IS NULL
   OR TRIM(date_received) = ''
   OR date_received NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
   OR date(date_received) IS NULL
   OR date(date_received) <> date_received;

-- @id: DQ-006
-- @name: Date received outside plausible range
-- @category: Validity
-- @severity: High
-- @threshold_pct: 0
-- @description: A valid date_received should fall between the earliest CFPB date (:min_date) and today (:today). Invalid dates are handled by DQ-005.
SELECT row_id, date_received AS detail
FROM v_complaints
WHERE date_received IS NOT NULL
  AND (date_received < :min_date OR date_received > :today);

-- @id: DQ-007
-- @name: Missing or invalid date sent to company
-- @category: Validity
-- @severity: High
-- @threshold_pct: 0
-- @description: date_sent_to_company is expected on every record and must be a real calendar date (real ISO timestamps and MM/DD/YYYY or MM/DD/YY values are converted to YYYY-MM-DD at ingestion; blanks and anything unrecognisable fail).
SELECT row_id, COALESCE(date_sent_to_company, '(null)') AS detail
FROM complaints_raw
WHERE date_sent_to_company IS NULL
   OR TRIM(date_sent_to_company) = ''
   OR date_sent_to_company NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
   OR date(date_sent_to_company) IS NULL
   OR date(date_sent_to_company) <> date_sent_to_company;

-- @id: DQ-008
-- @name: Date sent to company earlier than date received
-- @category: Consistency
-- @severity: High
-- @threshold_pct: 0
-- @description: A complaint cannot be sent to the company before it was received. Only records where BOTH dates are valid are compared.
SELECT row_id, date_received || ' -> ' || date_sent_to_company AS detail
FROM v_complaints
WHERE date_sent_to_company < date_received;


-- ----------------------------- STATE ---------------------------------

-- @id: DQ-009
-- @name: Invalid state code
-- @category: Validity
-- @severity: Medium
-- @threshold_pct: 0
-- @description: A non-blank state must be a recognised 2-letter US state, DC, territory or military code (data/reference/us_states.csv). Blank states are handled separately by DQ-010.
SELECT r.row_id, r.state AS detail
FROM complaints_raw AS r
LEFT JOIN ref_states AS s ON r.state = s.code
WHERE r.state IS NOT NULL
  AND TRIM(r.state) <> ''
  AND s.code IS NULL;

-- @id: DQ-010
-- @name: Missing state (tolerance-based)
-- @category: Completeness
-- @severity: Low
-- @threshold_pct: 5
-- @description: State is optional (consumers may not provide it or may be outside the US) so some blanks are legitimate; the rule fails only if more than 5% of records have no state.
SELECT row_id, '(blank)' AS detail
FROM complaints_raw
WHERE state IS NULL OR TRIM(state) = '';


-- ----------------------------- MANDATORY REPORTING COLUMNS -----------

-- @id: DQ-011
-- @name: Missing product
-- @category: Completeness
-- @severity: High
-- @threshold_pct: 0
-- @description: Product is the primary reporting dimension and is mandatory.
SELECT row_id, '(blank)' AS detail
FROM complaints_raw
WHERE product IS NULL OR TRIM(product) = '';

-- @id: DQ-012
-- @name: Missing issue
-- @category: Completeness
-- @severity: High
-- @threshold_pct: 0
-- @description: Issue (what the complaint is about) is mandatory for reporting.
SELECT row_id, '(blank)' AS detail
FROM complaints_raw
WHERE issue IS NULL OR TRIM(issue) = '';

-- @id: DQ-013
-- @name: Missing submission channel
-- @category: Completeness
-- @severity: Medium
-- @threshold_pct: 0
-- @description: submitted_via (Web, Phone, ...) is mandatory.
SELECT row_id, '(blank)' AS detail
FROM complaints_raw
WHERE submitted_via IS NULL OR TRIM(submitted_via) = '';

-- @id: DQ-014
-- @name: Missing company response
-- @category: Completeness
-- @severity: Medium
-- @threshold_pct: 0
-- @description: company_response_to_consumer is mandatory in the public database.
SELECT row_id, '(blank)' AS detail
FROM complaints_raw
WHERE company_response_to_consumer IS NULL OR TRIM(company_response_to_consumer) = '';

-- @id: DQ-015
-- @name: Missing timely-response flag
-- @category: Completeness
-- @severity: Medium
-- @threshold_pct: 0
-- @description: timely_response is mandatory; without it the timely-response percentage cannot be calculated accurately.
SELECT row_id, '(blank)' AS detail
FROM complaints_raw
WHERE timely_response IS NULL OR TRIM(timely_response) = '';


-- ----------------------------- INCONSISTENT SPELLINGS ----------------
-- Pattern: group values by their normalised form LOWER(TRIM(x)). If one
-- normalised form appears under more than one exact spelling, every record
-- using a non-dominant spelling is counted as failing. No hard-coded list of
-- "correct" products is needed.

-- @id: DQ-016
-- @name: Inconsistent product spellings
-- @category: Consistency
-- @severity: Medium
-- @threshold_pct: 0
-- @description: The same product written with different case or spacing (e.g. 'Mortgage' vs 'mortgage') splits reports into false categories.
WITH spelling_counts AS (
    SELECT LOWER(TRIM(product)) AS norm, product, COUNT(*) AS n
    FROM complaints_raw
    WHERE product IS NOT NULL AND TRIM(product) <> ''
    GROUP BY LOWER(TRIM(product)), product
),
ranked AS (
    SELECT norm, product,
           ROW_NUMBER() OVER (PARTITION BY norm ORDER BY n DESC, product) AS rnk,
           COUNT(*)     OVER (PARTITION BY norm)                          AS variants
    FROM spelling_counts
),
minority AS (
    SELECT norm, product FROM ranked WHERE variants > 1 AND rnk > 1
)
SELECT r.row_id, r.product AS detail
FROM complaints_raw AS r
JOIN minority AS m
  ON LOWER(TRIM(r.product)) = m.norm AND r.product = m.product;

-- @id: DQ-017
-- @name: Inconsistent issue spellings
-- @category: Consistency
-- @severity: Medium
-- @threshold_pct: 0
-- @description: The same issue written with different case or spacing fragments issue-level reporting.
WITH spelling_counts AS (
    SELECT LOWER(TRIM(issue)) AS norm, issue, COUNT(*) AS n
    FROM complaints_raw
    WHERE issue IS NOT NULL AND TRIM(issue) <> ''
    GROUP BY LOWER(TRIM(issue)), issue
),
ranked AS (
    SELECT norm, issue,
           ROW_NUMBER() OVER (PARTITION BY norm ORDER BY n DESC, issue) AS rnk,
           COUNT(*)     OVER (PARTITION BY norm)                        AS variants
    FROM spelling_counts
),
minority AS (
    SELECT norm, issue FROM ranked WHERE variants > 1 AND rnk > 1
)
SELECT r.row_id, r.issue AS detail
FROM complaints_raw AS r
JOIN minority AS m
  ON LOWER(TRIM(r.issue)) = m.norm AND r.issue = m.issue;

-- @id: DQ-018
-- @name: Inconsistent company name spellings
-- @category: Consistency
-- @severity: Medium
-- @threshold_pct: 0
-- @description: The same company written with different case or spacing splits its complaint count across several names.
WITH spelling_counts AS (
    SELECT LOWER(TRIM(company)) AS norm, company, COUNT(*) AS n
    FROM complaints_raw
    WHERE company IS NOT NULL AND TRIM(company) <> ''
    GROUP BY LOWER(TRIM(company)), company
),
ranked AS (
    SELECT norm, company,
           ROW_NUMBER() OVER (PARTITION BY norm ORDER BY n DESC, company) AS rnk,
           COUNT(*)     OVER (PARTITION BY norm)                          AS variants
    FROM spelling_counts
),
minority AS (
    SELECT norm, company FROM ranked WHERE variants > 1 AND rnk > 1
)
SELECT r.row_id, r.company AS detail
FROM complaints_raw AS r
JOIN minority AS m
  ON LOWER(TRIM(r.company)) = m.norm AND r.company = m.company;

-- @id: DQ-019
-- @name: Leading or trailing spaces in key text fields
-- @category: Consistency
-- @severity: Low
-- @threshold_pct: 0
-- @description: Product, issue or company values padded with spaces compare as different from the clean value in SQL. Blank (spaces-only) values are excluded - they are covered by the missing-value rules.
SELECT row_id,
       '[' || COALESCE(product, '') || '] [' || COALESCE(issue, '') || '] [' || COALESCE(company, '') || ']' AS detail
FROM complaints_raw
WHERE (TRIM(product) <> '' AND product <> TRIM(product))
   OR (TRIM(issue)   <> '' AND issue   <> TRIM(issue))
   OR (TRIM(company) <> '' AND company <> TRIM(company));


-- ----------------------------- CATEGORICAL VALUE VALIDITY ------------
-- Pattern: non-blank value must exist in data/reference/valid_categories.csv
-- (loaded into ref_valid_values). Comparison is case-sensitive on purpose.

-- @id: DQ-020
-- @name: Invalid submission channel
-- @category: Validity
-- @severity: Medium
-- @threshold_pct: 0
-- @description: submitted_via must be one of the allowed channels listed in ref_valid_values.
SELECT row_id, submitted_via AS detail
FROM complaints_raw
WHERE submitted_via IS NOT NULL AND TRIM(submitted_via) <> ''
  AND submitted_via NOT IN (SELECT valid_value FROM ref_valid_values WHERE column_name = 'submitted_via');

-- @id: DQ-021
-- @name: Invalid company response value
-- @category: Validity
-- @severity: Medium
-- @threshold_pct: 0
-- @description: company_response_to_consumer must be one of the allowed response types listed in ref_valid_values.
SELECT row_id, company_response_to_consumer AS detail
FROM complaints_raw
WHERE company_response_to_consumer IS NOT NULL AND TRIM(company_response_to_consumer) <> ''
  AND company_response_to_consumer NOT IN (SELECT valid_value FROM ref_valid_values WHERE column_name = 'company_response_to_consumer');

-- @id: DQ-022
-- @name: Invalid timely-response value
-- @category: Validity
-- @severity: High
-- @threshold_pct: 0
-- @description: timely_response must be exactly Yes or No.
SELECT row_id, timely_response AS detail
FROM complaints_raw
WHERE timely_response IS NOT NULL AND TRIM(timely_response) <> ''
  AND timely_response NOT IN (SELECT valid_value FROM ref_valid_values WHERE column_name = 'timely_response');

-- @id: DQ-023
-- @name: Invalid consumer-disputed value
-- @category: Validity
-- @severity: Low
-- @threshold_pct: 0
-- @description: consumer_disputed is optional (no longer collected for new complaints) but a non-blank value must be Yes, No or N/A.
SELECT row_id, consumer_disputed AS detail
FROM complaints_raw
WHERE consumer_disputed IS NOT NULL AND TRIM(consumer_disputed) <> ''
  AND consumer_disputed NOT IN (SELECT valid_value FROM ref_valid_values WHERE column_name = 'consumer_disputed');
