# Data Quality Summary (run 1)


## Run details

| Item | Value |
|---|---|
| Dataset | CFPB extract |
| Source file | data/raw/complaints_sample.csv |
| Run started | 2026-11-11T19:20:48 |
| Total execution time (s) | 12.69 |
| Records processed | 99,350 |
| Unique complaint IDs | 99,350 |
| Unique companies | 1,022 |
| Earliest valid date received | 2024-12-20 |
| Latest valid date received | 2024-12-31 |
| Stage timings (s) | ingest=4.06, profiling=2.21, validation=4.46, analysis=1.9 (report-writing time is added to the run record after this file is written) |


## Headline

| Rules | Passed | Failed | Errored | Pass % |
|---|---|---|---|---|
| 23 | 21 | 2 | 0 | 91.30 |


Pass % = rules passed / rules executed. A rule passes when the percentage of failing records is at or below its documented threshold (see sql/validation.sql).


## All validation rules

| Rule | Name | Category | Severity | Failing | Failing % | Threshold % | Status |
|---|---|---|---|---|---|---|---|
| DQ-001 | Missing complaint ID | Completeness | Critical | 0 | 0.00 | 0.00 | PASS |
| DQ-002 | Non-numeric complaint ID | Validity | High | 0 | 0.00 | 0.00 | PASS |
| DQ-003 | Duplicate complaint IDs | Uniqueness | Critical | 0 | 0.00 | 0.00 | PASS |
| DQ-004 | Missing company name | Completeness | Critical | 0 | 0.00 | 0.00 | PASS |
| DQ-005 | Missing or invalid date received | Validity | Critical | 0 | 0.00 | 0.00 | PASS |
| DQ-006 | Date received outside plausible range | Validity | High | 0 | 0.00 | 0.00 | PASS |
| DQ-007 | Missing or invalid date sent to company | Validity | High | 0 | 0.00 | 0.00 | PASS |
| DQ-008 | Date sent to company earlier than date received | Consistency | High | 0 | 0.00 | 0.00 | PASS |
| DQ-009 | Invalid state code | Validity | Medium | 178 | 0.18 | 0.00 | FAIL |
| DQ-010 | Missing state (tolerance-based) | Completeness | Low | 0 | 0.00 | 5.00 | PASS |
| DQ-011 | Missing product | Completeness | High | 0 | 0.00 | 0.00 | PASS |
| DQ-012 | Missing issue | Completeness | High | 0 | 0.00 | 0.00 | PASS |
| DQ-013 | Missing submission channel | Completeness | Medium | 0 | 0.00 | 0.00 | PASS |
| DQ-014 | Missing company response | Completeness | Medium | 0 | 0.00 | 0.00 | PASS |
| DQ-015 | Missing timely-response flag | Completeness | Medium | 0 | 0.00 | 0.00 | PASS |
| DQ-016 | Inconsistent product spellings | Consistency | Medium | 0 | 0.00 | 0.00 | PASS |
| DQ-017 | Inconsistent issue spellings | Consistency | Medium | 0 | 0.00 | 0.00 | PASS |
| DQ-018 | Inconsistent company name spellings | Consistency | Medium | 8 | 0.01 | 0.00 | FAIL |
| DQ-019 | Leading or trailing spaces in key text fields | Consistency | Low | 0 | 0.00 | 0.00 | PASS |
| DQ-020 | Invalid submission channel | Validity | Medium | 0 | 0.00 | 0.00 | PASS |
| DQ-021 | Invalid company response value | Validity | Medium | 0 | 0.00 | 0.00 | PASS |
| DQ-022 | Invalid timely-response value | Validity | High | 0 | 0.00 | 0.00 | PASS |
| DQ-023 | Invalid consumer-disputed value | Validity | Low | 0 | 0.00 | 0.00 | PASS |


## Identified issues

### DQ-009 - Invalid state code (FAIL, Medium)

178 of 99,350 records (0.18%) fail this check. A non-blank state must be a recognised 2-letter US state, DC, territory or military code (data/reference/us_states.csv). Blank states are handled separately by DQ-010. Exceeds the allowed 0%.

Example failing records: row 2668: `None`; row 4254: `None`; row 7829: `None`; row 8356: `None`; row 8963: `None`

### DQ-018 - Inconsistent company name spellings (FAIL, Medium)

8 of 99,350 records (0.01%) fail this check. The same company written with different case or spacing splits its complaint count across several names. Exceeds the allowed 0%.

Example failing records: row 8418: `First Technology Federal Credit Union`; row 18547: `First Technology Federal Credit Union`; row 32841: `First Technology Federal Credit Union`; row 34585: `First Technology Federal Credit Union`; row 54128: `First Technology Federal Credit Union`


## Missing values by column

| Column | Requirement | Missing | Missing % |
|---|---|---|---|
| complaint_id | Mandatory | 0 | 0.00 |
| date_received | Mandatory | 0 | 0.00 |
| product | Mandatory | 0 | 0.00 |
| issue | Mandatory | 0 | 0.00 |
| company | Mandatory | 0 | 0.00 |
| submitted_via | Mandatory | 0 | 0.00 |
| date_sent_to_company | Mandatory | 0 | 0.00 |
| company_response_to_consumer | Mandatory | 0 | 0.00 |
| timely_response | Mandatory | 0 | 0.00 |
| state | Optional (monitored) | 0 | 0.00 |
| zip_code | Optional | 0 | 0.00 |
| sub_product | Optional | 0 | 0.00 |
| sub_issue | Optional | 0 | 0.00 |
| company_public_response | Optional | 0 | 0.00 |
| tags | Optional | 0 | 0.00 |
| consumer_consent_provided | Optional | 99,350 | 100.00 |
| consumer_disputed | Optional | 99,350 | 100.00 |
| consumer_complaint_narrative | Optional (not loaded by default) | 99,350 | 100.00 |


## Duplicates

| Metric | Value |
|---|---|
| complaint_ids_that_repeat | 0 |
| surplus_rows_from_repeated_ids | 0 |
| surplus_rows_exact_duplicates | 0 |


## Timely response

| records_with_timely_flag | timely | not_timely | timely_pct |
|---|---|---|---|
| 99,350.00 | 99,085.00 | 265.00 | 99.73 |

