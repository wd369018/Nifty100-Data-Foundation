"""Cached SQLite data loaders for the Nifty100 Streamlit dashboard.

Every query function is decorated with @st.cache_data(ttl=600) so the
dashboard reuses results for 10 minutes.  Opening/closing the SQLite
connection happens inside each function.

Run the dashboard from the repository root:

    streamlit run src/dashboard/app.py
"""

from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / "db" / "nifty100.db"

CACHE_TTL = 600

METRIC_LABELS = {
    "sales": "Revenue",
    "net_profit": "Net Profit",
    "return_on_equity_pct": "ROE",
    "return_on_capital_employed_pct": "ROCE",
    "net_profit_margin_pct": "Net Margin",
    "operating_profit_margin_pct": "Op Margin",
    "debt_to_equity": "D/E",
    "interest_coverage": "Interest Coverage",
    "earnings_per_share": "EPS",
    "free_cash_flow_cr": "FCF",
    "market_cap_crore": "Market Cap",
}


def _query(sql, params=()):
    """Run a read-only SQL query and return the result as a DataFrame."""
    import sqlite3

    conn = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()


def clean_company_name(value):
    """Return the first line of a company name (strip stray newlines)."""
    text = str(value).strip()
    return text.split("\n")[0].strip()


def _clean_names(df):
    if "company_name" in df.columns:
        df["company_name"] = df["company_name"].apply(clean_company_name)
    return df


# ------------------------------------------------------------------
# Required loaders (Sprint 4 spec)
# ------------------------------------------------------------------


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_companies():
    """All 92 companies with profile metadata."""
    df = _query(
        "SELECT id, company_name, about_company, website, nse_profile, "
        "bse_profile FROM companies ORDER BY company_name"
    )
    return _clean_names(df)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_ratios(ticker, year=None):
    """Financial ratios for one company, optional year (int or 'YYYY-MM')."""
    sql = "SELECT * FROM financial_ratios WHERE company_id = ?"
    params = [ticker]
    if year is not None:
        if isinstance(year, int) or len(str(year)) == 4:
            sql += " AND year LIKE ?"
            params.append(f"{year}%")
        else:
            sql += " AND year = ?"
            params.append(str(year))
    sql += " ORDER BY year"
    return _query(sql, params)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_pl(ticker):
    """P&L statement rows for one company."""
    return _query(
        "SELECT company_id, year, sales, net_profit, operating_profit, "
        "other_income FROM profitandloss WHERE company_id = ? ORDER BY year",
        [ticker],
    )


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_bs(ticker):
    """Balance sheet rows for one company."""
    return _query(
        "SELECT company_id, year, equity_capital, reserves, borrowings, "
        "total_assets, investments FROM balancesheet "
        "WHERE company_id = ? ORDER BY year",
        [ticker],
    )


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_cf(ticker):
    """Cash flow rows for one company."""
    return _query(
        "SELECT company_id, year, operating_activity, investing_activity, "
        "financing_activity FROM cashflow WHERE company_id = ? ORDER BY year",
        [ticker],
    )


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_sectors():
    """Sector mapping for every company."""
    return _query(
        "SELECT company_id, broad_sector, sub_sector, index_weight_pct, "
        "market_cap_category FROM sectors"
    )


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_peers(group_name):
    """Companies inside ONE peer group, with benchmark flags."""
    df = _query(
        "SELECT g.peer_group_name, g.company_id, c.company_name, "
        "g.is_benchmark, s.broad_sector "
        "FROM peer_groups g "
        "JOIN companies c ON c.id = g.company_id "
        "LEFT JOIN sectors s ON s.company_id = g.company_id "
        "WHERE g.peer_group_name = ?",
        [group_name],
    )
    df["is_benchmark"] = df["is_benchmark"].astype(str).isin(["1", "True", "true"])
    return _clean_names(df)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_valuation(ticker):
    """Valuation summary row for one company (from Day 26 module)."""
    from src.analytics.valuation import build_valuation_frame

    frame = build_valuation_frame(DB_PATH)
    match = frame[frame["company_id"] == ticker]
    if match.empty:
        return pd.DataFrame()
    return match.head(1)


