"""
validate_data.py - Stage 3: run the SQL data quality rules.

Purpose
-------
Reads the rules in sql/validation.sql. Each rule is one SELECT that returns the
FAILING records (row_id, detail). For every rule this module:
  1. counts the failing records (SELECT COUNT(*) FROM (<rule>)),
  2. converts the count to a % of all records,
  3. compares it with the rule's @threshold_pct -> PASS or FAIL,
  4. keeps a few example failing records,
  5. saves everything to validation_results / validation_samples.
A rule whose SQL raises an error is recorded as ERROR (it never crashes the run
and is never silently counted as PASS).

Run it standalone
-----------------
    python src/validate_data.py
(run_pipeline.py is the normal entry point and calls run_all_validations()).
"""

import argparse
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import config  # noqa: E402
from src.db_utils import (connect, create_run, finish_run,  # noqa: E402
                          parse_sql_blocks, read_text)

REQUIRED_RULE_FIELDS = ("name", "category", "severity", "threshold_pct", "description")


@dataclass
class Rule:
    rule_id: str
    name: str
    category: str
    severity: str
    threshold_pct: float
    description: str
    sql: str


@dataclass
class RuleResult:
    rule_id: str
    name: str
    category: str
    severity: str
    threshold_pct: float
    description: str
    total_records: int
    failing_count: int = 0
    failing_pct: float = 0.0
    status: str = "PASS"
    explanation: str = ""
    execution_ms: float = 0.0
    error: str = ""
    samples: list = field(default_factory=list)


def load_rules(path=config.VALIDATION_SQL):
    """Parse validation.sql into Rule objects and sanity-check the metadata."""
    rules, seen = [], set()
    for block in parse_sql_blocks(read_text(path)):
        missing = [k for k in REQUIRED_RULE_FIELDS if k not in block]
        if missing:
            raise ValueError(f"Rule {block['id']} is missing metadata: {', '.join(missing)}")
        if block["id"] in seen:
            raise ValueError(f"Duplicate rule id {block['id']}")
        seen.add(block["id"])
        rules.append(Rule(block["id"], block["name"], block["category"], block["severity"],
                          float(block["threshold_pct"]), block["description"], block["sql"]))
    if not rules:
        raise ValueError(f"No rules found in {path}")
    return rules


def _explain(status, rule, count, pct, total):
    if status == "ERROR":
        return "The rule could not be executed; see error message."
    if count == 0:
        return "No records failed this check."
    base = f"{count:,} of {total:,} records ({pct:.2f}%) fail this check. {rule.description}"
    if status == "PASS":
        return base + f" Within the allowed tolerance of {rule.threshold_pct:g}%."
    return base + f" Exceeds the allowed {rule.threshold_pct:g}%."


def run_rule(conn, rule, total_records, params, sample_limit=config.SAMPLE_FAILURES_PER_RULE):
    """Execute one rule and return a RuleResult. Never raises for SQL problems."""
    result = RuleResult(rule.rule_id, rule.name, rule.category, rule.severity,
                        rule.threshold_pct, rule.description, total_records)
    started = time.perf_counter()
    try:
        query_params = dict(params, sample_limit=sample_limit)
        result.failing_count = conn.execute(
            f"SELECT COUNT(*) FROM ({rule.sql})", query_params).fetchone()[0]
        result.samples = conn.execute(
            f"SELECT row_id, detail FROM ({rule.sql}) LIMIT :sample_limit", query_params).fetchall()
        result.failing_pct = round(100.0 * result.failing_count / total_records, 4)
        result.status = "PASS" if result.failing_pct <= rule.threshold_pct else "FAIL"
    except sqlite3.Error as exc:
        result.status, result.error = "ERROR", str(exc)
        result.failing_count, result.failing_pct = None, None
    result.execution_ms = round((time.perf_counter() - started) * 1000, 1)
    result.explanation = _explain(result.status, rule, result.failing_count,
                                  result.failing_pct, total_records)
    return result


def run_all_validations(conn, rules=None, today=None, min_date=config.MIN_VALID_DATE, log=print):
    """Run all rules; returns (list_of_RuleResult, total_records)."""
    rules = rules or load_rules()
    total = conn.execute("SELECT COUNT(*) FROM complaints_raw").fetchone()[0]
    if total == 0:
        raise ValueError("complaints_raw is empty - nothing to validate. Run ingestion first.")
    params = {"min_date": min_date, "today": today or date.today().isoformat()}
    results = []
    for rule in rules:
        result = run_rule(conn, rule, total, params)
        count = "n/a" if result.failing_count is None else f"{result.failing_count:,}"
        log(f"  {result.rule_id}  {result.status:5}  failing={count:>10}  {result.name}")
        results.append(result)
    return results, total


def save_results(conn, run_id, results):
    """Persist rule results and failure samples for a run."""
    conn.executemany(
        "INSERT OR REPLACE INTO validation_results (run_id, rule_id, rule_name, category, severity, "
        "threshold_pct, total_records, failing_count, failing_pct, status, description, explanation, "
        "execution_ms, error_message) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(run_id, r.rule_id, r.name, r.category, r.severity, r.threshold_pct, r.total_records,
          r.failing_count, r.failing_pct, r.status, r.description, r.explanation,
          r.execution_ms, r.error or None) for r in results])
    conn.execute("DELETE FROM validation_samples WHERE run_id = ?", (run_id,))
    conn.executemany(
        "INSERT INTO validation_samples (run_id, rule_id, row_id, detail) VALUES (?, ?, ?, ?)",
        [(run_id, r.rule_id, row_id, detail) for r in results for row_id, detail in r.samples])
    conn.commit()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run data quality validation rules.")
    parser.add_argument("--db", default=str(config.DATABASE_PATH))
    parser.add_argument("--label", default="CFPB extract", help="dataset label stored with the run")
    args = parser.parse_args(argv)
    try:
        conn = connect(args.db)
        conn.execute("SELECT 1 FROM complaints_raw LIMIT 1")
    except (FileNotFoundError, sqlite3.Error):
        print("ERROR: database or complaints_raw table not found. Run src/ingest.py first.", file=sys.stderr)
        return 1
    started = time.perf_counter()
    run_id = create_run(conn, args.db, args.label)
    try:
        results, total = run_all_validations(conn)
        save_results(conn, run_id, results)
        finish_run(conn, run_id, "SUCCESS", time.perf_counter() - started, total, results)
    except Exception as exc:
        finish_run(conn, run_id, "FAILED", time.perf_counter() - started, error_message=str(exc))
        print(f"VALIDATION ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()
    passed = sum(r.status == "PASS" for r in results)
    print(f"\n{passed}/{len(results)} rules passed (run_id={run_id}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
