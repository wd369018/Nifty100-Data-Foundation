"""Valuation & market-cap endpoints — historical multiples (2019-2024)."""

from fastapi import APIRouter, HTTPException, Query

from src.api import query_all

router = APIRouter(prefix="/market-cap", tags=["valuation"])


@router.get("/{ticker}")
def market_cap_history(
    ticker: str,
    from_year: int | None = Query(None, ge=2014, le=2026),
    to_year: int | None = Query(None, ge=2014, le=2026),
):
    """Return historical valuation multiples (P/E, P/B, EV/EBITDA, div yield)."""
    from src.api.routers.companies import _require_ticker

    company_id = _require_ticker(ticker)

    low, high = from_year or 2019, to_year or 2024
    rows = query_all(
        "SELECT company_id, year, market_cap_crore, enterprise_value_crore, "
        "pe_ratio, pb_ratio, ev_ebitda, dividend_yield_pct "
        "FROM market_cap WHERE company_id = ? AND year BETWEEN ? AND ? "
        "ORDER BY year",
        [company_id, low, high],
    )
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No market-cap data for {ticker} between {low} and {high}.",
        )
    return {
        "company_id": company_id,
        "from_year": low,
        "to_year": high,
        "history": rows,
    }
