# SQL guide - every query explained

Written for a beginner in SQL. For each query: **What it does**, **Syntax**, **Why it matters here**,
**Example output**, **Common mistakes**.

> **About the example outputs.** They come from running the pipeline on the *synthetic* test file
> (203 invented rows with deliberately injected defects). They show the *shape* of each result.
> They are **not CFPB results**; your real numbers will differ.

Run any query yourself: open `database/complaints.db` in DB Browser for SQLite -> *Execute SQL*.
Queries with `:name` parameters need the placeholder replaced by a literal value (e.g. `:top_n` -> `10`).

---

## 0. SQL cheat-sheet used in this project

| Concept | Meaning | Where used |
|---|---|---|
| `SELECT cols FROM table` | choose columns from a table | everywhere |
| `WHERE` | filter **rows before** grouping | most queries |
| `GROUP BY` | collapse rows into one row per group, so aggregates work per group | P04, A01... |
| `HAVING` | filter **groups after** aggregation (WHERE cannot see `COUNT(*)`) | A07, A08, P07 |
| `ORDER BY ... DESC` / `LIMIT n` | sort / keep first n rows | A03, A08 |
| `COUNT(*)` / `COUNT(col)` / `COUNT(DISTINCT col)` | all rows / non-NULL values / distinct non-NULL values | P01 |
| `SUM`, `AVG`, `MIN`, `MAX`, `ROUND` | aggregates | P03, A06, A11 |
| `CASE WHEN ... THEN ... ELSE ... END` | if/else inside a query | P02, P09, A06 |
| `INNER JOIN` / `LEFT JOIN` | combine tables on a key (LEFT keeps unmatched left rows) | DQ-009, A04, A09, A10 |
| `UNION ALL` | stack results of several SELECTs | P02, P07 |
| `WITH name AS (...)` (CTE) | a named temporary result, makes long queries readable | DQ-016..018 |
| `ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ...)` | number rows within each group | DQ-003, DQ-016..018 |
| `strftime('%Y-%m', date)` / `strftime('%w', date)` | format a date to group by month/year, or get the weekday number | A02, A11 |

**Three rules that prevent most beginner bugs**

1. **NULL is "unknown", not a value.** `col = NULL` is never true; write `col IS NULL`. Any comparison with NULL
   gives NULL (treated as false in `WHERE`). That is why we define "blank" as `col IS NULL OR TRIM(col) = ''`.
2. **Integer division truncates.** `100 * 3 / 7` is `42`; write `100.0 * 3 / 7` to get `42.86`.
3. **Every non-aggregated column in SELECT must appear in GROUP BY.**

---

## 1. Schema (`sql/schema.sql`)

### 1.1 `CREATE TABLE complaints_raw`
* **What:** creates the table holding the CSV exactly as received: 18 TEXT columns plus `row_id`.
* **Syntax:** `CREATE TABLE name (column TYPE, ...)`; `INTEGER PRIMARY KEY AUTOINCREMENT` gives each row a unique number.
* **Why:** TEXT everywhere means a bad date such as `2024-13-45` or an ID like `ABC123` is **kept**, so validation can find it.
  `row_id` lets every failing record be pointed at, even when `complaint_id` is blank or duplicated.
* **Mistake:** typing columns as DATE/INTEGER. SQLite would not reject bad values but tools that read the table may convert them.

### 1.2 `CREATE VIEW v_complaints`
* **What:** a saved SELECT that behaves like a table, giving a cleaned version of the raw data.
* **Syntax highlights:**
  `NULLIF(TRIM(x), '')` -> trims spaces, turns `''` into NULL.
  `CASE WHEN date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND date(date) = date THEN date END`
  -> keep the date only if it has the right shape **and** is a real calendar day (`date('2024-02-30')` gives `2024-03-01`, which differs from the input, so it is rejected). Otherwise the result is NULL.
