"""
config.py - one place for paths, column definitions and default parameters.

Why this file exists
--------------------
Every other module imports its file paths and column lists from here, so there
is exactly one definition of "where does the database live?" and "which columns
are mandatory?". pathlib.Path is used everywhere, so the same code works on
Windows (backslashes) and Linux/macOS (forward slashes).

Nothing in this file touches the database or the dataset.
"""

from pathlib import Path

# --------------------------------------------------------------------------
# Paths (all relative to the project root, which is the parent of /src)
# --------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
REFERENCE_DIR = PROJECT_ROOT / "data" / "reference"
DATABASE_PATH = PROJECT_ROOT / "database" / "complaints.db"
SQL_DIR = PROJECT_ROOT / "sql"
REPORTS_DIR = PROJECT_ROOT / "reports"

DEFAULT_CSV_PATH = DATA_RAW_DIR / "complaints_sample.csv"

SCHEMA_SQL = SQL_DIR / "schema.sql"
INDEXES_SQL = SQL_DIR / "indexes.sql"
PROFILING_SQL = SQL_DIR / "profiling.sql"
VALIDATION_SQL = SQL_DIR / "validation.sql"
ANALYSIS_SQL = SQL_DIR / "analysis.sql"

STATES_CSV = REFERENCE_DIR / "us_states.csv"
CATEGORIES_CSV = REFERENCE_DIR / "valid_categories.csv"

# --------------------------------------------------------------------------
# Columns
# --------------------------------------------------------------------------
# Database column names, in the order they are stored in complaints_raw.
# A CSV header such as "Timely response?" is converted to "timely_response" by
# normalise_header() in ingest.py (lower-case, punctuation -> underscore).
DB_COLUMNS = [
    "date_received",
    "product",
    "sub_product",
    "issue",
    "sub_issue",
    "consumer_complaint_narrative",
    "company_public_response",
    "company",
    "state",
    "zip_code",
    "tags",
    "consumer_consent_provided",
    "submitted_via",
    "date_sent_to_company",
    "company_response_to_consumer",
    "timely_response",
    "consumer_disputed",
    "complaint_id",
]

# Date columns that ingest.py normalises to ISO (YYYY-MM-DD). The text exactly as
# it appeared in the CSV is kept in the matching "<column>_original" column.
DATE_COLUMNS = ["date_received", "date_sent_to_company"]
ORIGINAL_DATE_COLUMNS = [f"{c}_original" for c in DATE_COLUMNS]

# MANDATORY columns: every complaint record is expected to have a value.
# A blank here counts as a data quality failure (see sql/validation.sql).
MANDATORY_COLUMNS = [
    "complaint_id",
    "date_received",
    "product",
    "issue",
    "company",
    "submitted_via",
    "date_sent_to_company",
    "company_response_to_consumer",
    "timely_response",
]

# OPTIONAL columns: legitimately blank for many complaints (the consumer may
# not give a ZIP, may not consent to publishing a narrative, a product may have
# no sub-product, "Consumer disputed?" is no longer collected for new
# complaints, etc.). Blanks here are REPORTED in profiling but not treated as
# failures. State is a special case: it is optional but monitored with a
# tolerance threshold (rule DQ-010).
OPTIONAL_COLUMNS = [c for c in DB_COLUMNS if c not in MANDATORY_COLUMNS]

# Columns that must exist in the CSV header. If one is missing the file is not
# a CFPB complaint extract (or the CFPB changed its format) and ingestion stops.
REQUIRED_FILE_COLUMNS = MANDATORY_COLUMNS + ["state"]

# The consumer narrative is large and not needed for any check, so it is not
# loaded unless you pass --include-narrative to ingest.py.
NARRATIVE_COLUMN = "consumer_complaint_narrative"

# --------------------------------------------------------------------------
# Default parameters
# --------------------------------------------------------------------------
# Earliest plausible complaint date. The public database starts in December
# 2011 - confirm against the MIN date your profiling query reports.
MIN_VALID_DATE = "2011-12-01"

# Parameters for sql/analysis.sql
ANALYSIS_PARAMS = {"top_n": 10, "min_complaints": 100}

CHUNK_SIZE = 50_000
SAMPLE_FAILURES_PER_RULE = 5
