"""Tests for report generation and the one-command pipeline - SYNTHETIC data only."""

import csv
import json
import sqlite3

import pandas as pd

from src.analysis import run_analysis
from src.profile_data import run_profiling
from src.run_pipeline import main as pipeline_main
from tests.synthetic_data import ALLOWED_TODAY, EXPECTED, SYNTHETIC_CSV, TOTAL_ROWS


def _run(tmp_path, extra=None):
    args = ["--csv", str(SYNTHETIC_CSV), "--db", str(tmp_path / "p.db"),
            "--reports-dir", str(tmp_path / "reports"), "--label", "SYNTHETIC TEST DATA",
            "--today", ALLOWED_TODAY] + (extra or [])
    return pipeline_main(args)


def test_pipeline_runs_end_to_end_with_one_command(tmp_path, capsys):
    assert _run(tmp_path) == 0
    assert "Pipeline finished" in capsys.readouterr().out
    with sqlite3.connect(str(tmp_path / "p.db")) as db:
        row = db.execute("SELECT status, total_rows, rules_total, rules_passed, rules_failed, "
                         "dataset_label, stage_timings, duration_seconds FROM pipeline_runs").fetchone()
    status, total, n_rules, passed, failed, label, timings, duration = row
    assert (status, total, n_rules, passed, failed) == ("SUCCESS", TOTAL_ROWS, 23, 1, 22)
    assert label == "SYNTHETIC TEST DATA"
    assert set(json.loads(timings)) == {"ingest", "profiling", "validation", "analysis", "reporting"}
    assert duration > 0


def test_report_files_are_created_and_consistent(tmp_path):
    _run(tmp_path)
    reports = tmp_path / "reports"
    for name in ("validation_results.csv", "validation_failure_samples.csv",
                 "data_quality_summary.md", "readme_results_snippet.md"):
        assert (reports / name).exists(), name

    with open(reports / "validation_results.csv", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 23
    assert {r["rule_id"]: int(r["failing_count"]) for r in rows} == EXPECTED
    assert [r["status"] for r in rows].count("PASS") == 1

    summary = (reports / "data_quality_summary.md").read_text(encoding="utf-8")
    assert "SYNTHETIC TEST DATA" in summary and "NOT CFPB results" in summary
    assert f"| {TOTAL_ROWS} |" in summary or f"Records processed | {TOTAL_ROWS}" in summary
    assert "DQ-003" in summary

    samples = pd.read_csv(reports / "validation_failure_samples.csv")
    assert samples["rule_id"].nunique() == 23


def test_profiling_and_analysis_exports(tmp_path):
    _run(tmp_path)
    assert len(list((tmp_path / "reports" / "profiling").glob("*.csv"))) == 9
    assert len(list((tmp_path / "reports" / "analysis").glob("*.csv"))) == 11


def test_profiling_numbers_match_known_synthetic_facts(synthetic_db):
    with sqlite3.connect(str(synthetic_db)) as db:
        profiling = run_profiling(db)
        analysis = run_analysis(db)
    overview = profiling["P01_overview"][1].iloc[0]
    assert overview["total_records"] == TOTAL_ROWS
    assert overview["unique_complaint_ids"] == 198        # 200 base IDs - 2 blank IDs
    duplicates = dict(profiling["P07_duplicates"][1].values)
    assert duplicates["surplus_rows_from_repeated_ids"] == 3
    assert duplicates["surplus_rows_exact_duplicates"] == 2   # two of the three duplicates are exact copies
    timely = analysis["A06_timely_response_overall"][1].iloc[0]
    assert timely["records_with_timely_flag"] == timely["timely"] + timely["not_timely"]
    assert timely["records_with_timely_flag"] == TOTAL_ROWS - 3   # blank, 'Maybe', 'yes' excluded
    # LEFT JOIN anti-join finds exactly the four injected bad state codes
    bad_states = set(analysis["A10_unrecognised_state_codes"][1]["state_value"])
    assert bad_states == {"ZZ", "XX", "ca", "California"}


def test_pipeline_fails_gracefully_on_missing_csv(tmp_path, capsys):
    code = pipeline_main(["--csv", str(tmp_path / "missing.csv"), "--db", str(tmp_path / "x.db"),
                          "--reports-dir", str(tmp_path / "r")])
    assert code == 1
    assert "INGEST ERROR" in capsys.readouterr().err


def test_strict_mode_returns_exit_code_2_when_rules_fail(tmp_path):
    assert _run(tmp_path, ["--strict"]) == 2