* **Why:** analysis queries use the view so they never trip over invalid dates; the raw table stays untouched.
* **Mistake:** relying only on `GLOB` (it accepts the impossible `2024-13-45`) or only on `date()` (it quietly *normalises* `2024-02-30` to `2024-03-01` instead of rejecting it, so you must compare the result with the original text). Use both.

---

## 2. Profiling queries (`sql/profiling.sql`)

### P01 - Dataset overview
```sql
SELECT COUNT(*) AS total_records, COUNT(DISTINCT complaint_id) AS unique_complaint_ids,
       COUNT(DISTINCT company) AS unique_companies, COUNT(DISTINCT product) AS unique_products,
       COUNT(DISTINCT issue) AS unique_issues, COUNT(DISTINCT state) AS unique_state_values
FROM complaints_raw;
```
* **What:** one row of headline counts.
* **Syntax:** `COUNT(*)` counts rows; `COUNT(DISTINCT col)` counts different non-NULL values.
* **Why:** first look at the data. If `total_records` > `unique_complaint_ids` you already suspect duplicates or blank IDs.
* **Example (synthetic):**
  `total_records 203 | unique_complaint_ids 198 | unique_companies 9 | unique_products 8 | unique_issues 13`
  (198 = 200 base IDs minus 2 blank IDs; the 3 duplicated IDs add no new distinct values.)
* **Mistakes:** forgetting that `COUNT(DISTINCT x)` ignores NULLs; comparing it with `COUNT(*)` without remembering blanks.
  Note also that 9 companies / 8 products include spelling variants - that is a finding (DQ-016, DQ-018).

### P02 - Missing values by column
* **What:** for every column, how many values are NULL / empty / spaces-only, and what share of rows.
* **Syntax:** `SUM(CASE WHEN col IS NULL OR TRIM(col) = '' THEN 1 ELSE 0 END)` counts matching rows;
  `ROUND(100.0 * ... / COUNT(*), 2)` converts to a percentage; `UNION ALL` stacks one SELECT per column.
* **Why:** separates **mandatory** columns (should be 0 missing) from **optional** ones (blank is normal) - the basis of rules DQ-001, 004, 011-015.
* **Example (synthetic):**
  ```
  column_name  requirement  missing_count  missing_pct
  complaint_id Mandatory    2              0.99
  company      Mandatory    3              1.48
  state        Optional (monitored)  8    3.94
  ```
* **Mistakes:** `SUM(col IS NULL)` works in SQLite but is not portable - `CASE WHEN` is. Dividing by `COUNT(col)` instead of `COUNT(*)` would exclude the very rows you are measuring.

### P03 - Date range
```sql
SELECT MIN(date_received), MAX(date_received), COUNT(date_received),
       (SELECT COUNT(*) FROM complaints_raw) - COUNT(date_received)
FROM v_complaints;
```
* **What:** earliest and latest **valid** date, rows with a valid date, rows without.
* **Syntax:** `MIN/MAX` work on ISO dates because `YYYY-MM-DD` text sorts chronologically; `COUNT(col)` skips NULL (invalid dates are NULL in the view); `(SELECT ...)` is a scalar subquery.
* **Why:** confirms the extract covers the period you downloaded and exposes impossible dates (a 1999 or 2031 min/max is a red flag - DQ-006).
* **Example (synthetic):** `1999-05-01 | 2031-01-01 | 199 | 4`
* **Mistake:** running MIN/MAX on the raw column - `'05-Dec-2024'` would sort wrongly as text.