# ------------------------------------------------------------------
# Aggregated / derived loaders
# ------------------------------------------------------------------


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_all_ratios():
    """Every financial_ratios row (used for aggregate tiles)."""
    return _query("SELECT * FROM financial_ratios")


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_all_market_cap():
    """Every market_cap row."""
    return _query(
        "SELECT company_id, year, market_cap_crore, pe_ratio, pb_ratio, "
        "ev_ebitda, dividend_yield_pct FROM market_cap"
    )


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_market_cap(ticker):
    """Market-cap / valuation multiple history for one company."""
    return _query(
        "SELECT company_id, year, market_cap_crore, pe_ratio, pb_ratio, "
        "ev_ebitda, dividend_yield_pct FROM market_cap "
        "WHERE company_id = ? ORDER BY year",
        [ticker],
    )


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_feature_frame():
    """One row per company at its latest screening year (composites added)."""
    from src.screener.engine import compute_composite_score, load_feature_frame

    frame = compute_composite_score(load_feature_frame(db_path=DB_PATH))
    return _clean_names(frame)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_documents(ticker):
    """Annual report registry rows for one company."""
    return _query(
        "SELECT company_id, year, annual_report FROM documents "
        "WHERE company_id = ? ORDER BY year",
        [ticker],
    )


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_prosandcons(ticker):
    """Pros / cons bullet rows for one company (may be empty)."""
    return _query(
        "SELECT company_id, pros, cons FROM prosandcons WHERE company_id = ?",
        [ticker],
    )


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_company_series(ticker):
    """Annual time series for the trend charts (P&L + ratios + market cap).

    Columns: year_int, sales, net_profit, roe/roce/npm/opm/de/eps/fcf,
    market_cap_crore, pe_ratio.

    `return_on_capital_employed_pct` is not persisted in financial_ratios
    (the screener computes it on the fly), so it is derived here from the
    balance sheet and P&L for the same fiscal year.
    """
    ratios = get_ratios(ticker)
    if ratios.empty:
        return pd.DataFrame()

    pl = get_pl(ticker)[
        ["year", "sales", "net_profit", "operating_profit", "other_income"]
    ]
    bs = get_bs(ticker)[["year", "equity_capital", "reserves", "borrowings"]]
    mc = get_market_cap(ticker)[["year", "market_cap_crore", "pe_ratio"]]

    series = ratios.merge(pl, on="year", how="left", suffixes=("", "_pl"))
    series = series.merge(bs, on="year", how="left", suffixes=("", "_bs"))

    roce_rows = []
    for _, row in series.iterrows():
        op = row.get("operating_profit")
        oi = row.get("other_income")
        eq = row.get("equity_capital")
        res = row.get("reserves")
        bor = row.get("borrowings")
        ebit = None if pd.isna(op) else op + (0.0 if pd.isna(oi) else oi)
        ce = None
        if eq is not None and res is not None and bor is not None:
            eq_ = float(eq)
            res_ = float(res)
            bor_ = float(bor)
            if eq_ + res_ + bor_ > 0:
                ce = eq_ + res_ + bor_
        roce_rows.append(
            ebit / ce * 100.0 if ebit is not None and ce is not None else None
        )
    series["return_on_capital_employed_pct"] = roce_rows

    series["year_int"] = series["year"].str[:4].astype(int)
    mc = mc.rename(columns={"year": "year_int"})
    series = series.merge(mc, on="year_int", how="left")

    keep = [
        "year",
        "year_int",
        "sales",
        "net_profit",
        "return_on_equity_pct",
        "return_on_capital_employed_pct",
        "net_profit_margin_pct",
        "operating_profit_margin_pct",
        "debt_to_equity",
        "interest_coverage",
        "earnings_per_share",
        "free_cash_flow_cr",
        "market_cap_crore",
        "pe_ratio",
    ]
    return series[[c for c in keep if c in series.columns]].sort_values("year_int")


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_capital_allocation():
    """Latest-year capital allocation pattern per company (from CSV)."""
    csv_path = ROOT / "output" / "capital_allocation.csv"
    if not csv_path.exists():
        return pd.DataFrame(columns=["company_id", "year", "pattern_label"])
    df = pd.read_csv(csv_path)
    if df.empty:
        return df
    df["year_int"] = df["year"].str[:4].astype(int)
    latest = df.sort_values("year_int").drop_duplicates("company_id", keep="last")
    return _clean_names(latest)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_peer_groups():
    """Distinct peer group names (11)."""
    return [
        r[0]
        for r in _query(
            "SELECT DISTINCT peer_group_name FROM peer_groups "
            "ORDER BY peer_group_name"
        ).itertuples(index=False, name=None)
    ]


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_peer_percentiles():
    """Every peer_percentiles row (metric percentiles inside groups)."""
    return _query(
        "SELECT company_id, peer_group_name, metric, percentile_rank "
        "FROM peer_percentiles"
    )


@st.cache_data(ttl=86400, show_spinner=False)
def report_url_status(url):
    """Return 'ok' / 'unavailable' / 'missing' for an annual-report URL.

    Live HEAD checks can be disabled with the NIFTY100_LINK_CHECK=0
    environment variable (used by the automated verification harness so
    it stays fast and offline-safe).
    """
    import os

    if url is None or str(url).strip().lower() in ("null", "nan", ""):
        return "missing"
    if os.environ.get("NIFTY100_LINK_CHECK", "1") == "0":
        return "ok"
    import requests

    try:
        response = requests.head(url, timeout=4, allow_redirects=True)
        return "ok" if response.status_code < 400 else "unavailable"
    except requests.RequestException:
        return "unavailable"
