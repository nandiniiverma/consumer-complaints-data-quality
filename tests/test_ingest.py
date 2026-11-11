"""Tests for Stage 1 (ingestion) - SYNTHETIC data only."""

import csv
import sqlite3

import pytest

from src.ingest import IngestError, ingest_csv, normalise_header
from tests.synthetic_data import HEADER, SYNTHETIC_CSV, TOTAL_ROWS


def test_successful_ingestion_loads_every_row(tmp_path):
    result = ingest_csv(SYNTHETIC_CSV, tmp_path / "t.db", chunk_size=1000, log=lambda *_: None)
    assert result.rows_read == TOTAL_ROWS
    assert result.rows_loaded == TOTAL_ROWS
    with sqlite3.connect(str(tmp_path / "t.db")) as db:
        assert db.execute("SELECT COUNT(*) FROM complaints_raw").fetchone()[0] == TOTAL_ROWS


def test_database_tables_and_view_are_created(conn):
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
    expected = {"complaints_raw", "v_complaints", "ref_states", "ref_valid_values",
                "ingestion_log", "pipeline_runs", "validation_results", "validation_samples"}
    assert expected <= names


def test_complaints_raw_has_all_18_source_columns_plus_row_id_and_original_date_columns(conn):
    columns = [r[1] for r in conn.execute("PRAGMA table_info(complaints_raw)")]
    assert columns[0] == "row_id"
    assert len(columns) == 21  # row_id + 18 source + 2 *_original date columns


def test_chunking_gives_identical_result(tmp_path):
    ingest_csv(SYNTHETIC_CSV, tmp_path / "a.db", chunk_size=7, log=lambda *_: None)
    ingest_csv(SYNTHETIC_CSV, tmp_path / "b.db", chunk_size=100000, log=lambda *_: None)
    query = "SELECT * FROM complaints_raw ORDER BY row_id"
    with sqlite3.connect(str(tmp_path / "a.db")) as a, sqlite3.connect(str(tmp_path / "b.db")) as b:
        assert a.execute(query).fetchall() == b.execute(query).fetchall()


def test_raw_values_are_preserved_and_only_empty_fields_become_null(conn):
    # trailing space and wrong case must survive untouched
    assert conn.execute("SELECT COUNT(*) FROM complaints_raw WHERE product = 'Mortgage '").fetchone()[0] == 1
    # an invalid date is kept as the original text, not converted or dropped
    assert conn.execute("SELECT COUNT(*) FROM complaints_raw WHERE date_received = '2024-13-45'").fetchone()[0] == 1
    # empty CSV fields -> NULL; whitespace-only fields are NOT altered
    assert conn.execute("SELECT COUNT(*) FROM complaints_raw WHERE complaint_id IS NULL").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM complaints_raw WHERE company = '   '").fetchone()[0] == 1
    # "N/A" must stay the literal text, not become missing
    assert conn.execute("SELECT COUNT(*) FROM complaints_raw WHERE consumer_disputed = 'N/A'").fetchone()[0] > 0


def test_ingestion_is_logged_with_actual_counts(synthetic_db):
    with sqlite3.connect(str(synthetic_db)) as db:
        rows_read, rows_loaded, sha = db.execute(
            "SELECT rows_read, rows_loaded, source_sha256 FROM ingestion_log").fetchone()
    assert rows_read == rows_loaded == TOTAL_ROWS
    assert len(sha) == 64


def test_reingesting_replaces_rather_than_duplicates(tmp_path):
    db = tmp_path / "again.db"
    ingest_csv(SYNTHETIC_CSV, db, log=lambda *_: None)
    ingest_csv(SYNTHETIC_CSV, db, log=lambda *_: None)
    with sqlite3.connect(str(db)) as c:
        assert c.execute("SELECT COUNT(*) FROM complaints_raw").fetchone()[0] == TOTAL_ROWS
        assert c.execute("SELECT COUNT(*) FROM ingestion_log").fetchone()[0] == 2


