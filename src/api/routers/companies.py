"""Company endpoints — list, profile, financial statements and ratio KPIs."""

from fastapi import APIRouter, HTTPException, Query

from src.api import TEARSHEET_DIR, query_all, query_first

router = APIRouter(prefix="/companies", tags=["companies"])

PROFILE_COLUMNS = [
    "id",
    "company_name",
    "about_company",
    "website",
    "nse_profile",
    "bse_profile",
    "face_value",
    "book_value",
    "roce_percentage",
    "roe_percentage",
]


def _require_ticker(ticker):
    """Return the company profile row or raise HTTP 404."""
    company = query_first(
        "SELECT id FROM companies WHERE id = ? COLLATE NOCASE",
        [ticker],
    )
    if company is None:
        raise HTTPException(status_code=404, detail=f"Company not found: {ticker}")
    return company["id"]


@router.get("")
def list_companies(
    sector: str | None = Query(None, description="Filter by broad_sector"),
    market_cap_category: str | None = Query(None),
    search: str | None = Query(None),
):
    """Return all 92 companies with identifier, sector and headline KPIs."""
    sql = (
        "SELECT c.id, c.company_name, c.roe_percentage AS roe_pct, "
        "c.roce_percentage AS roce_pct, "
        "s.broad_sector, s.sub_sector, s.market_cap_category "
        "FROM companies c "
        "LEFT JOIN sectors s ON s.company_id = c.id "
        "WHERE 1=1"
    )
    params = []
    if sector:
        sql += " AND s.broad_sector = ?"
        params.append(sector)
    if market_cap_category:
        sql += " AND s.market_cap_category = ?"
        params.append(market_cap_category)
    if search:
        term = f"%{search}%"
        sql += " AND (c.id LIKE ? OR c.company_name LIKE ?)"
        params.extend([term, term])
    sql += " ORDER BY c.id"
    rows = query_all(sql, params)
    for row in rows:
        row["company_name"] = row["company_name"].split("\n")[0].strip()
    return {"count": len(rows), "companies": rows}


@router.get("/{ticker}")
def company_profile(ticker: str):
    """Return full company profile + latest-year KPIs + sector data (404 if missing)."""
    company_id = _require_ticker(ticker)
    company = query_first(
        "SELECT " + ", ".join(PROFILE_COLUMNS) + " FROM companies WHERE id = ?",
        [company_id],
    )
    company["company_name"] = company["company_name"].split("\n")[0].strip()

    latest = query_first(
        "SELECT * FROM financial_ratios WHERE company_id = ? "
        "ORDER BY year DESC LIMIT 1",
        [company_id],
    )
    sector = query_first("SELECT * FROM sectors WHERE company_id = ?", [company_id])

    return {
        "company": company,
        "latest_year_kpis": latest,
        "year": latest["year"] if latest else None,
        "sector": sector,
    }


def _statement_history(table, ticker, from_year, to_year, extra_cols=""):
    """Return year-filtered history rows for a financial-statement table."""
    company_id = _require_ticker(ticker)
    sql = f"SELECT company_id, year{extra_cols} FROM {table} WHERE company_id = ?"
    params = [company_id]
    if from_year:
        sql += " AND year >= ?"
        params.append(str(from_year))
    if to_year:
        sql += " AND year <= ?"
        params.append(str(to_year))
    sql += " ORDER BY year"
    rows = query_all(sql, params)
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No {table} records for {ticker} in that range.",
        )
    return rows


@router.get("/{ticker}/pl")
def company_pl(
    ticker: str,
    from_year: str | None = Query(None, description="YYYY-MM"),
    to_year: str | None = Query(None, description="YYYY-MM"),
):
    """Return P&L history (optionally filtered by from_year/to_year)."""
    return _statement_history(
        "profitandloss",
        ticker,
        from_year,
        to_year,
        extra_cols=", sales, expenses,"
        " operating_profit, opm_percentage, other_income, interest, depreciation,"
        " profit_before_tax, tax_percentage, net_profit, eps, dividend_payout",
    )


@router.get("/{ticker}/bs")
def company_bs(
    ticker: str,
    from_year: str | None = Query(None, description="YYYY-MM"),
    to_year: str | None = Query(None, description="YYYY-MM"),
):
    """Return balance-sheet history (optionally filtered by year)."""
    return _statement_history(
        "balancesheet",
        ticker,
        from_year,
        to_year,
        extra_cols=", equity_capital,"
        " reserves, borrowings, other_liabilities, total_liabilities, fixed_assets,"
        " cwip, investments, other_asset, total_assets",
    )


@router.get("/{ticker}/cashflow")
def company_cashflow(
    ticker: str,
    from_year: str | None = Query(None, description="YYYY-MM"),
    to_year: str | None = Query(None, description="YYYY-MM"),
):
    """Return cash-flow history (optionally filtered by year)."""
    return _statement_history(
        "cashflow",
        ticker,
        from_year,
        to_year,
        extra_cols=", operating_activity,"
        " investing_activity, financing_activity, net_cash_flow",
    )


@router.get("/{ticker}/ratios")
def company_ratios(
    ticker: str,
    year: str | None = Query(
        None, description="YYYY or YYYY-MM to filter a single year"
    ),
):
    """Return all computed KPI ratios per year, or a single year when asked."""
    company_id = _require_ticker(ticker)
    sql = "SELECT * FROM financial_ratios WHERE company_id = ?"
    params = [company_id]
    if year:
        if len(str(year)) == 4:
            sql += " AND year LIKE ?"
            params.append(f"{year}%")
        else:
            sql += " AND year = ?"
            params.append(str(year))
    sql += " ORDER BY year"
    rows = query_all(sql, params)
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No ratio data for {ticker} in that range.",
        )
    return rows


@router.get("/{ticker}/tearsheet")
def company_tearsheet(ticker: str):
    """Stream the pre-generated tearsheet PDF as application/pdf."""
    from fastapi.responses import FileResponse

    company_id = _require_ticker(ticker)
    pdf = TEARSHEET_DIR / f"{company_id}.pdf"
    if not pdf.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Tearsheet PDF not generated for {ticker}.",
        )
    return FileResponse(
        str(pdf), media_type="application/pdf", filename=f"{company_id}_tearsheet.pdf"
    )
