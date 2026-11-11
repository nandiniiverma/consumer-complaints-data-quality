## Actual results and findings


_Generated automatically by `src/generate_report.py` from pipeline run 1 (2026-11-11T19:20:48). Source file: `complaints_sample.csv`._

- Records processed: **99,350** (99,350 unique complaint IDs, 1,022 companies, 11 products)
- Valid date range: 2024-12-20 to 2024-12-31
- Validation: **21 of 23 rules passed** (91.3%); 2 failed, 0 errored
- Timely responses: 99.73% of 99,350 records that carry a Yes/No flag
- Largest products: Credit reporting or other personal consumer reports (86,833), Debt collection (5,480), Credit card (2,268)
- Largest companies by volume: TRANSUNION INTERMEDIATE HOLDINGS, INC. (28,448), Experian Information Solutions Inc. (28,011), EQUIFAX, INC. (26,961)

### Rules that did not pass

| Rule | Name | Failing records | Failing % | Status |
|---|---|---|---|---|
| DQ-009 | Invalid state code | 178 | 0.18 | FAIL |
| DQ-018 | Inconsistent company name spellings | 8 | 0.01 | FAIL |

_These are findings about the published CFPB extract as downloaded on the date shown; they say nothing about regulatory compliance._
