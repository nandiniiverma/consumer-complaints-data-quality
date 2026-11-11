-- =====================================================================
-- analysis.sql : business-style reporting queries.
-- They read the cleaned view v_complaints (invalid dates are NULL there)
-- and the reference table ref_states.
-- Named parameters supplied by Python: :top_n  :min_complaints
-- =====================================================================

-- @id: A01_complaints_by_product
-- @title: Complaints by product
-- @description: SELECT + GROUP BY + ORDER BY with a percentage share.
SELECT
    COALESCE(product, '(missing)')                                       AS product,
    COUNT(*)                                                             AS complaints,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM v_complaints), 2)     AS pct_of_total
FROM v_complaints
GROUP BY product
ORDER BY complaints DESC;

-- @id: A02_daily_trend
-- @title: Daily complaint trend
-- @description: Date-based grouping by calendar day (the extract covers only ~12 days, so a monthly view would be a single bar). Records without a valid date are excluded by WHERE; days with no complaints simply have no row.
SELECT
    date_received                                             AS received_date,
    CASE strftime('%w', date_received)
        WHEN '0' THEN 'Sun' WHEN '1' THEN 'Mon' WHEN '2' THEN 'Tue'
        WHEN '3' THEN 'Wed' WHEN '4' THEN 'Thu' WHEN '5' THEN 'Fri'
        ELSE 'Sat'
    END                                                       AS weekday,
    COUNT(*)                                                  AS complaints
FROM v_complaints
WHERE date_received IS NOT NULL
GROUP BY date_received
ORDER BY date_received;

-- @id: A03_top_companies
-- @title: Top companies by complaint volume
-- @description: GROUP BY + ORDER BY + LIMIT (:top_n companies).
SELECT
    company,
    COUNT(*)                                                             AS complaints,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM v_complaints), 2)     AS pct_of_total
FROM v_complaints
WHERE company IS NOT NULL
GROUP BY company
ORDER BY complaints DESC
LIMIT :top_n;

-- @id: A04_complaints_by_state
-- @title: Complaints by state (LEFT JOIN to state names)
-- @description: LEFT JOIN keeps records whose state is blank or unrecognised, labelled as such.
SELECT
    COALESCE(c.state, '(missing)')                    AS state,
    COALESCE(s.name, 'Unrecognised or missing')       AS state_name,
    COUNT(*)                                          AS complaints
FROM v_complaints AS c
LEFT JOIN ref_states AS s ON c.state = s.code
GROUP BY c.state, s.name
ORDER BY complaints DESC;

-- @id: A05_response_distribution
-- @title: Company response distribution
-- @description: How companies responded, with percentage share.
SELECT
    COALESCE(company_response_to_consumer, '(missing)')                  AS company_response,
    COUNT(*)                                                             AS complaints,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM v_complaints), 2)     AS pct_of_total
FROM v_complaints
GROUP BY company_response_to_consumer
ORDER BY complaints DESC;

-- @id: A06_timely_response_overall
-- @title: Timely response percentage
-- @description: CASE WHEN inside SUM. Only records whose timely_response is exactly Yes or No are counted, so blanks and invalid values cannot distort the percentage.
SELECT
    COUNT(*)                                                       AS records_with_timely_flag,
    SUM(CASE WHEN timely_response = 'Yes' THEN 1 ELSE 0 END)       AS timely,
    SUM(CASE WHEN timely_response = 'No'  THEN 1 ELSE 0 END)       AS not_timely,
    ROUND(100.0 * SUM(CASE WHEN timely_response = 'Yes' THEN 1 ELSE 0 END) / COUNT(*), 2) AS timely_pct
FROM v_complaints
WHERE timely_response IN ('Yes', 'No');

-- @id: A07_timely_by_product
-- @title: Timely response % by product (GROUP BY + HAVING)
-- @description: HAVING removes products with fewer than :min_complaints records, where a percentage would be unreliable.
SELECT
    product,
    COUNT(*)                                                       AS records_with_timely_flag,
    ROUND(100.0 * SUM(CASE WHEN timely_response = 'Yes' THEN 1 ELSE 0 END) / COUNT(*), 2) AS timely_pct
FROM v_complaints
WHERE timely_response IN ('Yes', 'No') AND product IS NOT NULL
GROUP BY product
HAVING COUNT(*) >= :min_complaints
ORDER BY timely_pct ASC;

-- @id: A08_untimely_companies
-- @title: Companies with the most untimely responses
-- @description: GROUP BY + HAVING + ORDER BY + LIMIT; shows count and rate of untimely responses among companies with enough volume.
SELECT
    company,
    COUNT(*)                                                       AS records_with_timely_flag,
    SUM(CASE WHEN timely_response = 'No' THEN 1 ELSE 0 END)        AS not_timely,
    ROUND(100.0 * SUM(CASE WHEN timely_response = 'No' THEN 1 ELSE 0 END) / COUNT(*), 2) AS not_timely_pct
FROM v_complaints
WHERE timely_response IN ('Yes', 'No') AND company IS NOT NULL
GROUP BY company
HAVING COUNT(*) >= :min_complaints
ORDER BY not_timely DESC, not_timely_pct DESC
LIMIT :top_n;

-- @id: A09_complaints_by_state_category
-- @title: Complaints by jurisdiction type (INNER JOIN)
-- @description: INNER JOIN keeps only records whose state matches ref_states, then groups by STATE / DISTRICT / TERRITORY / MILITARY.
SELECT
    s.category                       AS jurisdiction_type,
    COUNT(*)                         AS complaints
FROM v_complaints AS c
INNER JOIN ref_states AS s ON c.state = s.code
GROUP BY s.category
ORDER BY complaints DESC;

-- @id: A10_unrecognised_state_codes
-- @title: Unrecognised state codes (LEFT JOIN anti-join)
-- @description: LEFT JOIN + WHERE s.code IS NULL finds state values that have NO match in the reference list.
SELECT
    c.state                          AS state_value,
    COUNT(*)                         AS complaints
FROM v_complaints AS c
LEFT JOIN ref_states AS s ON c.state = s.code
WHERE c.state IS NOT NULL AND s.code IS NULL
GROUP BY c.state
ORDER BY complaints DESC;

-- @id: A11_yearly_summary
-- @title: Yearly volume and average days to forward a complaint
-- @description: Date grouping by year plus AVG of a date difference (julianday). Only records where both dates are valid and ordered correctly are averaged.
SELECT
    strftime('%Y', date_received)                                          AS year,
    COUNT(*)                                                               AS complaints,
    ROUND(AVG(CASE WHEN date_sent_to_company >= date_received
                   THEN julianday(date_sent_to_company) - julianday(date_received) END), 2)
                                                                           AS avg_days_to_send_to_company
FROM v_complaints
WHERE date_received IS NOT NULL
GROUP BY strftime('%Y', date_received)
ORDER BY year;
