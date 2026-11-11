"""
ingest.py - Stage 1: load the CFPB CSV into SQLite, preserving the raw data.

Purpose
-------
1. Inspect the CSV header (and show what Pandas would guess for data types).
2. Create the SQLite database and tables from sql/schema.sql.
3. Load the CSV in chunks into complaints_raw. Everything is read as TEXT
   (dtype=str, no automatic NA conversion) so nothing is silently altered.
   Two changes only: an empty CSV field is stored as NULL, and the two date
   columns are rewritten to ISO (YYYY-MM-DD) when they are real ISO timestamps
   (2024-12-23T11:23:45.000Z) or MM/DD/YYYY / MM/DD/YY dates; the exact original text is kept in *_original columns.
4. Load the reference tables (states, valid category values).
5. Record the ACTUAL number of rows read and loaded in ingestion_log.

How it uses the database
------------------------
Re-running ingestion REPLACES complaints_raw and the reference tables, so the
database always mirrors the CSV you point it at. Audit tables are kept.

Run it
------
    python src/ingest.py --csv data/raw/complaints_sample.csv
Options: --db PATH  --chunk-size N  --include-narrative
"""

import argparse
import csv
import hashlib
import re
import sys
import time
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

# Allow "python src/ingest.py" as well as "python -m src.ingest"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from src import config  # noqa: E402
from src.db_utils import connect, now_iso, read_text  # noqa: E402


class IngestError(Exception):
    """Raised for problems the user can fix (missing file, wrong columns...)."""


@dataclass
class IngestResult:
    csv_path: str
    db_path: str
    rows_read: int
    rows_loaded: int
    columns_in_file: int
    duration_seconds: float
    sha256: str
    notes: str


def normalise_header(name):
    """'Consumer consent provided?' -> 'consumer_consent_provided'."""
    cleaned = re.sub(r"[^0-9a-zA-Z]+", "_", str(name).strip().lower())
    return cleaned.strip("_")


