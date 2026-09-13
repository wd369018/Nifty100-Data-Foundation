"""Documents endpoint — annual report links with URL validity flags."""

import os

from fastapi import APIRouter, HTTPException, Query, Request

from src.api import query_all

router = APIRouter(tags=["documents"])


def _is_url_valid(url):
    """Live HEAD check; a missing/blank URL is always invalid (false)."""
    if not url or str(url).strip().lower() in ("null", "nan", ""):
        return False
    if os.environ.get("NIFTY100_LINK_CHECK", "1") == "0":
        return True
    import requests

    try:
        resp = requests.head(url, timeout=4, allow_redirects=True)
        return resp.status_code < 400
    except requests.RequestException:
        return False


@router.get("/companies/{ticker}/documents")
def company_documents(request: Request, ticker: str, year: int | None = Query(None)):
    """Return annual report links with an is_url_valid flag per year."""
    from src.api.routers.companies import _require_ticker

    company_id = _require_ticker(ticker)

    sql = "SELECT company_id, year, annual_report FROM documents WHERE company_id = ?"
    params = [company_id]
    if year is not None:
        sql += " AND year = ?"
        params.append(year)
    sql += " ORDER BY year"

    rows = query_all(sql, params)
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No documents for {ticker}"
            + (f" in year {year}" if year is not None else ""),
        )

    docs = []
    for row in rows:
        url = row["annual_report"]
        docs.append(
            {
                "year": row["year"],
                "annual_report": url,
                "is_url_valid": _is_url_valid(url),
            }
        )
    return {"company_id": company_id, "count": len(docs), "documents": docs}