### P04 / P05 / P08 - Distributions (product, state, channel)
```sql
SELECT COALESCE(product, '(missing)') AS product, COUNT(*) AS complaints,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM v_complaints), 2) AS pct_of_total
FROM v_complaints GROUP BY product ORDER BY complaints DESC;
```
* **What:** how many complaints fall in each category and what share of the total.
* **Syntax:** `GROUP BY` makes one row per product; `COALESCE(x, '(missing)')` substitutes a label for NULL so blanks are visible; the subquery gives the grand total for the percentage.
* **Why:** shows the shape of the data and surfaces odd categories (P04 reveals `mortgage` next to `Mortgage`; P05 reveals `ZZ`, `ca`).
* **Example (synthetic, P04):** `Student loan 40 19.70 | Mortgage 40 19.70 | ... | mortgage 1 0.49`
* **Mistakes:** selecting a column that is not in `GROUP BY`; forgetting `ORDER BY` (order is otherwise undefined); expecting `GROUP BY` to merge `Mortgage` and `mortgage` (it does not - that is what DQ-016 detects).
  P05/P08 are the same pattern on `state` / `submitted_via`.

### P06 - Top 15 issues
Same pattern as P04 plus `LIMIT 15`. **Mistake:** `LIMIT` without `ORDER BY` returns arbitrary rows.

### P07 - Duplicates
* **What:** three metrics: how many complaint IDs repeat, how many surplus rows they create, how many rows are **identical in all 18 columns**.
* **Syntax:** inner query `GROUP BY complaint_id HAVING COUNT(*) > 1` finds repeated IDs; `SUM(n - 1)` counts only the extra copies; the last query groups by every column.
* **Why:** a repeated ID is a key violation; an exact duplicate row is a load/extract problem. They are different findings.
* **Example (synthetic):** `complaint_ids_that_repeat 3 | surplus_rows_from_repeated_ids 3 | surplus_rows_exact_duplicates 2`
  (the third duplicate has the same ID but a different company, so it is not an exact copy.)
* **Mistakes:** using `WHERE COUNT(*) > 1` (must be `HAVING`); counting all rows in a duplicate group instead of the surplus.

### P09 - State classification with CASE WHEN + LEFT JOIN
```sql
SELECT CASE WHEN r.state IS NULL OR TRIM(r.state) = '' THEN 'Missing'
            WHEN s.code IS NULL THEN 'Unrecognised code'
            ELSE 'Valid (' || s.category || ')' END AS state_status,
       COUNT(*) AS complaints
FROM complaints_raw r LEFT JOIN ref_states s ON r.state = s.code
GROUP BY state_status ORDER BY complaints DESC;
```
* **What:** buckets every record as valid / unrecognised / missing.
* **Syntax:** `CASE` checks conditions in order; `||` concatenates text; `LEFT JOIN` keeps every complaint even with no matching state row (then `s.code` is NULL).
* **Why:** keeps *missing* and *invalid* states separate, as the project brief requires.
* **Example (synthetic):** `Valid (STATE) 152 | Valid (TERRITORY) 20 | Valid (DISTRICT) 19 | Missing 8 | Unrecognised code 4`
* **Mistakes:** using `INNER JOIN` (would silently drop the unmatched rows); order of `WHEN` branches (the blank check must come first).

---

## 3. Validation rules (`sql/validation.sql`)

Every rule is a SELECT returning the **failing** records as `(row_id, detail)`. Python counts them, turns the count into a % of all records and applies the rule's `@threshold_pct`. The 23 rules use seven patterns.

### Pattern A - Missing mandatory value (DQ-001, 004, 011, 012, 013, 014, 015)
```sql
SELECT row_id, '(blank)' AS detail FROM complaints_raw
WHERE complaint_id IS NULL OR TRIM(complaint_id) = '';
```
* **What:** records where a mandatory column is NULL, empty or only spaces.
* **Why:** a record without ID, company, product, issue... cannot be reported correctly.
* **Example (synthetic DQ-004):** 3 failing records: two empty companies and one containing only spaces.
* **Mistakes:** `= NULL`; forgetting `TRIM` (spaces-only looks filled but is useless). Optional columns are deliberately **not** tested this way.
* **Tolerance variant - DQ-010 (state):** same query, but `@threshold_pct: 5`, so up to 5 % blanks still PASS (synthetic: 8 of 203 = 3.94 % -> PASS).