def test_missing_required_column_is_rejected(tmp_path):
    bad = tmp_path / "bad.csv"
    header = [h for h in HEADER if h != "Company"]
    with open(bad, "w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerows([header, ["x"] * len(header)])
    with pytest.raises(IngestError, match="company"):
        ingest_csv(bad, tmp_path / "x.db", log=lambda *_: None)


def test_missing_file_gives_clear_error(tmp_path):
    with pytest.raises(IngestError, match="CSV not found"):
        ingest_csv(tmp_path / "nope.csv", tmp_path / "x.db", log=lambda *_: None)


@pytest.mark.parametrize("raw, expected", [
    ("Date received", "date_received"),
    ("Sub-product", "sub_product"),
    ("Consumer consent provided?", "consumer_consent_provided"),
    ("Timely response?", "timely_response"),
    ("ZIP code", "zip_code"),
    ("Complaint ID", "complaint_id"),
])
def test_header_normalisation(raw, expected):
    assert normalise_header(raw) == expected


# ---------------------------------------------------------------------------
# Date normalisation (the real CFPB export may use MM/DD/YYYY or MM/DD/YY)
# ---------------------------------------------------------------------------
import pandas as pd  # noqa: E402

from src.ingest import normalise_date  # noqa: E402
from src.validate_data import run_all_validations  # noqa: E402
from tests.synthetic_data import ALLOWED_TODAY, CLEAN_CSV  # noqa: E402


@pytest.mark.parametrize("raw, expected, rewritten", [
    ("2024-03-09", "2024-03-09", False),   # ISO stays as is
    ("03/09/2024", "2024-03-09", True),    # US 4-digit year
    ("3/9/2024", "2024-03-09", True),      # no zero padding
    ("03/09/24", "2024-03-09", True),      # 2-digit year read as 20YY
    ("13/45/2024", "13/45/2024", False),   # impossible: left as written
    ("02/30/2024", "02/30/2024", False),   # impossible calendar day: left as written
    ("05-Dec-2024", "05-Dec-2024", False), # unrecognised format: left as written
    ("", "", False),
    # ISO 8601 timestamps as in the real CFPB filtered CSV export
    ("2024-12-23T11:23:45.000Z", "2024-12-23", True),
    ("2024-12-20T01:17:30.000Z", "2024-12-20", True),   # date as written, no time-zone shift
    ("2024-12-23 11:23:45", "2024-12-23", True),
    ("2024-02-30T10:00:00.000Z", "2024-02-30T10:00:00.000Z", False),   # impossible day
    ("2024-12-23T25:00:00.000Z", "2024-12-23T25:00:00.000Z", False),   # impossible hour
])
def test_normalise_date(raw, expected, rewritten):
    assert normalise_date(raw) == (expected, rewritten)


def test_normalise_date_handles_none():
    assert normalise_date(None) == (None, False)


def test_us_style_file_ingests_as_iso_and_keeps_originals(tmp_path):
    """A whole file written with MM/DD/YYYY dates must pass the date rules."""
    frame = pd.read_csv(CLEAN_CSV, dtype=str, keep_default_na=False)
    for column in ("Date received", "Date sent to company"):
        frame[column] = pd.to_datetime(frame[column]).dt.strftime("%m/%d/%Y")
    us_csv = tmp_path / "SYNTHETIC_us_dates.csv"
    frame.to_csv(us_csv, index=False)

    db = tmp_path / "us.db"
    ingest_csv(us_csv, db, log=lambda *_: None)
    with sqlite3.connect(str(db)) as connection:
        stored, original = connection.execute(
            "SELECT date_received, date_received_original FROM complaints_raw ORDER BY row_id LIMIT 1"
        ).fetchone()
        assert len(stored) == 10 and stored[4] == "-"      # ISO
        assert original[2] == "/"                          # original text preserved
        results, _ = run_all_validations(connection, today=ALLOWED_TODAY, log=lambda *_: None)
    by_id = {r.rule_id: r for r in results}
    for rule in ("DQ-005", "DQ-006", "DQ-007", "DQ-008"):
        assert by_id[rule].failing_count == 0, rule


def test_unsupported_date_format_is_diagnosed_not_hidden(tmp_path):
    """Day-first dates (20/12/2025) are NOT converted; ingestion must say so and DQ-005 must fail."""
    frame = pd.read_csv(CLEAN_CSV, dtype=str, keep_default_na=False)
    frame["Date received"] = "20/12/2025"           # month 20 is impossible -> unrecognised
    bad_csv = tmp_path / "SYNTHETIC_dayfirst.csv"
    frame.to_csv(bad_csv, index=False)

    messages = []
    db = tmp_path / "dayfirst.db"
    ingest_csv(bad_csv, db, log=messages.append)
    assert any("DATE FORMAT" in m for m in messages)
    with sqlite3.connect(str(db)) as connection:
        stored, original = connection.execute(
            "SELECT date_received, date_received_original FROM complaints_raw LIMIT 1").fetchone()
        assert stored == original == "20/12/2025"    # raw value untouched
        results, _ = run_all_validations(connection, today=ALLOWED_TODAY, log=lambda *_: None)
    assert {r.rule_id: r for r in results}["DQ-005"].failing_count == len(frame)


def test_real_cfpb_export_layout_timestamps_and_15_columns(tmp_path):
    """Mimics the real filtered export: 15 columns (no narrative / consent / disputed),
    ISO timestamps with milliseconds and a trailing Z, and the literal text 'None' in Tags.
    SYNTHETIC rows - invented values, only the layout matches the real file."""
    header = ("Date received,Product,Sub-product,Issue,Sub-issue,Company public response,Company,State,"
              "ZIP code,Tags,Submitted via,Date sent to company,Company response to consumer,"
              "Timely response?,Complaint ID")
    rows = [
        "2024-12-23T11:23:45.000Z,Mortgage,,Struggling to pay mortgage,,,Synthetic Bank A,NJ,07093,None,Web,"
        "2024-12-23T11:26:32.000Z,Closed with explanation,Yes,9100001",
        "2024-12-20T01:17:30.000Z,Mortgage,,Struggling to pay mortgage,,,Synthetic Bank A,TX,75001,None,Web,"
        "2024-12-20T01:28:54.000Z,In progress,Yes,9100002",
        # defect: sent before received -> must still be flagged by DQ-008
        "2024-12-24T10:00:00.000Z,Mortgage,,Struggling to pay mortgage,,,Synthetic Bank A,CA,90001,None,Web,"
        "2024-12-23T10:00:00.000Z,In progress,Yes,9100003",
        # defect: impossible calendar date -> must still be flagged by DQ-005
        "2024-02-30T10:00:00.000Z,Mortgage,,Struggling to pay mortgage,,,Synthetic Bank A,CA,90001,None,Web,"
        "2024-12-23T10:00:00.000Z,In progress,Yes,9100004",
    ]
    csv_path = tmp_path / "SYNTHETIC_real_layout.csv"
    csv_path.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")

    db = tmp_path / "real_layout.db"
    result = ingest_csv(csv_path, db, log=lambda *_: None)
    assert result.rows_loaded == 4
    with sqlite3.connect(str(db)) as connection:
        stored = connection.execute(
            "SELECT date_received, date_received_original, date_sent_to_company FROM complaints_raw "
            "ORDER BY row_id LIMIT 1").fetchone()
        assert stored == ("2024-12-23", "2024-12-23T11:23:45.000Z", "2024-12-23")
        results, _ = run_all_validations(connection, today="2026-11-11", log=lambda *_: None)
    by_id = {r.rule_id: r for r in results}
    assert by_id["DQ-005"].failing_count == 1      # only the impossible 2024-02-30
    assert by_id["DQ-007"].failing_count == 0
    assert by_id["DQ-008"].failing_count == 1      # sent the day before received
