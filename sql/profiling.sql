-- =====================================================================
-- profiling.sql : data DISCOVERY queries (what does the data look like?)
-- Run by src/profile_data.py; each block is exported as a CSV.
-- Profiling only DESCRIBES the data - pass/fail decisions are in validation.sql.
-- =====================================================================

-- @id: P01_overview
-- @title: Dataset overview
-- @description: Record count and distinct counts of key columns.
SELECT
    COUNT(*)                       AS total_records,
    COUNT(DISTINCT complaint_id)   AS unique_complaint_ids,
    COUNT(DISTINCT company)        AS unique_companies,
    COUNT(DISTINCT product)        AS unique_products,
    COUNT(DISTINCT issue)          AS unique_issues,
    COUNT(DISTINCT state)          AS unique_state_values
FROM complaints_raw;

-- @id: P02_missing_values
-- @title: Missing values by column
-- @description: Blank (NULL, empty or spaces-only) values per column. Mandatory columns should be 0; optional columns may legitimately be blank.
SELECT 'complaint_id' AS column_name, 'Mandatory' AS requirement,
       SUM(CASE WHEN complaint_id IS NULL OR TRIM(complaint_id) = '' THEN 1 ELSE 0 END) AS missing_count,
       ROUND(100.0 * SUM(CASE WHEN complaint_id IS NULL OR TRIM(complaint_id) = '' THEN 1 ELSE 0 END) / COUNT(*), 2) AS missing_pct
FROM complaints_raw
UNION ALL
SELECT 'date_received', 'Mandatory',
       SUM(CASE WHEN date_received IS NULL OR TRIM(date_received) = '' THEN 1 ELSE 0 END),
       ROUND(100.0 * SUM(CASE WHEN date_received IS NULL OR TRIM(date_received) = '' THEN 1 ELSE 0 END) / COUNT(*), 2)
FROM complaints_raw
UNION ALL
SELECT 'product', 'Mandatory',
       SUM(CASE WHEN product IS NULL OR TRIM(product) = '' THEN 1 ELSE 0 END),
       ROUND(100.0 * SUM(CASE WHEN product IS NULL OR TRIM(product) = '' THEN 1 ELSE 0 END) / COUNT(*), 2)
FROM complaints_raw
UNION ALL
SELECT 'issue', 'Mandatory',
       SUM(CASE WHEN issue IS NULL OR TRIM(issue) = '' THEN 1 ELSE 0 END),
       ROUND(100.0 * SUM(CASE WHEN issue IS NULL OR TRIM(issue) = '' THEN 1 ELSE 0 END) / COUNT(*), 2)
FROM complaints_raw
UNION ALL
SELECT 'company', 'Mandatory',
       SUM(CASE WHEN company IS NULL OR TRIM(company) = '' THEN 1 ELSE 0 END),
       ROUND(100.0 * SUM(CASE WHEN company IS NULL OR TRIM(company) = '' THEN 1 ELSE 0 END) / COUNT(*), 2)
FROM complaints_raw
UNION ALL
SELECT 'submitted_via', 'Mandatory',
       SUM(CASE WHEN submitted_via IS NULL OR TRIM(submitted_via) = '' THEN 1 ELSE 0 END),
       ROUND(100.0 * SUM(CASE WHEN submitted_via IS NULL OR TRIM(submitted_via) = '' THEN 1 ELSE 0 END) / COUNT(*), 2)
FROM complaints_raw
UNION ALL
SELECT 'date_sent_to_company', 'Mandatory',
       SUM(CASE WHEN date_sent_to_company IS NULL OR TRIM(date_sent_to_company) = '' THEN 1 ELSE 0 END),
       ROUND(100.0 * SUM(CASE WHEN date_sent_to_company IS NULL OR TRIM(date_sent_to_company) = '' THEN 1 ELSE 0 END) / COUNT(*), 2)
FROM complaints_raw
UNION ALL
SELECT 'company_response_to_consumer', 'Mandatory',
       SUM(CASE WHEN company_response_to_consumer IS NULL OR TRIM(company_response_to_consumer) = '' THEN 1 ELSE 0 END),
       ROUND(100.0 * SUM(CASE WHEN company_response_to_consumer IS NULL OR TRIM(company_response_to_consumer) = '' THEN 1 ELSE 0 END) / COUNT(*), 2)
