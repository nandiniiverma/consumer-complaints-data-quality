# Testing, screenshots and publishing to GitHub

## A. Final test checklist (before you publish)
```powershell
pytest -q                                                  # 55 passed
python src/run_pipeline.py --csv data/raw/complaints_sample.csv
streamlit run dashboard/app.py
```
Confirm:
- [ ] The pipeline summary prints your **real** record count.
- [ ] `reports/data_quality_summary.md` does **not** show the "SYNTHETIC TEST DATA" banner.
- [ ] You skimmed the failing-record samples in the dashboard (*Identified issues*) and understand them.
- [ ] Rules that fail are findings you can explain - or a reference list / threshold you adjusted **and documented**.

## B. Screenshots
Take them from the dashboard run on the real extract (Windows: `Win+Shift+S`). Save in `docs/images/`:

| File | What to capture |
|---|---|
| `dashboard_overview.png` | KPI cards + validation table |
| `dashboard_missing_values.png` | Missing values tab |
| `dashboard_trends.png` | Complaint trends tab |
| `dashboard_products_companies.png` | By product / By company |
| `pipeline_run.png` | Terminal after `run_pipeline.py` |

Then uncomment the image lines in the README "Dashboard screenshots" section.
Do not publish screenshots of synthetic data as if they were real results.

## C. Fill in the README results
1. Open `reports/readme_results_snippet.md` (generated from your real run).
2. Paste it over the placeholder under **"12. Actual results and findings"** in `README.md`.
3. Add 2-3 sentences of your own interpretation.
4. Fill in the "Dataset log" (download date, filters, file size).

## D. Publish
```powershell
git init                       # skip if already done
git add .
git status                     # check: NO data/raw/*.csv and NO database/*.db listed
git commit -m "SQL-based data quality and validation pipeline for CFPB complaints"
```
On github.com click **New repository** (name: `consumer-complaints-data-quality`, public, no README/.gitignore), then:
```powershell
git branch -M main
git remote add origin https://github.com/<your-username>/consumer-complaints-data-quality.git
git push -u origin main
```
Check size: `git count-objects -vH`; the repository should be well under a few MB.
If a big file slipped in: `git rm --cached data/raw/complaints_sample.csv`, commit, and make sure `.gitignore` is correct.

Polish: add repository topics (`sql`, `sqlite`, `data-quality`, `python`, `streamlit`, `pandas`), pin the repo on your
profile, and put the link on your resume as: *"SQL-Based Data Quality and Validation Pipeline (Python, SQLite, Streamlit) - github.com/..."*.

## E. Resume bullet template (fill with YOUR real numbers)
"Built a SQLite/Python pipeline that ingested [N] CFPB consumer-complaint records, ran [23] SQL data quality rules
(completeness, uniqueness, validity, consistency) with documented pass/fail thresholds, and published CSV/Markdown reports and a Streamlit dashboard; tested with a synthetic dataset of injected defects ([55] automated tests)."
