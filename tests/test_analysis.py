"""Tests for the daily trend query (A02) - SYNTHETIC data only."""

import datetime

from src.analysis import run_analysis


def test_daily_trend_counts_match_database(conn):
    results = run_analysis(conn)
    block, daily = results["A02_daily_trend"]
    valid_dates = conn.execute("SELECT COUNT(*) FROM v_complaints WHERE date_received IS NOT NULL").fetchone()[0]
    assert daily["complaints"].sum() == valid_dates          # nothing lost or invented
    assert daily["received_date"].is_unique                   # exactly one row per day
    assert list(daily["received_date"]) == sorted(daily["received_date"])


def test_daily_trend_weekday_labels_are_correct(conn):
    _, daily = run_analysis(conn)["A02_daily_trend"]
    for row in daily.itertuples():
        expected = datetime.date.fromisoformat(row.received_date).strftime("%a")
        assert row.weekday == expected


def test_daily_trend_excludes_invalid_dates(conn):
    _, daily = run_analysis(conn)["A02_daily_trend"]
    assert "2024-13-45" not in set(daily["received_date"])