def file_sha256(path, block_size=1024 * 1024):
    """SHA-256 fingerprint of the file, recorded so results can be tied to an exact input."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_columns(csv_path, include_narrative, log=print):
    """Read only the header row and map CSV column names to database column names.

    Returns (mapping, notes) where mapping = {original_header: db_column}.
    Raises IngestError if a required column is missing.
    """
    try:
        header = pd.read_csv(csv_path, nrows=0, dtype=str, encoding="utf-8-sig").columns.tolist()
    except pd.errors.EmptyDataError as exc:
        raise IngestError(f"The file is empty: {csv_path}") from exc

    normalised = {}
    for original in header:
        db_name = normalise_header(original)
        if db_name in normalised.values():
            raise IngestError(f"Two CSV columns both normalise to '{db_name}'.")
        normalised[original] = db_name

    present = set(normalised.values())
    missing_required = [c for c in config.REQUIRED_FILE_COLUMNS if c not in present]
    if missing_required:
        raise IngestError(
            "The CSV is missing required column(s): " + ", ".join(missing_required)
            + ". Found headers: " + ", ".join(header)
        )

    wanted = set(config.DB_COLUMNS)
    if not include_narrative:
        wanted.discard(config.NARRATIVE_COLUMN)
    mapping = {orig: db for orig, db in normalised.items() if db in wanted}

    notes = []
    unexpected = sorted(present - set(config.DB_COLUMNS))
    if unexpected:
        notes.append("Ignored extra columns: " + ", ".join(unexpected))
    absent_optional = sorted(set(config.DB_COLUMNS) - present - {config.NARRATIVE_COLUMN})
    if absent_optional:
        notes.append("Optional columns absent from file (stored blank): " + ", ".join(absent_optional))
    for note in notes:
        log("  note: " + note)
    return mapping, "; ".join(notes)


def inspect_csv(csv_path, sample_rows=5000, log=print):
    """Print columns, the types Pandas would GUESS, and missing values in a sample.

    Educational: it shows why the pipeline loads everything as text instead of
    trusting type inference (e.g. ZIP codes or IDs would lose leading zeros).
    """
    sample = pd.read_csv(csv_path, nrows=sample_rows, encoding="utf-8-sig", low_memory=False)
    log(f"\nInspection of the first {len(sample):,} rows ({len(sample.columns)} columns):")
    summary = pd.DataFrame({
        "pandas_guessed_dtype": sample.dtypes.astype(str),
        "missing_in_sample": sample.isna().sum(),
    })
    log(summary.to_string())


_US_DATE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})$")
# ISO 8601 timestamp as in the CFPB filtered CSV export, e.g. 2024-12-23T11:23:45.000Z
_ISO_TIMESTAMP = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$")


@lru_cache(maxsize=None)
def normalise_date(value):
    """Return (text_to_store, was_rewritten).

    Recognised and rewritten to ISO 'YYYY-MM-DD' ONLY when they are real dates:
      * ISO 8601 timestamps such as '2024-12-23T11:23:45.000Z' (the CFPB filtered
        CSV export). The calendar date as written in the timestamp is kept; the
        time of day is dropped (and not converted between time zones).
      * 'MM/DD/YYYY' and 'MM/DD/YY' (US order, month first; 2-digit years = 20YY).
    Plain 'YYYY-MM-DD', blanks and anything unrecognised or impossible
    ('13/45/2024', '2024-02-30T10:00:00Z', '05-Dec-2024') are returned unchanged,
    so invalid dates still reach the validation rules. The exact original text
    is always kept separately in the *_original column.
    """
    if value is None:
        return value, False
    text = value.strip()
    try:
        match = _ISO_TIMESTAMP.match(text)
        if match:
            year, month, day, hour, minute, second = (int(g) for g in match.groups())
            if hour > 23 or minute > 59 or second > 59:
                return value, False
            return date(year, month, day).isoformat(), True
        match = _US_DATE.match(text)
        if match:
            month, day, year = int(match.group(1)), int(match.group(2)), match.group(3)
            year = int(year) + 2000 if len(year) == 2 else int(year)
            return date(year, month, day).isoformat(), True
    except ValueError:      # e.g. February 30th
        return value, False
    return value, False


def _normalise_date_columns(chunk):
    """Keep the original text, then ISO-normalise the date columns. Returns rewritten count."""
    rewritten = 0
    for column in config.DATE_COLUMNS:
        original = chunk[column]
        chunk[f"{column}_original"] = original
        converted = [normalise_date(v if v != "" else None) for v in original]
        chunk[column] = [text if text is not None else "" for text, _ in converted]
        rewritten += sum(1 for _, changed in converted if changed)
    return rewritten


def report_unrecognised_dates(conn, log=print):
    """Warn when date values could not be read as dates; returns {column: count}.

    This separates "the file uses a date format we do not recognise" (almost every
    row unrecognised) from "a few genuinely bad dates" (a handful of rows).
    Non-blank values only: blanks are counted by the validation rules instead.
    """
    counts = {}
    for column in config.DATE_COLUMNS:
        where = (f"{column} IS NOT NULL AND TRIM({column}) <> '' "
                 f"AND {column} NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'")
        bad = conn.execute(f"SELECT COUNT(*) FROM complaints_raw WHERE {where}").fetchone()[0]
        counts[column] = bad
        if bad:
            total = conn.execute("SELECT COUNT(*) FROM complaints_raw").fetchone()[0]
            examples = [r[0] for r in conn.execute(
                f"SELECT DISTINCT {column}_original FROM complaints_raw WHERE {where} LIMIT 5")]
            log(f"  WARNING: {bad:,} of {total:,} {column} values are not a recognised date "
                f"(examples: {examples}). Rules DQ-005/DQ-007 will flag them.")
            if total and bad / total > 0.5:
                log("  WARNING: more than half the values are unrecognised - this looks like an "
                    "unsupported DATE FORMAT, not bad data. Check the first rows of your CSV.")
    return counts


def _create_schema(conn):
    conn.executescript(read_text(config.SCHEMA_SQL))


def _load_reference_tables(conn):
    with open(config.STATES_CSV, newline="", encoding="utf-8") as handle:
        rows = [(r["code"], r["name"], r["category"]) for r in csv.DictReader(handle)]
    conn.executemany("INSERT INTO ref_states (code, name, category) VALUES (?, ?, ?)", rows)

    with open(config.CATEGORIES_CSV, newline="", encoding="utf-8") as handle:
        rows = [(r["column_name"], r["valid_value"]) for r in csv.DictReader(handle)]
    conn.executemany("INSERT INTO ref_valid_values (column_name, valid_value) VALUES (?, ?)", rows)


def _load_chunks(conn, csv_path, mapping, chunk_size, log=print):
    """Stream the CSV into complaints_raw; returns the number of data rows read."""
    stored_columns = config.DB_COLUMNS + config.ORIGINAL_DATE_COLUMNS
    insert_sql = (
        f"INSERT INTO complaints_raw ({', '.join(stored_columns)}) "
        f"VALUES ({', '.join('?' for _ in stored_columns)})"
    )
    reader = pd.read_csv(
        csv_path,
        usecols=list(mapping.keys()),
        dtype=str,              # keep everything as text
        keep_default_na=False,  # do NOT turn "NA", "N/A", "" into NaN
        na_values=[],
        encoding="utf-8-sig",
        chunksize=chunk_size,
    )
    rows_read = 0
    dates_rewritten = 0
    for chunk_number, chunk in enumerate(reader, start=1):
        chunk = chunk.rename(columns=mapping)
        # any column not in the file (or narrative when skipped) is stored blank
        chunk = chunk.reindex(columns=config.DB_COLUMNS, fill_value="").fillna("")
        dates_rewritten += _normalise_date_columns(chunk)
        records = [
            tuple(None if value == "" else value for value in row)
            for row in chunk.itertuples(index=False, name=None)
        ]
        conn.executemany(insert_sql, records)
        rows_read += len(records)
        log(f"  chunk {chunk_number}: {rows_read:,} rows loaded so far")
    if dates_rewritten:
        log(f"  note: {dates_rewritten:,} date values (timestamp or MM/DD/YY[YY]) were rewritten to ISO; "
            "originals are kept in the *_original columns.")
    return rows_read, dates_rewritten


def ingest_csv(csv_path=config.DEFAULT_CSV_PATH, db_path=config.DATABASE_PATH,
               chunk_size=config.CHUNK_SIZE, include_narrative=False, log=print):
    """Full ingestion. Returns an IngestResult; raises IngestError on user-fixable problems."""
    csv_path, db_path = Path(csv_path), Path(db_path)
    if not csv_path.exists():
        raise IngestError(
            f"CSV not found: {csv_path}\n"
            "Download a CFPB extract (see README, 'Dataset') and save it there, or pass --csv PATH."
        )
    if chunk_size < 1:
        raise IngestError("chunk_size must be at least 1.")

    started = time.perf_counter()
    log(f"Ingesting {csv_path} -> {db_path}")
    mapping, notes = resolve_columns(csv_path, include_narrative, log)
    sha256 = file_sha256(csv_path)

    conn = connect(db_path)
    try:
        conn.execute("PRAGMA synchronous = OFF")  # safe: the DB can always be rebuilt from the CSV
        _create_schema(conn)
        _load_reference_tables(conn)
        try:
            rows_read, dates_rewritten = _load_chunks(conn, csv_path, mapping, chunk_size, log)
            if dates_rewritten:
                notes = (notes + "; " if notes else "") + (
                    f"{dates_rewritten:,} timestamp / MM/DD/YY[YY] date values rewritten to ISO (originals kept)")
        except (pd.errors.ParserError, UnicodeDecodeError) as exc:
            raise IngestError(f"Could not parse the CSV ({exc}). Is it the original CFPB file?") from exc
        conn.commit()

        conn.executescript(read_text(config.INDEXES_SQL))
        report_unrecognised_dates(conn, log)

        rows_loaded = conn.execute("SELECT COUNT(*) FROM complaints_raw").fetchone()[0]
        if rows_loaded != rows_read:
            raise IngestError(f"Row mismatch: read {rows_read:,} but table holds {rows_loaded:,}.")

        duration = time.perf_counter() - started
        conn.execute(
            "INSERT INTO ingestion_log (ingested_at, source_file, source_sha256, file_size_bytes, "
            "columns_in_file, rows_read, rows_loaded, narrative_included, chunk_size, "
            "duration_seconds, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (now_iso(), str(csv_path), sha256, csv_path.stat().st_size, len(mapping),
             rows_read, rows_loaded, int(include_narrative), chunk_size, round(duration, 3), notes),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    log(f"Done: {rows_loaded:,} rows loaded in {duration:.1f}s (verified with COUNT(*)).")
    return IngestResult(str(csv_path), str(db_path), rows_read, rows_loaded,
                        len(mapping), duration, sha256, notes)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Load a CFPB complaints CSV into SQLite.")
    parser.add_argument("--csv", default=str(config.DEFAULT_CSV_PATH), help="path to the CSV")
    parser.add_argument("--db", default=str(config.DATABASE_PATH), help="SQLite database path")
    parser.add_argument("--chunk-size", type=int, default=config.CHUNK_SIZE)
    parser.add_argument("--include-narrative", action="store_true",
                        help="also load the (large) consumer narrative column")
    parser.add_argument("--inspect", action="store_true", help="print a column/type inspection first")
    args = parser.parse_args(argv)
    try:
        if args.inspect and Path(args.csv).exists():
            inspect_csv(args.csv)
        ingest_csv(args.csv, args.db, args.chunk_size, args.include_narrative)
    except IngestError as exc:
        print(f"\nINGEST ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
