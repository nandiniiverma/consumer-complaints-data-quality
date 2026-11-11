"""
dashboard/app.py - Stage 6: Streamlit dashboard.

Purpose
-------
A read-only view of the pipeline results. EVERY number and chart is loaded from
the SQLite database (pipeline_runs, validation_results, validation_samples and
the SQL in sql/profiling.sql + sql/analysis.sql). Nothing is hard-coded.
The database is opened in read-only mode, so the dashboard cannot change data.

Run it (after run_pipeline.py has created database/complaints.db)
-----------------------------------------------------------------
    streamlit run dashboard/app.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import streamlit as st  # noqa: E402

from src import config  # noqa: E402
from src.analysis import run_analysis  # noqa: E402
from src.db_utils import connect  # noqa: E402
from src.profile_data import run_profiling  # noqa: E402

PRIMARY = "#1F4E79"   # single accent colour for volume charts
STATUS_COLOURS = {"PASS": "#2E7D32", "FAIL": "#C62828", "ERROR": "#EF6C00"}
SEVERITY_ORDER = ["Critical", "High", "Medium", "Low"]

st.set_page_config(page_title="Complaints Data Quality", page_icon="📊", layout="wide")

st.markdown(
    """
    <style>
      .block-container {padding-top: 2rem; max-width: 1250px;}
      div[data-testid="stMetric"] {border: 1px solid rgba(128,128,128,.25);
          border-radius: 8px; padding: 12px 16px;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner=False)
def load_data(db_path: str, db_mtime: float, run_id: int | None):
    """Load everything the dashboard needs from the database (cached per DB version)."""
    conn = connect(db_path, read_only=True)
    try:
        runs = pd.read_sql_query(
            "SELECT * FROM pipeline_runs WHERE status = 'SUCCESS' ORDER BY run_id DESC", conn)
        if runs.empty:
            return None
        chosen = runs.iloc[0] if run_id is None else runs[runs["run_id"] == run_id].iloc[0]
        rid = int(chosen["run_id"])
        results = pd.read_sql_query(
            "SELECT * FROM validation_results WHERE run_id = ? ORDER BY rule_id", conn, params=(rid,))
        samples = pd.read_sql_query(
            "SELECT * FROM validation_samples WHERE run_id = ? ORDER BY rule_id, row_id", conn, params=(rid,))
        ingestion = pd.read_sql_query(
            "SELECT * FROM ingestion_log ORDER BY ingestion_id DESC LIMIT 1", conn)
        profiling = {k: v[1] for k, v in run_profiling(conn).items()}
        analysis = {k: v[1] for k, v in run_analysis(conn).items()}
        return {"runs": runs, "run": chosen, "results": results, "samples": samples,
                "ingestion": ingestion, "profiling": profiling, "analysis": analysis}
    finally:
        conn.close()


def style_status(value):
    colour = STATUS_COLOURS.get(value, "")
    return f"color: white; background-color: {colour}; font-weight: 600; text-align: center" if colour else ""


# ----------------------------------------------------------------------------
# Sidebar: choose database and run
# ----------------------------------------------------------------------------
st.sidebar.header("Data source")
db_path = Path(st.sidebar.text_input("SQLite database", str(config.DATABASE_PATH)))

if not db_path.exists():
    st.title("Complaints Data Quality Dashboard")
    st.error(f"Database not found: `{db_path}`")
    st.markdown("Run the pipeline first:\n\n```\npython src/run_pipeline.py --csv data/raw/complaints_sample.csv\n```")
    st.stop()

try:
    probe = connect(db_path, read_only=True)
    run_choices = pd.read_sql_query(
        "SELECT run_id, started_at, dataset_label FROM pipeline_runs WHERE status = 'SUCCESS' ORDER BY run_id DESC",
        probe)
    probe.close()
except Exception as exc:
    st.title("Complaints Data Quality Dashboard")
    st.error(f"Could not read the database: {exc}")
    st.stop()

if run_choices.empty:
    st.title("Complaints Data Quality Dashboard")
    st.warning("The database has no completed pipeline run yet. Run `python src/run_pipeline.py`.")
    st.stop()

labels = {int(r.run_id): f"Run {r.run_id} - {r.started_at} - {r.dataset_label}" for r in run_choices.itertuples()}
selected_run = st.sidebar.selectbox("Pipeline run", list(labels), format_func=labels.get)

data = load_data(str(db_path), db_path.stat().st_mtime, int(selected_run))
run, results, samples = data["run"], data["results"], data["samples"]
profiling, analysis = data["profiling"], data["analysis"]

# ----------------------------------------------------------------------------
# Header
# ----------------------------------------------------------------------------
st.title("Consumer Complaints - Data Quality Dashboard")
st.caption(f"Source file: `{Path(str(run['source_file'])).name}` | run {int(run['run_id'])} "
           f"started {run['started_at']} | pipeline time {run['duration_seconds']}s")