FROM complaints_raw
UNION ALL
SELECT 'timely_response', 'Mandatory',
       SUM(CASE WHEN timely_response IS NULL OR TRIM(timely_response) = '' THEN 1 ELSE 0 END),
       ROUND(100.0 * SUM(CASE WHEN timely_response IS NULL OR TRIM(timely_response) = '' THEN 1 ELSE 0 END) / COUNT(*), 2)
FROM complaints_raw
UNION ALL
SELECT 'state', 'Optional (monitored)',
       SUM(CASE WHEN state IS NULL OR TRIM(state) = '' THEN 1 ELSE 0 END),
       ROUND(100.0 * SUM(CASE WHEN state IS NULL OR TRIM(state) = '' THEN 1 ELSE 0 END) / COUNT(*), 2)
FROM complaints_raw
UNION ALL
SELECT 'zip_code', 'Optional',
       SUM(CASE WHEN zip_code IS NULL OR TRIM(zip_code) = '' THEN 1 ELSE 0 END),
       ROUND(100.0 * SUM(CASE WHEN zip_code IS NULL OR TRIM(zip_code) = '' THEN 1 ELSE 0 END) / COUNT(*), 2)
FROM complaints_raw
UNION ALL
SELECT 'sub_product', 'Optional',
       SUM(CASE WHEN sub_product IS NULL OR TRIM(sub_product) = '' THEN 1 ELSE 0 END),
       ROUND(100.0 * SUM(CASE WHEN sub_product IS NULL OR TRIM(sub_product) = '' THEN 1 ELSE 0 END) / COUNT(*), 2)
FROM complaints_raw
UNION ALL
SELECT 'sub_issue', 'Optional',
       SUM(CASE WHEN sub_issue IS NULL OR TRIM(sub_issue) = '' THEN 1 ELSE 0 END),
       ROUND(100.0 * SUM(CASE WHEN sub_issue IS NULL OR TRIM(sub_issue) = '' THEN 1 ELSE 0 END) / COUNT(*), 2)
FROM complaints_raw
UNION ALL
SELECT 'company_public_response', 'Optional',
       SUM(CASE WHEN company_public_response IS NULL OR TRIM(company_public_response) = '' THEN 1 ELSE 0 END),
       ROUND(100.0 * SUM(CASE WHEN company_public_response IS NULL OR TRIM(company_public_response) = '' THEN 1 ELSE 0 END) / COUNT(*), 2)
FROM complaints_raw
UNION ALL
SELECT 'tags', 'Optional',
       SUM(CASE WHEN tags IS NULL OR TRIM(tags) = '' THEN 1 ELSE 0 END),
       ROUND(100.0 * SUM(CASE WHEN tags IS NULL OR TRIM(tags) = '' THEN 1 ELSE 0 END) / COUNT(*), 2)
FROM complaints_raw
UNION ALL
SELECT 'consumer_consent_provided', 'Optional',
       SUM(CASE WHEN consumer_consent_provided IS NULL OR TRIM(consumer_consent_provided) = '' THEN 1 ELSE 0 END),
       ROUND(100.0 * SUM(CASE WHEN consumer_consent_provided IS NULL OR TRIM(consumer_consent_provided) = '' THEN 1 ELSE 0 END) / COUNT(*), 2)
FROM complaints_raw
UNION ALL
SELECT 'consumer_disputed', 'Optional',
       SUM(CASE WHEN consumer_disputed IS NULL OR TRIM(consumer_disputed) = '' THEN 1 ELSE 0 END),
       ROUND(100.0 * SUM(CASE WHEN consumer_disputed IS NULL OR TRIM(consumer_disputed) = '' THEN 1 ELSE 0 END) / COUNT(*), 2)
FROM complaints_raw
UNION ALL
SELECT 'consumer_complaint_narrative', 'Optional (not loaded by default)',
       SUM(CASE WHEN consumer_complaint_narrative IS NULL OR TRIM(consumer_complaint_narrative) = '' THEN 1 ELSE 0 END),
       ROUND(100.0 * SUM(CASE WHEN consumer_complaint_narrative IS NULL OR TRIM(consumer_complaint_narrative) = '' THEN 1 ELSE 0 END) / COUNT(*), 2)
