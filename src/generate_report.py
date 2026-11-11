"""
generate_report.py - Stage 5 (part): turn stored validation results into reports.

Purpose
-------
Reads a pipeline run from the database and writes:
  reports/validation_results.csv        one row per rule
  reports/validation_failure_samples.csv   example failing records per rule
  reports/data_quality_summary.md       human-readable summary
  reports/readme_results_snippet.md     a ready-to-paste "Actual results" section
Every number comes from the database; nothing is typed in by hand.

Run it
------
    python src/generate_report.py            # latest successful run
    python src/generate_report.py --run-id 3
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from src import config  # noqa: E402
from src.analysis import run_analysis  # noqa: E402
from src.db_utils import connect  # noqa: E402
from src.profile_data import run_profiling  # noqa: E402


def _cell(value):
    """Format a value for a Markdown table cell."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "n/a"
    if isinstance(value, float):
        return f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value).replace("|", "\\|").replace("\n", " ")


def md_table(headers, rows):
    """Render a simple Markdown table (no extra dependencies)."""
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(_cell(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


def load_run(conn, run_id=None):
    """Return the pipeline_runs row (as dict) for run_id, or the latest SUCCESS run."""
    conn.row_factory = None
    cursor = conn.cursor()
    if run_id is None:
        cursor.execute("SELECT * FROM pipeline_runs WHERE status = 'SUCCESS' ORDER BY run_id DESC LIMIT 1")
    else:
        cursor.execute("SELECT * FROM pipeline_runs WHERE run_id = ?", (run_id,))
    row = cursor.fetchone()
    if row is None:
        raise LookupError("No matching pipeline run found. Run src/run_pipeline.py first.")
    return dict(zip([c[0] for c in cursor.description], row))


def _banner(label):
    if label and "SYNTHETIC" in label.upper():
        return ("> **WARNING - SYNTHETIC TEST DATA.** These figures describe a tiny artificial "
                "dataset used only to test the pipeline. They are NOT CFPB results.\n\n")
    return ""


def build_summary_markdown(run, results, samples, profiling, analysis):
    """Compose data_quality_summary.md."""
    overview = profiling["P01_overview"][1].iloc[0]
    dates = profiling["P03_date_range"][1].iloc[0]
    timings = json.loads(run["stage_timings"]) if run.get("stage_timings") else {}
    severity_rank = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    failed = (results[results["status"] != "PASS"]
              .assign(_rank=lambda d: d["severity"].map(severity_rank).fillna(9))
              .sort_values(["_rank", "failing_count"], ascending=[True, False]))

    out = [f"# Data Quality Summary (run {run['run_id']})\n", _banner(run["dataset_label"])]
    out.append("## Run details\n")
    out.append(md_table(["Item", "Value"], [
        ["Dataset", run["dataset_label"]],
        ["Source file", run["source_file"]],
        ["Run started", run["started_at"]],
        ["Total execution time (s)", run["duration_seconds"]],
        ["Records processed", int(run["total_rows"])],
        ["Unique complaint IDs", int(overview["unique_complaint_ids"])],
        ["Unique companies", int(overview["unique_companies"])],
        ["Earliest valid date received", dates["earliest_date_received"]],
        ["Latest valid date received", dates["latest_date_received"]],
        ["Stage timings (s)", (", ".join(f"{k}={v}" for k, v in timings.items()) or "n/a")
         + " (report-writing time is added to the run record after this file is written)"],
    ]))
    out.append("\n\n## Headline\n")
    out.append(md_table(["Rules", "Passed", "Failed", "Errored", "Pass %"], [[
        int(run["rules_total"]), int(run["rules_passed"]), int(run["rules_failed"]),
        int(run["rules_errored"]), run["pass_pct"]]]))
    out.append("\n\nPass % = rules passed / rules executed. A rule passes when the percentage of "
               "failing records is at or below its documented threshold (see sql/validation.sql).\n")

    out.append("\n## All validation rules\n")
    out.append(md_table(
        ["Rule", "Name", "Category", "Severity", "Failing", "Failing %", "Threshold %", "Status"],
        [[r.rule_id, r.rule_name, r.category, r.severity, None if pd.isna(r.failing_count) else int(r.failing_count),
          r.failing_pct, r.threshold_pct, r.status] for r in results.itertuples()]))

    out.append("\n\n## Identified issues\n")
    if failed.empty:
        out.append("All rules passed.\n")
    for r in failed.itertuples():
        out.append(f"### {r.rule_id} - {r.rule_name} ({r.status}, {r.severity})\n")
        out.append(f"{r.explanation}\n")
        if r.error_message:
            out.append(f"Error: `{r.error_message}`\n")
        sample = samples[samples["rule_id"] == r.rule_id]
        if not sample.empty:
            out.append("Example failing records: " + "; ".join(
                f"row {int(s.row_id)}: `{s.detail}`" for s in sample.itertuples()) + "\n")

    out.append("\n## Missing values by column\n")
    missing = profiling["P02_missing_values"][1]
    out.append(md_table(["Column", "Requirement", "Missing", "Missing %"], missing.values.tolist()))
    out.append("\n\n## Duplicates\n")
    out.append(md_table(["Metric", "Value"], profiling["P07_duplicates"][1].values.tolist()))
    timely = analysis["A06_timely_response_overall"][1]
    out.append("\n\n## Timely response\n")
    out.append(md_table(list(timely.columns), timely.values.tolist()))
    out.append("\n")
    return "\n".join(out)


def build_readme_snippet(run, results, profiling, analysis):
    """A ready-to-paste 'Actual results and findings' section for the README."""
    overview = profiling["P01_overview"][1].iloc[0]
    dates = profiling["P03_date_range"][1].iloc[0]
    timely = analysis["A06_timely_response_overall"][1].iloc[0]
    top_products = analysis["A01_complaints_by_product"][1].head(3)
    top_companies = analysis["A03_top_companies"][1].head(3)
    failing = results[results["status"] != "PASS"].sort_values("failing_count", ascending=False)

    lines = [f"## Actual results and findings\n", _banner(run["dataset_label"]),
             f"_Generated automatically by `src/generate_report.py` from pipeline run {run['run_id']} "
             f"({run['started_at']}). Source file: `{Path(run['source_file']).name}`._\n",
             f"- Records processed: **{int(run['total_rows']):,}** "
             f"({int(overview['unique_complaint_ids']):,} unique complaint IDs, "
             f"{int(overview['unique_companies']):,} companies, "
             f"{int(overview['unique_products']):,} products)",
             f"- Valid date range: {dates['earliest_date_received']} to {dates['latest_date_received']}",
             f"- Validation: **{int(run['rules_passed'])} of {int(run['rules_total'])} rules passed** "
             f"({run['pass_pct']}%); {int(run['rules_failed'])} failed, {int(run['rules_errored'])} errored",
             f"- Timely responses: {timely['timely_pct']}% of {int(timely['records_with_timely_flag']):,} "
             f"records that carry a Yes/No flag",
             "- Largest products: " + ", ".join(f"{r.product} ({int(r.complaints):,})" for r in top_products.itertuples()),
             "- Largest companies by volume: " + ", ".join(f"{r.company} ({int(r.complaints):,})" for r in top_companies.itertuples()),
             "", "### Rules that did not pass\n"]
    if failing.empty:
        lines.append("None - every rule passed on this dataset.")
    else:
        lines.append(md_table(["Rule", "Name", "Failing records", "Failing %", "Status"],
                              [[r.rule_id, r.rule_name, None if pd.isna(r.failing_count) else int(r.failing_count),
                                r.failing_pct, r.status] for r in failing.itertuples()]))
    lines.append("\n_These are findings about the published CFPB extract as downloaded on the date shown; "
                 "they say nothing about regulatory compliance._\n")
    return "\n".join(lines)


def write_reports(conn, run_id=None, reports_dir=config.REPORTS_DIR):
    """Generate all report files. Returns {name: Path}."""
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    run = load_run(conn, run_id)
    results = pd.read_sql_query(
        "SELECT * FROM validation_results WHERE run_id = ? ORDER BY rule_id", conn, params=(run["run_id"],))
    samples = pd.read_sql_query(
        "SELECT * FROM validation_samples WHERE run_id = ? ORDER BY rule_id, row_id", conn, params=(run["run_id"],))
    profiling = run_profiling(conn)
    analysis = run_analysis(conn)

    paths = {
        "results_csv": reports_dir / "validation_results.csv",
        "samples_csv": reports_dir / "validation_failure_samples.csv",
        "summary_md": reports_dir / "data_quality_summary.md",
        "readme_snippet": reports_dir / "readme_results_snippet.md",
    }
    results.to_csv(paths["results_csv"], index=False)
    samples.to_csv(paths["samples_csv"], index=False)
    paths["summary_md"].write_text(build_summary_markdown(run, results, samples, profiling, analysis), encoding="utf-8")
    paths["readme_snippet"].write_text(build_readme_snippet(run, results, profiling, analysis), encoding="utf-8")
    return paths


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate data quality reports from a stored run.")
    parser.add_argument("--db", default=str(config.DATABASE_PATH))
    parser.add_argument("--reports-dir", default=str(config.REPORTS_DIR))
    parser.add_argument("--run-id", type=int, default=None)
    args = parser.parse_args(argv)
    try:
        conn = connect(args.db, read_only=True)
        paths = write_reports(conn, args.run_id, args.reports_dir)
    except (FileNotFoundError, LookupError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        try:
            conn.close()
        except NameError:
            pass
    for name, path in paths.items():
        print(f"{name:15} {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