### Pattern B - Invalid date (DQ-005, DQ-007)
```sql
WHERE date_received IS NULL OR TRIM(date_received) = ''
   OR date_received NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
   OR date(date_received) IS NULL
   OR date(date_received) <> date_received
```
* **What:** flags blank dates, wrong format, impossible dates and non-existent days.
* **Syntax:** `GLOB` is a case-sensitive wildcard match (`[0-9]` = one digit); `date(x)` returns NULL for nonsense and *normalises* e.g. `2024-02-30` to `2024-03-01`, which then differs from the input.
* **Example (synthetic):** `(null)`, `2024-13-45`, `2024-02-30`, `05-Dec-2024`.
* **Mistake:** writing `NOT (glob AND date(x) = x)` - when `date(x)` is NULL the whole expression is NULL and the bad row **escapes**. Testing each failure mode with `OR` avoids this NULL trap.

### Pattern C - Range and cross-field logic (DQ-006, DQ-008)
* **DQ-006:** `WHERE date_received IS NOT NULL AND (date_received < :min_date OR date_received > :today)` on the view: valid dates outside CFPB's start date and today. Parameters are bound by Python, never pasted into the SQL.
* **DQ-008:** `WHERE date_sent_to_company < date_received` on the view (ISO dates compare correctly as text); rows with an invalid date are skipped automatically because comparisons with NULL are not true.
* **Example (synthetic DQ-008):** `2024-03-31 -> 2024-03-26`.
* **Mistake:** comparing raw text like `05-Dec-2024` - always compare validated ISO dates.

### Pattern D - Duplicate keys with a window function (DQ-003)
```sql
SELECT row_id, complaint_id AS detail FROM (
    SELECT row_id, complaint_id,
           ROW_NUMBER() OVER (PARTITION BY complaint_id ORDER BY row_id) AS occurrence
    FROM complaints_raw WHERE complaint_id IS NOT NULL AND TRIM(complaint_id) <> '')
WHERE occurrence > 1;
```
* **What:** numbers the rows within each complaint_id (1, 2, 3...) and keeps the 2nd and later - the surplus copies.
* **Syntax:** `PARTITION BY` = restart numbering for each ID; `ORDER BY row_id` decides which copy counts as the "original".
* **Why:** flags exactly the records you would delete, never the first one. Blank IDs are excluded (they are DQ-001).
* **Example (synthetic):** rows 201, 202, 203 with IDs `9000011`, `9000012`, `9000013`.
* **Mistakes:** `GROUP BY ... HAVING COUNT(*) > 1` returns the IDs, not the individual rows; needs SQLite 3.25+ for window functions (any recent Python has it).

### Pattern E - Inconsistent spellings with CTEs (DQ-016, 017, 018)
```sql
WITH spelling_counts AS (SELECT LOWER(TRIM(product)) AS norm, product, COUNT(*) AS n ... GROUP BY LOWER(TRIM(product)), product),
     ranked AS (SELECT norm, product, ROW_NUMBER() OVER (PARTITION BY norm ORDER BY n DESC, product) AS rnk,
                       COUNT(*) OVER (PARTITION BY norm) AS variants FROM spelling_counts),
     minority AS (SELECT norm, product FROM ranked WHERE variants > 1 AND rnk > 1)
SELECT r.row_id, r.product AS detail FROM complaints_raw r JOIN minority m ON ... ;
```
* **What:** step 1 counts every exact spelling; step 2 ranks the spellings that normalise to the same text (lower-case, trimmed) by frequency; step 3 keeps the less common spellings; the final SELECT returns the records using them.
* **Why:** finds `Mortgage` / `mortgage` / `MORTGAGE` without hard-coding what the "right" product names are - so it keeps working if the CFPB adds a new product.
* **Example (synthetic DQ-016):** `mortgage`, `Mortgage ` (trailing space), `MORTGAGE` (3 records; `Mortgage` is the dominant spelling).
* **Mistakes:** thinking `=` ignores case (it does not in SQLite); counting the dominant spelling as an error.

