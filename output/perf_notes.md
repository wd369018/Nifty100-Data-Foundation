# Performance Notes (Sprint 6, Day 43)

## API load test

Command: `venv\Scripts\python.exe scripts/load_test_api.py`

10 concurrent GET `/api/v1/screener?min_roe=15` requests against a live
uvicorn server. Gate: total wall time below 10 s.

| Metric | Value |
| --- | --- |
| Concurrent requests | 10 |
| Total wall time | < 10 s gate |
| Mean per-call latency | ~30 ms |

## Dashboard performance (Company Profile page)

Shared page-level loaders (`get_companies()`, `get_feature_frame()`)
run once per page and are cached at ttl=600 by streamlit. The
per-ticker loads are `get_pl`, `get_company_series`, `get_prosandcons`.
Gate: each of the 5 representative tickers finishes in under 3 s.

Shared page load: 1.30s (once, cached).

| Ticker | Seconds |
| --- | ---: |
| TCS | 0.07 |
| RELIANCE | 0.04 |
| HDFCBANK | 0.04 |
| INFY | 0.04 |
| TATAMOTORS | 0.04 |

**Result: PASS** (per-ticker limit 3.0s)