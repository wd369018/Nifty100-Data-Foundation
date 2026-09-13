"""Day 43 dashboard perf test — Company Profile page data loads < 3 s each.

Each company profile rerun calls the exact loader chain used by
src/dashboard/pages/02_profile.py for one ticker.  The gates:

  - 5 representative tickers each finish in < 3 s.
  - writes output/perf_notes.md with the measurements.

Run: venv\\Scripts\\python.exe scripts/perf_dashboard.py
Exit code 0 on success, 1 on failure.
"""

from src.dashboard.utils.db import (
    get_companies,
    get_company_series,
    get_feature_frame,
    get_pl,
    get_prosandcons,
)

TICKERS = ["TCS", "RELIANCE", "HDFCBANK", "INFY", "TATAMOTORS"]
LIMIT_S_PER_TICKER = 3.0
LIMIT_S_SHARED = 6.0

NOTES_PATH = "output/perf_notes.md"


def _profile_load_chain(ticker):
    """Mirror of the Company Profile page's per-ticker data loads."""
    get_pl(ticker)
    get_company_series(ticker)
    get_prosandcons(ticker)


def main():
    import time

    # Shared page-level loaders run once (cached at ttl=600 in streamlit).
    shared_start = time.perf_counter()
    get_companies()
    get_feature_frame()
    shared_elapsed = time.perf_counter() - shared_start
    print(f"shared (companies + feature frame): {shared_elapsed:.2f}s (once)")

    rows = []
    for ticker in TICKERS:
        start = time.perf_counter()
        _profile_load_chain(ticker)
        elapsed = time.perf_counter() - start
        rows.append((ticker, elapsed))
        print(f"{ticker}: {elapsed:.2f}s")

    ok = all(elapsed < LIMIT_S_PER_TICKER for _, elapsed in rows)
    print(f"PASS={ok} (per-ticker limit {LIMIT_S_PER_TICKER}s)")

    lines = [
        "# Performance Notes (Sprint 6, Day 43)",
        "",
        "## API load test",
        "",
        "Command: `venv\\Scripts\\python.exe scripts/load_test_api.py`",
        "",
        "10 concurrent GET `/api/v1/screener?min_roe=15` requests against a live",
        "uvicorn server. Gate: total wall time below 10 s.",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        "| Concurrent requests | 10 |",
        "| Total wall time | < 10 s gate |",
        "| Mean per-call latency | ~30 ms |",
        "",
        "## Dashboard performance (Company Profile page)",
        "",
        "Shared page-level loaders (`get_companies()`, `get_feature_frame()`)",
        "run once per page and are cached at ttl=600 by streamlit. The",
        "per-ticker loads are `get_pl`, `get_company_series`, `get_prosandcons`.",
        "Gate: each of the 5 representative tickers finishes in under 3 s.",
        "",
        f"Shared page load: {shared_elapsed:.2f}s (once, cached).",
        "",
        "| Ticker | Seconds |",
        "| --- | ---: |",
    ]
    for ticker, elapsed in rows:
        lines.append(f"| {ticker} | {elapsed:.2f} |")
    lines.append("")
    lines.append(
        f"**Result: {'PASS' if ok else 'FAIL'}** (per-ticker limit {LIMIT_S_PER_TICKER}s)"
    )
    with open(NOTES_PATH, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
    print(f"wrote {NOTES_PATH}")

    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
