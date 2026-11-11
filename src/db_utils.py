"""
db_utils.py - small shared helpers used by every other module.

What it does
------------
* connect()            open a SQLite connection (optionally read-only).
* parse_sql_blocks()   split a .sql file into named queries using "-- @id:" tags.
* run_query_blocks()   run every query in a .sql file and return DataFrames.
* create_run() / finish_run()   write the pipeline_runs audit row.

How it touches the database
---------------------------
It only opens connections and runs the SQL it is given. It never creates the
data tables itself (that is ingest.py's job, using sql/schema.sql).

This file is a library, not a script: you do not run it directly.
"""

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

# A metadata line looks like:   -- @name: Missing complaint ID
_META_RE = re.compile(r"^--\s*@(\w+):\s*(.*?)\s*$")


def connect(db_path, read_only=False):
    """Open a SQLite connection.

    read_only=True is used by the dashboard so it can never modify the data.
    Path.as_uri() produces a valid "file:///C:/..." URI on Windows as well.
    """
    path = Path(db_path).resolve()
    if read_only:
        if not path.exists():
            raise FileNotFoundError(f"Database not found: {path}")
        return sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(path))


def read_text(path):
    """Read a text file as UTF-8."""
    return Path(path).read_text(encoding="utf-8")


def parse_sql_blocks(text):
    """Split SQL text into blocks, each introduced by '-- @id: <ID>'.

    Lines such as '-- @name: ...' directly after the id become metadata keys.
    Everything else in the block is the SQL statement (ordinary '--' comments
    are fine). Text before the first @id (the file header) is ignored.

    Returns a list of dicts: {'id': ..., '<metadata keys>': ..., 'sql': ...}
    """
    blocks, current = [], None
    for line in text.splitlines():
        match = _META_RE.match(line.strip())
        if match:
            key, value = match.group(1).lower(), match.group(2)
            if key == "id":
                if current:
                    blocks.append(current)
                current = {"id": value, "_lines": []}
            elif current is not None:
                current[key] = value
            continue
        if current is not None:
            current["_lines"].append(line)
    if current:
        blocks.append(current)

    for block in blocks:
        lines = block.pop("_lines")
        # drop trailing blank / comment-only lines, then the final semicolon
        while lines and (not lines[-1].strip() or lines[-1].strip().startswith("--")):
            lines.pop()
        sql = "\n".join(lines).strip().rstrip(";").strip()
        block["sql"] = sql
    return blocks


def run_query_blocks(conn, sql_path, params=None):
    """Run every query block in a .sql file.

    Returns a list of (block_metadata, DataFrame). A query that fails raises
    sqlite3.Error with the query id added, so the problem is easy to find.
    """
    results = []
    for block in parse_sql_blocks(read_text(sql_path)):
        try:
            frame = pd.read_sql_query(block["sql"], conn, params=params or {})
        except Exception as exc:  # add the query id to the message
            raise sqlite3.Error(f"Query {block['id']} failed: {exc}") from exc
        results.append((block, frame))
    return results


def now_iso():
    """Current local time as an ISO-8601 string (second precision)."""
    return datetime.now().isoformat(timespec="seconds")


def create_run(conn, source_file, dataset_label):
    """Insert a RUNNING row in pipeline_runs and return its run_id."""
    cursor = conn.execute(
        "INSERT INTO pipeline_runs (started_at, status, source_file, dataset_label) "
        "VALUES (?, 'RUNNING', ?, ?)",
        (now_iso(), str(source_file), dataset_label),
    )
    conn.commit()
    return cursor.lastrowid


def finish_run(conn, run_id, status, duration_seconds, total_rows=None,
               results=None, stage_timings=None, error_message=None):
    """Complete a pipeline_runs row with totals computed from rule results."""
    passed = failed = errored = total = None
    pass_pct = None
    if results is not None:
        total = len(results)
        passed = sum(1 for r in results if r.status == "PASS")
        failed = sum(1 for r in results if r.status == "FAIL")
        errored = sum(1 for r in results if r.status == "ERROR")
        pass_pct = round(100.0 * passed / total, 2) if total else None
    conn.execute(
        "UPDATE pipeline_runs SET finished_at = ?, duration_seconds = ?, status = ?, "
        "total_rows = ?, rules_total = ?, rules_passed = ?, rules_failed = ?, "
        "rules_errored = ?, pass_pct = ?, stage_timings = ?, error_message = ? "
        "WHERE run_id = ?",
        (now_iso(), round(duration_seconds, 3), status, total_rows, total, passed,
         failed, errored, pass_pct,
         json.dumps(stage_timings) if stage_timings else None,
         error_message, run_id),
    )
    conn.commit()