### Pattern F - Reference-table checks (DQ-009 with LEFT JOIN; DQ-020..023 with NOT IN)
```sql
-- DQ-009
SELECT r.row_id, r.state AS detail FROM complaints_raw r
LEFT JOIN ref_states s ON r.state = s.code
WHERE r.state IS NOT NULL AND TRIM(r.state) <> '' AND s.code IS NULL;
-- DQ-020
... WHERE submitted_via NOT IN (SELECT valid_value FROM ref_valid_values WHERE column_name = 'submitted_via')
```
* **What:** finds non-blank values that do not exist in the reference lists in `data/reference/`.
* **Why:** an "anti-join" (LEFT JOIN ... WHERE right side IS NULL) is the standard SQL way to say "in A but not in B".
* **Example (synthetic DQ-009):** `ZZ`, `XX`, `ca` (lower-case), `California` (name instead of code).
* **Mistakes:** `NOT IN` returns no rows if the list contains a NULL (our reference file has none); forgetting to exclude blanks, which would double-count missing values already covered by Pattern A.
* **Caution:** these rules are only as good as the reference lists. If the CFPB adds a category, review the failing samples before calling it bad data.

### Pattern G - Untrimmed text (DQ-019)
`WHERE (TRIM(product) <> '' AND product <> TRIM(product)) OR ...` - values with leading/trailing spaces. The `TRIM(x) <> ''` guard excludes spaces-only values so they are counted once, by Pattern A.
* **Example (synthetic):** `[Mortgage ] [Problem with a purchase] [Synthetic Union F]` - square brackets make the stray space visible.

### Rule index
| ID | Check | Pattern | Threshold |
|---|---|---|---|
| DQ-001 | Missing complaint ID | A | 0 % |
| DQ-002 | Non-numeric complaint ID (`GLOB '*[^0-9]*'`) | - | 0 % |
| DQ-003 | Duplicate complaint IDs | D | 0 % |
| DQ-004 | Missing company | A | 0 % |
| DQ-005 / 007 | Missing/invalid date received / sent | B | 0 % |
| DQ-006 | Date received outside range | C | 0 % |
| DQ-008 | Sent before received | C | 0 % |
| DQ-009 | Invalid state code | F | 0 % |
| DQ-010 | Missing state | A (tolerance) | 5 % |
| DQ-011..015 | Missing product, issue, channel, response, timely flag | A | 0 % |
| DQ-016..018 | Spelling variants: product, issue, company | E | 0 % |
| DQ-019 | Leading/trailing spaces | G | 0 % |
| DQ-020..023 | Invalid channel, response, timely flag, disputed flag | F | 0 % |

Thresholds are **policy choices for this project**, written in the `@threshold_pct` line of each rule. Change them there.

---

## 4. Analysis queries (`sql/analysis.sql`)

### A01 - Complaints by product
Same as P04 on the cleaned view. **Shows:** SELECT, GROUP BY, ORDER BY, COUNT.
Example (synthetic): `Student loan 40 19.7 | Mortgage 40 19.7 | ...`

### A02 - Daily trend
```sql
SELECT date_received AS received_date,
       CASE strftime('%w', date_received) WHEN '0' THEN 'Sun' ... ELSE 'Sat' END AS weekday,
       COUNT(*) AS complaints
FROM v_complaints WHERE date_received IS NOT NULL
GROUP BY date_received ORDER BY date_received;
```
* **What:** complaints received on each calendar day. **Syntax:** `GROUP BY date_received` makes one row per day; `strftime('%w', date)` gives the weekday number (0 = Sunday) which `CASE` turns into a name.
* **Why:** the dashboard trend chart. The real extract covers only about 12 days, so a monthly grouping would be a single bar. **Example (synthetic):** `2024-01-03 Wed 7 | 2024-01-04 Thu 9 ...`
* **Mistakes:** forgetting that days with no complaints have no row (the dashboard fills them with 0); excluding NULL dates is required because `strftime` returns NULL for them.