if "SYNTHETIC" in str(run["dataset_label"]).upper():
    st.warning("SYNTHETIC TEST DATA - these figures come from an artificial test file, not from the CFPB dataset.")

# ----------------------------------------------------------------------------
# KPI row
# ----------------------------------------------------------------------------
duplicates = dict(profiling["P07_duplicates"].values)
timely = analysis["A06_timely_response_overall"].iloc[0]
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Records processed", f"{int(run['total_rows']):,}")
k2.metric("Validation rules", int(run["rules_total"]))
k3.metric("Passed checks", int(run["rules_passed"]))
k4.metric("Failed checks", int(run["rules_failed"]) + int(run["rules_errored"]))
k5.metric("Data quality pass %", f"{run['pass_pct']:.1f}%")

k6, k7, k8, k9 = st.columns(4)
k6.metric("Surplus rows from repeated IDs", f"{int(duplicates['surplus_rows_from_repeated_ids']):,}")
k7.metric("Exact duplicate rows", f"{int(duplicates['surplus_rows_exact_duplicates']):,}")
k8.metric("Unique companies", f"{int(profiling['P01_overview'].iloc[0]['unique_companies']):,}")
timely_pct = timely["timely_pct"]
k9.metric("Timely responses", "n/a" if pd.isna(timely_pct) else f"{timely_pct:.1f}%")
st.caption("Pass % = rules passed / rules executed. A rule passes when its failing-record percentage is "
           "within its documented threshold (sql/validation.sql).")

tab_rules, tab_missing, tab_trend, tab_product, tab_company, tab_issues = st.tabs(
    ["Validation rules", "Missing values", "Complaint trends", "By product", "By company", "Identified issues"])

# ----------------------------------------------------------------------------
# Validation rules table
# ----------------------------------------------------------------------------
with tab_rules:
    status_filter = st.multiselect("Status", ["PASS", "FAIL", "ERROR"], default=["PASS", "FAIL", "ERROR"])
    shown = results[results["status"].isin(status_filter)][
        ["rule_id", "rule_name", "category", "severity", "failing_count", "failing_pct",
         "threshold_pct", "status"]].rename(columns={
            "rule_id": "Rule", "rule_name": "Name", "category": "Category", "severity": "Severity",
            "failing_count": "Failing records", "failing_pct": "Failing %",
            "threshold_pct": "Threshold %", "status": "Status"})
    styled = (shown.style.map(style_status, subset=["Status"])
              .format({"Failing records": "{:,.0f}", "Failing %": "{:.2f}", "Threshold %": "{:g}"},
                      na_rep="n/a"))
    st.dataframe(styled, width="stretch", hide_index=True)
    by_status = results.groupby("status").size().reset_index(name="rules")
    st.caption("Rules by status: " + ", ".join(f"{r.status} {r.rules}" for r in by_status.itertuples()))

# ----------------------------------------------------------------------------
# Missing values
# ----------------------------------------------------------------------------
with tab_missing:
    missing = profiling["P02_missing_values"]
    with_missing = missing[missing["missing_count"] > 0].sort_values("missing_pct")
    if with_missing.empty:
        st.success("No blank values were found in any column.")
    else:
        # calm colours on purpose: blanks in OPTIONAL columns are legitimate, not defects
        requirement_colours = {"Mandatory": "#1F4E79", "Optional (monitored)": "#5B9BD5",
                               "Optional": "#9AA5B1", "Optional (not loaded by default)": "#CBD2D9"}
        fig = px.bar(with_missing, x="missing_pct", y="column_name", orientation="h",
                     color="requirement", color_discrete_map=requirement_colours,
                     labels={"missing_pct": "Missing (%)", "column_name": "",
                             "requirement": "Column type"},
                     title="Columns with missing values")
        fig.update_layout(height=max(300, 28 * len(with_missing) + 120), legend_title_text="")
        st.plotly_chart(fig, width="stretch")
    st.dataframe(missing.rename(columns={"column_name": "Column", "requirement": "Requirement",
                                         "missing_count": "Missing", "missing_pct": "Missing %"})
                 .style.format({"Missing": "{:,.0f}", "Missing %": "{:.2f}"}),
                 width="stretch", hide_index=True)
    st.caption("Mandatory columns should have no blanks. Optional columns (sub-product, narrative, tags, ...) "
               "may be legitimately blank; the narrative is not loaded unless --include-narrative is used.")