FROM complaints_raw;

-- @id: P03_date_range
-- @title: Complaint date range
-- @description: Earliest and latest VALID date_received, and how many rows have no valid date.
SELECT
    MIN(date_received)                                   AS earliest_date_received,
    MAX(date_received)                                   AS latest_date_received,
    COUNT(date_received)                                 AS rows_with_valid_date,
    (SELECT COUNT(*) FROM complaints_raw) - COUNT(date_received) AS rows_without_valid_date
FROM v_complaints;

-- @id: P04_by_product
-- @title: Complaints by product
-- @description: Number and share of complaints per product, largest first.
SELECT
    COALESCE(product, '(missing)')                                              AS product,
    COUNT(*)                                                                    AS complaints,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM v_complaints), 2)            AS pct_of_total
FROM v_complaints
GROUP BY product
ORDER BY complaints DESC;

-- @id: P05_by_state
-- @title: Complaints by state value
-- @description: Complaints per state value exactly as stored (invalid codes are kept visible).
SELECT
    COALESCE(state, '(missing)')                                                AS state,
    COUNT(*)                                                                    AS complaints,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM v_complaints), 2)            AS pct_of_total
FROM v_complaints
GROUP BY state
ORDER BY complaints DESC;

-- @id: P06_top_issues
-- @title: Top 15 issues
-- @description: The most frequent complaint issues.
SELECT
    COALESCE(issue, '(missing)')   AS issue,
    COUNT(*)                       AS complaints
FROM v_complaints
GROUP BY issue
ORDER BY complaints DESC
LIMIT 15;

-- @id: P07_duplicates
-- @title: Duplicate records
-- @description: Duplicate complaint IDs and fully identical rows (all 18 source columns equal).
SELECT 'complaint_ids_that_repeat' AS metric, COUNT(*) AS value
FROM (
    SELECT complaint_id FROM complaints_raw
    WHERE complaint_id IS NOT NULL AND TRIM(complaint_id) <> ''
    GROUP BY complaint_id HAVING COUNT(*) > 1
)
UNION ALL
SELECT 'surplus_rows_from_repeated_ids', COALESCE(SUM(n - 1), 0)
FROM (
    SELECT COUNT(*) AS n FROM complaints_raw
    WHERE complaint_id IS NOT NULL AND TRIM(complaint_id) <> ''
    GROUP BY complaint_id HAVING COUNT(*) > 1
)
UNION ALL
SELECT 'surplus_rows_exact_duplicates', COALESCE(SUM(n - 1), 0)
FROM (
    SELECT COUNT(*) AS n FROM complaints_raw
    GROUP BY date_received, product, sub_product, issue, sub_issue,
             consumer_complaint_narrative, company_public_response, company, state,
             zip_code, tags, consumer_consent_provided, submitted_via,
             date_sent_to_company, company_response_to_consumer, timely_response,
             consumer_disputed, complaint_id
    HAVING COUNT(*) > 1
);

-- @id: P08_submitted_via
-- @title: Complaints by submission channel
-- @description: Distribution of submitted_via values as stored.
SELECT
    COALESCE(submitted_via, '(missing)') AS submitted_via,
    COUNT(*)                             AS complaints
FROM v_complaints
GROUP BY submitted_via
ORDER BY complaints DESC;

-- @id: P09_state_classification
-- @title: State values classified with CASE WHEN
-- @description: How many records have a valid state, an unrecognised state code, or no state.
SELECT
    CASE
        WHEN r.state IS NULL OR TRIM(r.state) = '' THEN 'Missing'
        WHEN s.code IS NULL                         THEN 'Unrecognised code'
        ELSE 'Valid (' || s.category || ')'
    END                                              AS state_status,
    COUNT(*)                                         AS complaints
FROM complaints_raw AS r
LEFT JOIN ref_states AS s ON r.state = s.code
GROUP BY state_status
ORDER BY complaints DESC;
