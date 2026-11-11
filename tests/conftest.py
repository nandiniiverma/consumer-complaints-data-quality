"""Shared fixtures. All tests use SYNTHETIC data and temporary databases only -
they never touch database/complaints.db or the real CFPB file."""

import sqlite3

import pytest

from src.ingest import ingest_csv
from src.validate_data import load_rules, run_all_validations
from tests.synthetic_data import ALLOWED_TODAY, CLEAN_CSV, SYNTHETIC_CSV, write_csv, \
    build_clean_rows, build_defective_rows


@pytest.fixture(scope="session", autouse=True)
def synthetic_files():
    """Make sure the synthetic CSVs exist (regenerated deterministically)."""
    write_csv(SYNTHETIC_CSV, build_defective_rows())
    write_csv(CLEAN_CSV, build_clean_rows())


@pytest.fixture(scope="session")
def synthetic_db(tmp_path_factory, synthetic_files):
    """Database ingested from the defective synthetic CSV."""
    db_path = tmp_path_factory.mktemp("db") / "synthetic.db"
    ingest_csv(SYNTHETIC_CSV, db_path, chunk_size=50, log=lambda *_: None)
    return db_path


@pytest.fixture()
def conn(synthetic_db):
    connection = sqlite3.connect(str(synthetic_db))
    yield connection
    connection.close()


@pytest.fixture(scope="session")
def results_by_id(synthetic_db):
    connection = sqlite3.connect(str(synthetic_db))
    results, total = run_all_validations(connection, today=ALLOWED_TODAY, log=lambda *_: None)
    connection.close()
    return {r.rule_id: r for r in results}


@pytest.fixture(scope="session")
def rules():
    return load_rules()