# ----------------------------------------------------------------------------
# Trend / product / company charts
# ----------------------------------------------------------------------------
with tab_trend:
    trend = analysis["A02_daily_trend"].copy()
    if trend.empty:
        st.info("No valid dates to plot.")
    else:
        trend["received_date"] = pd.to_datetime(trend["received_date"])
        # Days with no complaints have no row in SQL; show them as 0 so the line is not misleading.
        full_range = pd.date_range(trend["received_date"].min(), trend["received_date"].max(), freq="D")
        trend = (trend.set_index("received_date").reindex(full_range).rename_axis("received_date")
                 .reset_index())
        trend["complaints"] = trend["complaints"].fillna(0).astype(int)
        trend["weekday"] = trend["received_date"].dt.strftime("%a")
        trend["label"] = trend["received_date"].dt.strftime("%d %b %Y")
        fig = px.line(trend, x="received_date", y="complaints", markers=True,
                      custom_data=["label", "weekday"],
                      labels={"received_date": "Date received", "complaints": "Complaints"},
                      title="Complaints received per day")
        fig.update_traces(line_color=PRIMARY,
                          hovertemplate="%{customdata[0]} (%{customdata[1]})<br>Complaints: %{y:,}<extra></extra>")
        fig.update_xaxes(tickformat="%d %b", dtick=86400000)  # one tick per day, e.g. "20 Dec"
        fig.update_yaxes(rangemode="tozero")
        st.plotly_chart(fig, width="stretch")
        st.dataframe(trend[["label", "weekday", "complaints"]].rename(columns={
            "label": "Date received", "weekday": "Day", "complaints": "Complaints"}),
            width="stretch", hide_index=True)
    st.caption("Only records with a valid date_received are plotted; invalid dates are reported under DQ-005. "
               "Counts are read from the database (query A02_daily_trend).")

with tab_product:
    products = analysis["A01_complaints_by_product"].sort_values("complaints")
    fig = px.bar(products, x="complaints", y="product", orientation="h", text="complaints",
                 labels={"complaints": "Complaints", "product": ""}, title="Complaints by product")
    fig.update_traces(marker_color=PRIMARY)
    fig.update_layout(height=max(320, 30 * len(products) + 120))
    st.plotly_chart(fig, width="stretch")
    st.dataframe(analysis["A07_timely_by_product"].rename(columns={
        "product": "Product", "records_with_timely_flag": "Records with Yes/No flag",
        "timely_pct": "Timely %"}), width="stretch", hide_index=True)
    st.caption("Timely % is shown for products with at least "
               f"{config.ANALYSIS_PARAMS['min_complaints']} flagged records.")

with tab_company:
    companies = analysis["A03_top_companies"].sort_values("complaints")
    fig = px.bar(companies, x="complaints", y="company", orientation="h", text="complaints",
                 labels={"complaints": "Complaints", "company": ""},
                 title=f"Top {config.ANALYSIS_PARAMS['top_n']} companies by complaint volume")
    fig.update_traces(marker_color=PRIMARY)
    fig.update_layout(height=max(320, 34 * len(companies) + 120))
    st.plotly_chart(fig, width="stretch")
    st.markdown("**Companies with the most untimely responses**")
    st.dataframe(analysis["A08_untimely_companies"], width="stretch", hide_index=True)

# ----------------------------------------------------------------------------
# Explanation of identified issues
# ----------------------------------------------------------------------------
with tab_issues:
    problems = results[results["status"] != "PASS"].copy()
    if problems.empty:
        st.success("Every rule passed on this dataset.")
    problems["_rank"] = problems["severity"].map({s: i for i, s in enumerate(SEVERITY_ORDER)}).fillna(9)
    for row in problems.sort_values(["_rank", "rule_id"]).itertuples():
        icon = "🔴" if row.status == "FAIL" else "🟠"
        with st.expander(f"{icon} {row.rule_id} - {row.rule_name}  ({row.severity}, {row.status})"):
            st.write(row.explanation)
            if row.error_message:
                st.code(row.error_message)
            rule_samples = samples[samples["rule_id"] == row.rule_id]
            if not rule_samples.empty:
                st.caption("Example failing records")
                st.dataframe(rule_samples[["row_id", "detail"]].rename(
                    columns={"row_id": "row_id (complaints_raw)", "detail": "Offending value"}),
                    width="stretch", hide_index=True)
    passed_with_failures = results[(results["status"] == "PASS") & (results["failing_count"] > 0)]
    if not passed_with_failures.empty:
        st.info("Within tolerance (PASS, but some records still fail): " + ", ".join(
            f"{r.rule_id} ({int(r.failing_count)} records, {r.failing_pct:.2f}% <= {r.threshold_pct:g}%)"
            for r in passed_with_failures.itertuples()))

st.sidebar.markdown("---")
st.sidebar.caption("Findings describe data quality of the extract only. They do not establish "
                   "regulatory compliance or data governance.")
