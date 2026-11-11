"""Tests for Stage 3 (validation rules) - SYNTHETIC data only.

EXPECTED counts come from tests/synthetic_data.py, which derives them from the
defects deliberately injected (not from re-running the SQL).
"""

import sqlite3

import pytest

from src.ingest import ingest_csv
from src.validate_data import Rule, run_all_validations, run_rule
from tests.synthetic_data import (ALLOWED_TODAY, CLEAN_CSV, EXPECTED, EXPECTED_PASS,
                                  N_BASE, TOTAL_ROWS)


def test_rule_file_parses_into_23_unique_rules(rules):
    ids = [r.rule_id for r in rules]
    assert len(ids) == 23 and len(set(ids)) == 23
    assert set(ids) == set(EXPECTED)
    for rule in rules:
        assert rule.sql.upper().lstrip().startswith(("SELECT", "WITH"))
        assert rule.threshold_pct >= 0 and rule.description


@pytest.mark.parametrize("rule_id", sorted(EXPECTED))
def test_each_rule_flags_exactly_the_injected_defects(results_by_id, rule_id):
    result = results_by_id[rule_id]
    assert result.status != "ERROR", result.error
    assert result.failing_count == EXPECTED[rule_id]
    assert result.total_records == TOTAL_ROWS


def test_duplicate_detection(results_by_id, conn):
    assert results_by_id["DQ-003"].failing_count == 3
    ids = {d for _, d in results_by_id["DQ-003"].samples}
    assert ids == {"9000011", "9000012", "9000013"}   # IDs of source rows 10, 11, 12
    # only the surplus occurrence is flagged, never the first one
    flagged = {r for r, _ in results_by_id["DQ-003"].samples}
    first_rows = {r[0] for r in conn.execute(
        "SELECT MIN(row_id) FROM complaints_raw WHERE complaint_id IN ('9000011','9000012','9000013') GROUP BY complaint_id")}
    assert flagged.isdisjoint(first_rows)


def test_missing_value_detection_includes_whitespace_only(results_by_id):
    # DQ-004: 2 empty companies + 1 company of spaces only
    details = {row_id for row_id, _ in results_by_id["DQ-004"].samples}
    assert results_by_id["DQ-004"].failing_count == 3 and len(details) == 3
    assert results_by_id["DQ-001"].failing_count == 2   # missing complaint IDs
    assert results_by_id["DQ-011"].failing_count == 1   # missing product


def test_optional_blanks_are_not_failures(conn, results_by_id):
    # sub_product / sub_issue / narrative / tags are blank in every synthetic row
    # yet no rule reports them
    blank_sub_product = conn.execute(
        "SELECT COUNT(*) FROM complaints_raw WHERE sub_product IS NULL").fetchone()[0]
    assert blank_sub_product == TOTAL_ROWS
    assert not any("sub_product" in r.name.lower() for r in results_by_id.values())


def test_date_validation_rejects_impossible_and_misformatted_dates(results_by_id):
    flagged = {detail for _, detail in results_by_id["DQ-005"].samples}
    assert flagged == {"(null)", "2024-13-45", "2024-02-30", "05-Dec-2024"}
    assert {d for _, d in results_by_id["DQ-006"].samples} == {"1999-05-01", "2031-01-01"}
    assert {d for _, d in results_by_id["DQ-007"].samples} == {"(null)", "2024-99-99"}


def test_response_date_before_received_date(results_by_id):
    assert results_by_id["DQ-008"].failing_count == 2
    for _, detail in results_by_id["DQ-008"].samples:
        received, sent = detail.split(" -> ")
        assert sent < received


def test_state_rules_separate_invalid_from_missing(results_by_id):
    assert {d for _, d in results_by_id["DQ-009"].samples} == {"ZZ", "XX", "ca", "California"}
    assert results_by_id["DQ-010"].failing_count == 8


def test_threshold_logic_pass_and_fail(results_by_id):
    # DQ-010: 8/203 = 3.94 % <= 5 % tolerance -> PASS although records fail
    assert results_by_id["DQ-010"].status == "PASS"
    assert results_by_id["DQ-010"].failing_count > 0
    # zero-tolerance rules with failures -> FAIL
    for rule_id in set(EXPECTED) - EXPECTED_PASS:
        assert results_by_id[rule_id].status == "FAIL", rule_id


def test_clean_data_passes_every_rule(tmp_path):
    db = tmp_path / "clean.db"
    ingest_csv(CLEAN_CSV, db, log=lambda *_: None)
    with sqlite3.connect(str(db)) as connection:
        results, total = run_all_validations(connection, today=ALLOWED_TODAY, log=lambda *_: None)
    assert total == N_BASE
    assert all(r.status == "PASS" and r.failing_count == 0 for r in results), \
        [(r.rule_id, r.failing_count) for r in results if r.failing_count]


def test_broken_rule_is_reported_as_error_not_pass(conn):
    broken = Rule("DQ-999", "Broken", "Test", "Low", 0.0, "bad SQL on purpose",
                  "SELECT row_id, detail FROM table_that_does_not_exist")
    result = run_rule(conn, broken, TOTAL_ROWS, {"min_date": "2011-12-01", "today": ALLOWED_TODAY})
    assert result.status == "ERROR" and result.error
    assert result.failing_count is None


def test_empty_database_is_refused(tmp_path):
    db = tmp_path / "empty.db"
    ingest_csv(CLEAN_CSV, db, log=lambda *_: None)
    with sqlite3.connect(str(db)) as connection:
        connection.execute("DELETE FROM complaints_raw")
        with pytest.raises(ValueError, match="empty"):
            run_all_validations(connection, log=lambda *_: None)
