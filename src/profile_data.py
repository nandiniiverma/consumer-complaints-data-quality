"""
profile_data.py - Stage 2: data profiling / discovery.

Purpose
-------
Runs every query in sql/profiling.sql against the database and exports each
result as reports/profiling/<id>.csv. Profiling DESCRIBES the data (counts,
missing values, distributions, duplicates); it does not pass or fail anything.

Database use: read-only SELECTs on complaints_raw, v_complaints, ref_states.

Run it
------
    python src/profile_data.py
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import config  # noqa: E402
from src.db_utils import connect, run_query_blocks  # noqa: E402


def run_profiling(conn):
    """Return {query_id: (metadata, DataFrame)} for every profiling query."""
    return {block["id"]: (block, frame)
            for block, frame in run_query_blocks(conn, config.PROFILING_SQL)}


def export_profiling(results, reports_dir=config.REPORTS_DIR):
    """Write each profiling DataFrame to CSV; returns the list of written paths."""
    out_dir = Path(reports_dir) / "profiling"
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for query_id, (_, frame) in results.items():
        path = out_dir / f"{query_id}.csv"
        frame.to_csv(path, index=False)
        paths.append(path)
    return paths


def main(argv=None):
    parser = argparse.ArgumentParser(description="Profile the complaints database.")
    parser.add_argument("--db", default=str(config.DATABASE_PATH))
    parser.add_argument("--reports-dir", default=str(config.REPORTS_DIR))
    args = parser.parse_args(argv)
    try:
        conn = connect(args.db, read_only=True)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}. Run src/ingest.py first.", file=sys.stderr)
        return 1
    try:
        results = run_profiling(conn)
    finally:
        conn.close()
    for query_id, (block, frame) in results.items():
        print(f"\n=== {query_id}: {block.get('title', '')} ===")
        print(frame.head(12).to_string(index=False))
    export_profiling(results, args.reports_dir)
    print(f"\nExported {len(results)} profiling tables to {Path(args.reports_dir) / 'profiling'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
