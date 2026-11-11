# Windows + VS Code setup and run guide

All commands are for **PowerShell** (VS Code: `Ctrl + ~`). Run them from the project root
(the folder that contains `src`, `sql`, `tests`).

## 1. One-time setup

```powershell
python --version                     # 3.10 or newer
cd path\to\consumer-complaints-data-quality
python -m venv .venv
.venv\Scripts\Activate.ps1           # prompt now starts with (.venv)
python -m pip install --upgrade pip
pip install -r requirements.txt
```

In VS Code: `Ctrl+Shift+P` -> **Python: Select Interpreter** -> choose the one in `.venv`.

## 2. Check that everything works BEFORE downloading real data

```powershell
pytest -q
```
Expected: `55 passed` (the tests use only synthetic data and temporary databases).

## 3. Download the real CFPB extract

1. Open https://www.consumerfinance.gov/data-research/consumer-complaints/
2. Use the search/filter tool to select a **date range** (e.g. 1 Jan 2024 - 31 Dec 2024) and optionally a product.
3. **Export data -> CSV -> Filtered results**.
4. Save as `data\raw\complaints_sample.csv`. Do not open it in Excel (it can rewrite dates and IDs).
5. Record what you downloaded (see "Dataset log" in the README).

## 4. Run the pipeline (one command)

```powershell
python src/run_pipeline.py --csv data/raw/complaints_sample.csv
```

Then:

```powershell
streamlit run dashboard/app.py       # opens http://localhost:8501
```

Individual stages (for learning / debugging):

| Command | Does |
|---|---|
| `python src/ingest.py --csv data/raw/complaints_sample.csv --inspect` | CSV -> SQLite only |
| `python src/profile_data.py` | profiling queries, prints + CSVs |
| `python src/validate_data.py` | validation rules only |
| `python src/analysis.py` | analysis queries |
| `python src/generate_report.py` | rebuild reports from the latest run |
| `python src/run_pipeline.py --skip-ingest` | re-run everything except loading |

## 5. Look at the database yourself

Install **DB Browser for SQLite** (sqlitebrowser.org), open `database\complaints.db`, go to
*Execute SQL* and paste queries from `sql/`. Queries containing `:top_n`, `:min_complaints`,
`:min_date` or `:today` need those replaced with literal values (e.g. `10`, `100`,
`'2011-12-01'`, `'2026-11-11'`). Close DB Browser before re-running ingestion (it can lock the file).

## 6. Common problems

| Symptom | Fix |
|---|---|
| `running scripts is disabled` when activating | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, retry |
| `python` not recognised | reinstall Python with "Add to PATH" ticked, or use `py` instead of `python` |
| `ModuleNotFoundError: pandas/streamlit` | the venv is not active - run `.venv\Scripts\Activate.ps1`, then `pip install -r requirements.txt` |
| `ModuleNotFoundError: src` | run commands from the project root, not from inside `src` |
| `INGEST ERROR: CSV not found` | the file is not at `data\raw\complaints_sample.csv`; pass `--csv` with the right path |
| `INGEST ERROR: missing required column(s)` | the file is not a standard CFPB export; check its header row |
| `database is locked` | close DB Browser / any other program using `complaints.db` |
| `MemoryError` on a huge file | use `--chunk-size 20000`, or download a smaller filtered extract |
| Dashboard says "Database not found" | run the pipeline first; confirm the path in the sidebar |
| Many DQ-016..018 failures on real data | read the failing samples first - they are real findings, not bugs |