### A03 - Top companies
`GROUP BY company ORDER BY complaints DESC LIMIT :top_n` - top N by volume with % of total. Example (synthetic): `Synthetic Bank B 35 17.24`.
**Mistake:** `LIMIT` before `ORDER BY` is a syntax error; spelling variants split a company's count (see DQ-018).

### A04 - Complaints by state (LEFT JOIN)
`LEFT JOIN ref_states` adds the state name; `COALESCE(s.name, 'Unrecognised or missing')` labels unmatched rows. Example (synthetic): `GA Georgia 20 | PR Puerto Rico 20 | CA California 19`.

### A05 - Response distribution
Counts by `company_response_to_consumer` with percentage share. Example (synthetic): `Closed with monetary relief 41 20.20`.

### A06 - Timely response percentage
```sql
SELECT COUNT(*), SUM(CASE WHEN timely_response='Yes' THEN 1 ELSE 0 END), SUM(CASE WHEN timely_response='No' THEN 1 ELSE 0 END),
       ROUND(100.0 * SUM(CASE WHEN timely_response='Yes' THEN 1 ELSE 0 END) / COUNT(*), 2)
FROM v_complaints WHERE timely_response IN ('Yes', 'No');
```
* **What:** share of records answered on time. **Why accurate:** `WHERE ... IN ('Yes','No')` excludes blank/invalid flags so they cannot distort the %; the dataset has a suitable field, as the brief requires.
* **Example (synthetic):** `200 flagged | 179 timely | 21 not timely | 89.5 %`.
* **Mistake:** dividing by all rows (including blanks); integer division (use `100.0`).

### A07 - Timely % by product (GROUP BY + HAVING)
`GROUP BY product HAVING COUNT(*) >= :min_complaints ORDER BY timely_pct ASC` - lowest timely rates first, ignoring tiny groups.
**WHERE vs HAVING:** `WHERE` filters rows *before* grouping; `HAVING` filters groups *after* `COUNT(*)` exists. Example (synthetic, threshold 30): `Mortgage 39 51.28 | Checking account 40 100.00 | ...`

### A08 - Companies with most untimely responses
`HAVING COUNT(*) >= :min_complaints ORDER BY not_timely DESC LIMIT :top_n`. Example (synthetic, threshold 30): `Synthetic Finance E 32 8 25.00`.
**Mistake:** ranking by percentage only - a company with 2 complaints and 1 late shows 50 %; HAVING keeps the list meaningful.

### A09 - Jurisdiction type (INNER JOIN)
`FROM v_complaints c INNER JOIN ref_states s ON c.state = s.code GROUP BY s.category`. INNER JOIN keeps **only matching** rows - records with blank/invalid states disappear on purpose. Example (synthetic): `STATE 152 | TERRITORY 20 | DISTRICT 19`.
**Compare with A04/A10** to see the difference between INNER and LEFT JOIN: A09's total (191) is smaller than the record count because unmatched states are excluded.

### A10 - Unrecognised state codes (LEFT JOIN anti-join)
`LEFT JOIN ... WHERE c.state IS NOT NULL AND s.code IS NULL` - values with no match. Example (synthetic): `ca 1 | ZZ 1 | XX 1 | California 1`.

### A11 - Yearly volume and average days to forward
`strftime('%Y', date_received)` for the year; `julianday(date_sent_to_company) - julianday(date_received)` gives days between two dates; averaged only where sent >= received. Example (synthetic): `2024 197 1.0`.
**Mistake:** subtracting date strings directly - use `julianday()`.
