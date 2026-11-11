"""
run_pipeline.py - ONE COMMAND to run the whole pipeline.

Stages
------
1. Ingest      CSV -> SQLite complaints_raw            (src/ingest.py)
2. Profile     sql/profiling.sql -> reports/profiling  (src/profile_data.py)
3. Validate    sql/validation.sql -> validation_results (src/validate_data.py)
4. Analyse     sql/analysis.sql -> reports/analysis    (src/analysis.py)
5. Report      CSV + Markdown summaries                (src/generate_report.py)

Every run is recorded in pipeline_runs with the actual row count, rule totals
and the time each stage took. Errors are caught, logged to the run record and
reported with a clear message and a non-zero exit code.

Run it
------
    python src/run_pipeline.py --csv data/raw/complaints_sample.csv
    python src/run_pipeline.py --skip-ingest          # reuse the existing database
Options: --db --reports-dir --chunk-size --include-narrative --label --strict
Exit codes: 0 ok | 1 pipeline error | 2 (--strict only) some rule failed
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import config  # noqa: E402
from src.analysis import export_analysis, run_analysis  # noqa: E402
from src.db_utils import connect, create_run, finish_run  # noqa: E402
from src.generate_report import write_reports  # noqa: E402
from src.ingest import IngestError, ingest_csv  # noqa: E402
from src.profile_data import export_profiling, run_profiling  # noqa: E402
from src.validate_data import run_all_validations, save_results  # noqa: E402


def run_pipeline(csv_path, db_path=config.DATABASE_PATH, reports_dir=config.REPORTS_DIR,
                 chunk_size=config.CHUNK_SIZE, include_narrative=False, skip_ingest=False,
                 dataset_label="CFPB extract", today=None, log=print):
    """Run all stages. Returns (run_id, results). Raises on failure after recording it."""
    pipeline_start = time.perf_counter()
    timings = {}

    if not skip_ingest:
        log("\n[1/5] Ingesting CSV ...")
        t = time.perf_counter()
        ingest_csv(csv_path, db_path, chunk_size, include_narrative, log)
        timings["ingest"] = round(time.perf_counter() - t, 2)
    else:
        log("\n[1/5] Ingestion skipped (--skip-ingest): using the existing database.")

    conn = connect(db_path)
    run_id = create_run(conn, csv_path, dataset_label)
    try:
        log("\n[2/5] Profiling ...")
        t = time.perf_counter()
        profiling = run_profiling(conn)
        export_profiling(profiling, reports_dir)
        timings["profiling"] = round(time.perf_counter() - t, 2)

        log("\n[3/5] Validating (23 SQL rules) ...")
        t = time.perf_counter()
        results, total_rows = run_all_validations(conn, today=today, log=log)
        save_results(conn, run_id, results)
        timings["validation"] = round(time.perf_counter() - t, 2)

        log("\n[4/5] Running SQL analysis ...")
        t = time.perf_counter()
        export_analysis(run_analysis(conn), reports_dir)
        timings["analysis"] = round(time.perf_counter() - t, 2)

        # record the run now so the report can read it, then update with report time
        finish_run(conn, run_id, "SUCCESS", time.perf_counter() - pipeline_start,
                   total_rows, results, timings)

        log("\n[5/5] Writing reports ...")
        t = time.perf_counter()
        paths = write_reports(conn, run_id, reports_dir)
        timings["reporting"] = round(time.perf_counter() - t, 2)
        finish_run(conn, run_id, "SUCCESS", time.perf_counter() - pipeline_start,
                   total_rows, results, timings)
        for name, path in paths.items():
            log(f"  wrote {path}")
    except Exception as exc:
        finish_run(conn, run_id, "FAILED", time.perf_counter() - pipeline_start,
                   error_message=f"{type(exc).__name__}: {exc}")
        conn.close()
        raise
    conn.close()

    passed = sum(r.status == "PASS" for r in results)
    log("\n" + "=" * 60)
    log(f"Pipeline finished in {time.perf_counter() - pipeline_start:.1f}s | run_id={run_id}")
    log(f"Records processed : {total_rows:,}")
    log(f"Rules passed      : {passed} / {len(results)} ({100 * passed / len(results):.1f}%)")
    log(f"Stage timings (s) : {timings}")
    log("=" * 60)
    return run_id, results


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the complete data quality pipeline.")
    parser.add_argument("--csv", default=str(config.DEFAULT_CSV_PATH))
    parser.add_argument("--db", default=str(config.DATABASE_PATH))
    parser.add_argument("--reports-dir", default=str(config.REPORTS_DIR))
    parser.add_argument("--chunk-size", type=int, default=config.CHUNK_SIZE)
    parser.add_argument("--include-narrative", action="store_true")
    parser.add_argument("--skip-ingest", action="store_true")
    parser.add_argument("--label", default="CFPB extract",
                        help="dataset label stored with the run (use 'SYNTHETIC TEST DATA' for test data)")
    parser.add_argument("--today", default=None, help="override 'today' (YYYY-MM-DD) for the date-range rule")
    parser.add_argument("--strict", action="store_true", help="exit with code 2 if any rule fails")
    args = parser.parse_args(argv)

    try:
        _, results = run_pipeline(args.csv, args.db, args.reports_dir, args.chunk_size,
                                  args.include_narrative, args.skip_ingest, args.label, args.today)
    except IngestError as exc:
        print(f"\nINGEST ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # last-resort handler: clear message, non-zero exit
        print(f"\nPIPELINE FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    if args.strict and any(r.status != "PASS" for r in results):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
