"""
analysis.py - Stage 4: SQL-based analysis reports.

Purpose
-------
Runs every query in sql/analysis.sql (complaints by product, daily trend,
top companies, by state, response distribution, timely-response %, joins...)
and exports each result to reports/analysis/<id>.csv.

Database use: read-only SELECTs on v_complaints and ref_states. Parameters
(:top_n, :min_complaints) are passed as named SQL parameters, never pasted
into the SQL text.

Run it
------
    python src/analysis.py
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import config  # noqa: E402
from src.db_utils import connect, run_query_blocks  # noqa: E402


def run_analysis(conn, params=None):
    """Return {query_id: (metadata, DataFrame)} for every analysis query."""
    merged = dict(config.ANALYSIS_PARAMS)
    merged.update(params or {})
    return {block["id"]: (block, frame)
            for block, frame in run_query_blocks(conn, config.ANALYSIS_SQL, merged)}


def export_analysis(results, reports_dir=config.REPORTS_DIR):
    """Write each analysis DataFrame to CSV; returns the list of written paths."""
    out_dir = Path(reports_dir) / "analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for query_id, (_, frame) in results.items():
        path = out_dir / f"{query_id}.csv"
        frame.to_csv(path, index=False)
        paths.append(path)
    return paths


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run SQL analysis reports.")
    parser.add_argument("--db", default=str(config.DATABASE_PATH))
    parser.add_argument("--reports-dir", default=str(config.REPORTS_DIR))
    parser.add_argument("--top-n", type=int, default=config.ANALYSIS_PARAMS["top_n"])
    parser.add_argument("--min-complaints", type=int, default=config.ANALYSIS_PARAMS["min_complaints"])
    args = parser.parse_args(argv)
    try:
        conn = connect(args.db, read_only=True)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}. Run src/ingest.py first.", file=sys.stderr)
        return 1
    try:
        results = run_analysis(conn, {"top_n": args.top_n, "min_complaints": args.min_complaints})
    finally:
        conn.close()
    for query_id, (block, frame) in results.items():
        print(f"\n=== {query_id}: {block.get('title', '')} ===")
        print(frame.head(10).to_string(index=False))
    export_analysis(results, args.reports_dir)
    print(f"\nExported {len(results)} analysis tables to {Path(args.reports_dir) / 'analysis'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
