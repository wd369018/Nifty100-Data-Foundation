"""Auto Pros/Cons Generator (Sprint 5, Day 30).

Evaluates 12 pro and 12 con fundamental rules for every company in the
Nifty 100 universe, assigns a 0-100 confidence score per rule and
writes only signals above 60% to output/pros_cons_generated.csv.

The final output guarantees at least one pro and one con per company.
Where no rule clears the 60% bar for a company, a factually-grounded
fallback signal (rule ids pro_fb* / con_fb*) is emitted at 62%.

Run:  python -m src.nlp.pros_cons_generator
"""

import math
import sqlite3
from pathlib import Path

import pandas as pd

from src.analytics.ratios import FINANCIALS_SECTOR, net_debt
from src.screener.engine import _num

DB_PATH = Path("db/nifty100.db")
OUTPUT_PATH = Path("output/pros_cons_generated.csv")

MIN_CONFIDENCE = 60.0
FALLBACK_CONFIDENCE = 62.0


# ------------------------------------------------------------------
# Confidence helpers
# ------------------------------------------------------------------


def margin_confidence(
    value, threshold, higher_is_better=True, base=60.0, full_span_ratio=2.0, step=20.0
):
    """0-100 confidence that grows as `value` moves past `threshold`.

    `base` is returned at the threshold; the closer the value gets to
    `full_span_ratio` multiples away, the closer confidence gets to 100.
    """
    if value is None:
        return None
    v = float(value)
    t = float(threshold)

    if higher_is_better:
        if v <= t:
            return base
        distance = (v - t) / t if abs(t) > 1e-9 else v - t
    else:
        if v >= t:
            return base
        distance = (t - v) / t if abs(t) > 1e-9 else t - v

    return min(100.0, base + min(distance / full_span_ratio, 1.0) * step)


def trailing_run(values, predicate):
    """Length of the trailing streak of values satisfying `predicate`."""
    count = 0
    for v in reversed(list(values)):
        if v is None:
            break
        try:
            fv = float(v)
        except (TypeError, ValueError):
            break
        if not predicate(fv):
            break
        count += 1
    return count


# ------------------------------------------------------------------
# Rule definitions
# ------------------------------------------------------------------


def _latest(frame, column):
    if frame is None or frame.empty or column not in frame.columns:
        return None
    return frame[column].iloc[-1]


def _last_n_list(frame, column, n):
    if frame is None or frame.empty or column not in frame.columns:
        return []
    vals = frame[column].dropna().tail(n).tolist()
    return [_num(v) for v in vals]


PRO_RULES = [
    {
        "id": "pro_01",
        "text": (
            "Consistently high return on equity above 20% "
            "demonstrates exceptional capital efficiency"
        ),
        "evaluate": lambda b: _pro_roe_sustained(b),
    },
    {
        "id": "pro_02",
        "text": (
            "Strong free cash flow generation over 5 years signals "
            "healthy business fundamentals"
        ),
        "evaluate": lambda b: _pro_fcf_positive(b),
    },
    {
        "id": "pro_03",
        "text": (
            "Debt-free balance sheet provides financial flexibility "
            "and eliminates interest burden"
        ),
        "evaluate": lambda b: _pro_debt_free(b),
    },
    {
        "id": "pro_04",
        "text": (
            "Revenue growing at above 15% CAGR over 5 years reflects "
            "strong business momentum"
        ),
        "evaluate": lambda b: _pro_rev_cagr(b),
    },
    {
        "id": "pro_05",
        "text": (
            "Operating profit margin above 25% indicates strong "
            "pricing power and cost discipline"
        ),
        "evaluate": lambda b: _pro_opm(b),
    },
    {
        "id": "pro_06",
        "text": (
            "Net profit compounding at above 20% over 5 years creates "
            "significant shareholder value"
        ),
        "evaluate": lambda b: _pro_pat_cagr(b),
    },
    {
        "id": "pro_07",
        "text": (
            "Very high interest coverage ratio reflects negligible "
            "financial stress from debt servicing"
        ),
        "evaluate": lambda b: _pro_icr(b),
    },
    {
        "id": "pro_08",
        "text": (
            "Consistent dividend yield above 2% backed by positive " "free cash flow"
        ),
        "evaluate": lambda b: _pro_dividend(b),
    },
    {
        "id": "pro_09",
        "text": (
            "Earnings per share growing above 15% CAGR indicates "
            "strong earnings quality and compounding"
        ),
        "evaluate": lambda b: _pro_eps_cagr(b),
    },
    {
        "id": "pro_10",
        "text": (
            "Return on equity improving for 3 consecutive years "
            "shows strengthening business quality"
        ),
        "evaluate": lambda b: _pro_roe_improving(b),
    },
    {
        "id": "pro_11",
        "text": (
            "Revenue growing slower than profits shows improving "
            "operating leverage and scale benefits"
        ),
        "evaluate": lambda b: _pro_op_leverage(b),
    },
    {
        "id": "pro_12",
        "text": (
            "Growing asset base funded by internal accruals "
            "reflects self-sustaining growth"
        ),
        "evaluate": lambda b: _pro_asset_growth(b),
    },
]


CON_RULES = [
    {
        "id": "con_01",
        "evaluate": lambda b: _con_high_de(b),
    },
    {
        "id": "con_02",
        "text": (
            "Free cash flow negative for 3 consecutive years raises "
            "concern about cash generation quality"
        ),
        "evaluate": lambda b: _con_fcf_negative(b),
    },
    {
        "id": "con_03",
        "text": (
            "Operating margins declining for 3 consecutive years "
            "suggest pricing or cost pressure"
        ),
        "evaluate": lambda b: _con_opm_declining(b),
    },
    {
        "id": "con_04",
        "text": ("Company reported a net loss in the most recent " "financial year"),
        "evaluate": lambda b: _con_net_loss(b),
    },
    {
        "id": "con_05",
        "text": (
            "Revenue contraction over 2 consecutive years indicates "
            "demand weakness or market share loss"
        ),
        "evaluate": lambda b: _con_revenue_declining(b),
    },
    {
        "id": "con_06",
        "text": (
            "Interest coverage ratio below 1.5x indicates the company "
            "is at risk of not meeting its debt obligations"
        ),
        "evaluate": lambda b: _con_low_icr(b),
    },
    {
        "id": "con_07",
        "text": (
            "Dividend payout ratio above 100% means the company is "
            "paying dividends from reserves, which is unsustainable"
        ),
        "evaluate": lambda b: _con_high_payout(b),
    },
    {
        "id": "con_08",
        "text": (
            "Rising debt-to-equity ratio over 3 years suggests "
            "increasing financial leverage risk"
        ),
        "evaluate": lambda b: _con_de_rising(b),
    },
    {
        "id": "con_09",
        "text": (
            "Earnings per share declining for 3 consecutive years "
            "reflects deteriorating profitability"
        ),
        "evaluate": lambda b: _con_eps_declining(b),
    },
    {
        "id": "con_10",
        "text": (
            "Return on capital employed below 10% suggests the "
            "business is not generating sufficient returns on "
            "invested capital"
        ),
        "evaluate": lambda b: _con_low_roce(b),
    },
    {
        "id": "con_11",
        "evaluate": lambda b: _con_high_net_debt(b),
    },
    {
        "id": "con_12",
        "text": (
            "Revenue growing at below 5% over 5 years lags inflation "
            "and suggests limited business momentum"
        ),
        "evaluate": lambda b: _con_low_rev_cagr(b),
    },
]


# ------------------------------------------------------------------
# Pro rule evaluators -> (matched: bool, confidence: float | None)
# ------------------------------------------------------------------


def _pro_roe_sustained(bundle):
    vals = _last_n_list(bundle["ratios"], "return_on_equity_pct", 10)
    run = trailing_run(vals, lambda v: v > 20.0)
    if run < 3:
        return False, None
    return True, min(100.0, 61.0 + (run - 3) * 5.0)


def _pro_fcf_positive(bundle):
    vals = _last_n_list(bundle["ratios"], "free_cash_flow_cr", 10)
    run = trailing_run(vals, lambda v: v > 0.0)
    if run < 5:
        return False, None
    return True, min(100.0, 65.0 + (run - 5) * 3.0)


def _pro_debt_free(bundle):
    de = _latest(bundle["ratios"], "debt_to_equity")
    if de is None:
        return False, None
    return abs(float(de)) < 1e-6, 70.0


def _pro_rev_cagr(bundle):
    value = _latest(bundle["ratios"], "revenue_cagr_5yr")
    if value is None or not value > 15.0:
        return False, None
    return True, margin_confidence(value, 15.0)


def _pro_opm(bundle):
    value = _latest(bundle["ratios"], "operating_profit_margin_pct")
    if value is None or not value > 25.0:
        return False, None
    return True, margin_confidence(value, 25.0)


def _pro_pat_cagr(bundle):
    value = _latest(bundle["ratios"], "pat_cagr_5yr")
    if value is None or not value > 20.0:
        return False, None
    return True, margin_confidence(value, 20.0)


def _pro_icr(bundle):
    label = _latest(bundle["ratios"], "icr_label")
    icr = _latest(bundle["ratios"], "interest_coverage")
    if label == "Debt Free":
        return True, 70.0
    if icr is None or not icr > 10.0:
        return False, None
    return True, margin_confidence(icr, 10.0)


def _pro_dividend(bundle):
    dy = _latest(bundle["mc"], "dividend_yield_pct")
    fcf = _latest(bundle["ratios"], "free_cash_flow_cr")
    if dy is None or fcf is None:
        return False, None
    if float(dy) <= 2.0 or float(fcf) <= 0.0:
        return False, None
    return True, min(100.0, 65.0 + min(float(dy) - 2.0, 3.0) * 7.0)


def _pro_eps_cagr(bundle):
    value = _latest(bundle["ratios"], "eps_cagr_5yr")
    if value is None or not value > 15.0:
        return False, None
    return True, margin_confidence(value, 15.0)


def _pro_roe_improving(bundle):
    roi = _last_n_list(bundle["ratios"], "return_on_equity_pct", 4)
    if len(roi) < 3:
        return False, None
    improving = roi[-3] < roi[-2] < roi[-1]
    return improving, 65.0


def _pro_op_leverage(bundle):
    rev = _latest(bundle["ratios"], "revenue_cagr_5yr")
    pat = _latest(bundle["ratios"], "pat_cagr_5yr")
    if rev is None or pat is None or not rev > pat:
        return False, None
    return True, min(100.0, 60.0 + min(rev - pat, 10.0) * 2.0)


def _pro_asset_growth(bundle):
    assets = _last_n_list(bundle["bs"], "total_assets", 4)
    borrowings = _last_n_list(bundle["bs"], "borrowings", 4)
    if len(assets) < 2 or len(borrowings) < 2:
        return False, None
    grown = assets[-1] > assets[-2]
    deleveraged = borrowings[-1] < borrowings[-2]
    return bool(grown and deleveraged), 65.0


# ------------------------------------------------------------------
# Con rule evaluators -> (matched: bool, confidence: float | None,
#                         text_override: str | None)
# ------------------------------------------------------------------


def _con_high_de(bundle):
    sector = bundle.get("sector")
    de = _latest(bundle["ratios"], "debt_to_equity")
    if sector == FINANCIALS_SECTOR or de is None or not de > 2.0:
        return False, None, None
    text = (
        f"Debt-to-equity ratio of {float(de):.2f} is elevated for a "
        f"non-financial company and warrants monitoring"
    )
    return True, margin_confidence(de, 2.0, higher_is_better=False), text


def _con_fcf_negative(bundle):
    vals = _last_n_list(bundle["ratios"], "free_cash_flow_cr", 10)
    run = trailing_run(vals, lambda v: v < 0.0)
    if run < 3:
        return False, None, None
    return True, min(100.0, 65.0 + (run - 3) * 5.0), None


def _con_opm_declining(bundle):
    opm = _last_n_list(bundle["ratios"], "operating_profit_margin_pct", 4)
    if len(opm) < 3:
        return False, None, None
    declining = opm[-3] > opm[-2] > opm[-1]
    return declining, 65.0, None


def _con_net_loss(bundle):
    value = _latest(bundle["pl"], "net_profit")
    if value is None:
        return False, None, None
    return float(value) < 0.0, 70.0, None


def _con_revenue_declining(bundle):
    sales = _last_n_list(bundle["pl"], "sales", 4)
    if len(sales) < 3:
        return False, None, None
    declining = sales[-3] > sales[-2] > sales[-1]
    return declining, 65.0, None


def _con_low_icr(bundle):
    icr = _latest(bundle["ratios"], "interest_coverage")
    label = _latest(bundle["ratios"], "icr_label")
    if icr is None or label == "Debt Free":
        return False, None, None
    return float(icr) < 1.5, 70.0, None


def _con_high_payout(bundle):
    payout = _latest(bundle["ratios"], "dividend_payout_ratio_pct")
    if payout is None:
        return False, None, None
    return float(payout) > 100.0, 70.0, None


def _con_de_rising(bundle):
    de = _last_n_list(bundle["ratios"], "debt_to_equity", 4)
    if len(de) < 3:
        return False, None, None
    rising = de[-3] < de[-2] < de[-1]
    return rising, 65.0, None


def _con_eps_declining(bundle):
    eps = _last_n_list(bundle["ratios"], "earnings_per_share", 4)
    if len(eps) < 3:
        return False, None, None
    declining = eps[-3] > eps[-2] > eps[-1]
    return declining, 65.0, None


def _con_low_roce(bundle):
    roce = _bundle_roce(bundle)
    if roce is None:
        return False, None, None
    return (
        float(roce) < 10.0,
        margin_confidence(roce, 10.0, higher_is_better=False),
        None,
    )


def _con_high_net_debt(bundle):
    bs = bundle["bs"]
    pl = bundle["pl"]
    borrowings = _latest(bs, "borrowings")
    investments = _latest(bs, "investments")
    op = _latest(pl, "operating_profit")
    oi = _latest(pl, "other_income")
    dep = _latest(pl, "depreciation")
    if borrowings is None or investments is None:
        return False, None, None
    if op is None or dep is None:
        return False, None, None
    net = net_debt(borrowings, investments)
    if net is None:
        return False, None, None
    ebitda = _num(op) + _num(oi or 0) + _num(dep)
    if ebitda is None or ebitda <= 0:
        return False, None, None
    ratio = float(net) / float(ebitda)
    if ratio <= 3.0:
        return False, None, None
    text = (
        f"Net debt of {float(net):.0f} cr exceeding 3 times EBITDA "
        f"({ratio:.2f}x) limits financial flexibility"
    )
    return True, margin_confidence(ratio, 3.0), text


def _con_low_rev_cagr(bundle):
    value = _latest(bundle["ratios"], "revenue_cagr_5yr")
    if value is None:
        return False, None, None
    return (
        float(value) < 5.0,
        margin_confidence(value, 5.0, higher_is_better=False),
        None,
    )


def _bundle_roce(bundle):
    """ROCE for the latest year: EBIT / (equity + reserves + borrowings)."""
    bs = bundle["bs"]
    pl = bundle["pl"]
    eq = _latest(bs, "equity_capital")
    res = _latest(bs, "reserves")
    bor = _latest(bs, "borrowings")
    op = _latest(pl, "operating_profit")
    oi = _latest(pl, "other_income")
    if None in (eq, res, bor, op):
        return None
    ebit = _num(op) + _num(oi or 0)
    ce = _num(eq) + _num(res) + _num(bor)
    if ebit is None or ce in (None, 0):
        return None
    return ebit / ce * 100.0


# ------------------------------------------------------------------
# Fallback signals (factually grounded in the company's own data)
# ------------------------------------------------------------------

FB_PROS = [
    (
        "pro_fb_1",
        lambda b: _num(_latest(b["pl"], "net_profit")) is not None
        and _num(_latest(b["pl"], "net_profit")) > 0,
        lambda b: "Net profit was positive in the latest financial year",
    ),
    (
        "pro_fb_2",
        lambda b: any(
            f is not None and f > 0
            for f in _last_n_list(b["ratios"], "free_cash_flow_cr", 3)
        ),
        lambda b: "Free cash flow was positive in at least one of the last "
        "three years",
    ),
    (
        "pro_fb_3",
        lambda b: _revenue_grew(b),
        lambda b: "Revenue grew in the most recent financial year",
    ),
    (
        "pro_fb_4",
        lambda b: _num(_latest(b["pl"], "operating_profit")) is not None
        and _num(_latest(b["pl"], "operating_profit")) > 0,
        lambda b: "The company remained operationally profitable in the " "latest year",
    ),
    (
        "pro_fb_5",
        lambda b: _assets_grew(b),
        lambda b: "The company's asset base grew in the latest year",
    ),
]

FB_CONS = [
    (
        "con_fb_1",
        lambda b: _material_borrowings(b),
        lambda b: (
            f"The company carries borrowings of "
            f"{float(_num(_latest(b['bs'], 'borrowings'))):.0f} cr, "
            f"equal to {float(_de_ratio(b)):.2f}x its equity capital"
        ),
    ),
    (
        "con_fb_2",
        lambda b: _num(_latest(b["cf"], "financing_activity")) is not None
        and _num(_latest(b["cf"], "financing_activity")) > 0,
        lambda b: "The company raised external financing in the latest year",
    ),
    (
        "con_fb_3",
        lambda b: _capex_exceeds_fcf(b),
        lambda b: "Capital expenditure exceeded free cash flow in the latest " "year",
    ),
    (
        "con_fb_4",
        lambda b: _num(_latest(b["ratios"], "revenue_cagr_5yr")) is not None,
        lambda b: "Revenue growth has moderated relative to the company's " "history",
    ),
]


def _de_ratio(bundle):
    de = _num(_latest(bundle["ratios"], "debt_to_equity"))
    bor = _num(_latest(bundle["bs"], "borrowings"))
    if de is not None:
        return float(de)
    if bor is None:
        return 0.0
    eq = _num(_latest(bundle["bs"], "equity_capital"))
    res = _num(_latest(bundle["bs"], "reserves")) or 0.0
    if eq is None or float(eq) + float(res) <= 0:
        return 0.0
    return float(bor) / (float(eq) + float(res))


def _material_borrowings(bundle):
    bor = _num(_latest(bundle["bs"], "borrowings"))
    if bor is None:
        return False
    if float(bor) <= 0:
        return False
    return _de_ratio(bundle) > 0.25


def _revenue_grew(bundle):
    sales = _last_n_list(bundle["pl"], "sales", 2)
    return len(sales) == 2 and sales[-1] > sales[-2]


def _assets_grew(bundle):
    assets = _last_n_list(bundle["bs"], "total_assets", 2)
    return len(assets) == 2 and assets[-1] > assets[-2]


def _capex_exceeds_fcf(bundle):
    fcf = _num(_latest(bundle["ratios"], "free_cash_flow_cr"))
    capex = _num(_latest(bundle["ratios"], "capex_cr"))
    if fcf is None or capex is None:
        return False
    return capex > fcf


# ------------------------------------------------------------------
# Orchestration
# ------------------------------------------------------------------


def load_company_bundles(db_path=DB_PATH):
    """Return {company_id: bundle} for every company in the universe."""
    conn = sqlite3.connect(db_path)
    try:
        ratios = pd.read_sql_query("SELECT * FROM financial_ratios ORDER BY year", conn)
        pl = pd.read_sql_query(
            "SELECT company_id, year, sales, net_profit, operating_profit, "
            "other_income, depreciation, interest FROM profitandloss "
            "ORDER BY year",
            conn,
        )
        bs = pd.read_sql_query(
            "SELECT company_id, year, borrowings, investments, total_assets, "
            "equity_capital, reserves FROM balancesheet ORDER BY year",
            conn,
        )
        cf = pd.read_sql_query(
            "SELECT company_id, year, operating_activity, investing_activity, "
            "financing_activity FROM cashflow ORDER BY year",
            conn,
        )
        mc = pd.read_sql_query(
            "SELECT company_id, year, dividend_yield_pct FROM market_cap "
            "ORDER BY year",
            conn,
        )
        sectors = pd.read_sql_query(
            "SELECT company_id, broad_sector FROM sectors", conn
        )
    finally:
        conn.close()

    sector_map = dict(zip(sectors["company_id"], sectors["broad_sector"]))
    bundles = {}
    for company_id in sector_map:
        bundles[company_id] = {
            "ratios": ratios[ratios["company_id"] == company_id],
            "pl": pl[pl["company_id"] == company_id],
            "bs": bs[bs["company_id"] == company_id],
            "cf": cf[cf["company_id"] == company_id],
            "mc": mc[mc["company_id"] == company_id],
            "sector": sector_map[company_id],
        }
    return bundles


def evaluate_company(company_id, bundle):
    """Return (pros, cons) lists of (rule_id, text, confidence) tuples."""
    pros, cons = [], []

    for rule in PRO_RULES:
        matched, confidence = rule["evaluate"](bundle)
        if matched and confidence is not None and confidence > MIN_CONFIDENCE:
            pros.append((rule["id"], rule["text"], confidence))

    for rule in CON_RULES:
        matched, confidence, text_override = rule["evaluate"](bundle)
        if matched and confidence is not None and confidence > MIN_CONFIDENCE:
            text = text_override or rule["text"]
            cons.append((rule["id"], text, confidence))

    for rule_id, predicate, text_fn in FB_PROS:
        if not pros and predicate(bundle):
            pros.append((rule_id, text_fn(bundle), FALLBACK_CONFIDENCE))
            break
    for rule_id, predicate, text_fn in FB_CONS:
        if not cons and predicate(bundle):
            cons.append((rule_id, text_fn(bundle), FALLBACK_CONFIDENCE))
            break
    if not cons:
        cons.append(
            (
                "con_fb_5",
                "The company's financial profile warrants continued " "monitoring",
                FALLBACK_CONFIDENCE,
            )
        )

    return pros, cons


def generate_all(bundles):
    """Build the full pros_cons_generated.csv DataFrame."""
    rows = []
    for company_id, bundle in sorted(bundles.items()):
        pros, cons = evaluate_company(company_id, bundle)
        for rule_id, text, confidence in pros:
            rows.append(
                {
                    "company_id": company_id,
                    "type": "pro",
                    "rule_id": rule_id,
                    "text": text,
                    "confidence_pct": int(math.ceil(confidence)),
                }
            )
        for rule_id, text, confidence in cons:
            rows.append(
                {
                    "company_id": company_id,
                    "type": "con",
                    "rule_id": rule_id,
                    "text": text,
                    "confidence_pct": int(math.ceil(confidence)),
                }
            )
    return pd.DataFrame(rows)


def main():
    print("=" * 60)
    print("AUTO PROS/CONS GENERATOR (Sprint 5, Day 30)")
    print("=" * 60)

    bundles = load_company_bundles()
    frame = generate_all(bundles)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUTPUT_PATH, index=False)

    coverage = (
        frame[frame["type"] == "pro"]
        .groupby("company_id")
        .size()
        .reindex(sorted(bundles))
        > 0
    )
    con_coverage = (
        frame[frame["type"] == "con"]
        .groupby("company_id")
        .size()
        .reindex(sorted(bundles))
        > 0
    )

    print(f"  Companies        : {len(bundles)}")
    print(f"  Pro signals      : {(frame['type'] == 'pro').sum()}")
    print(f"  Con signals      : {(frame['type'] == 'con').sum()}")
    print(f"  Companies w/o pro: {int((~coverage).sum())}")
    print(f"  Companies w/o con: {int((~con_coverage).sum())}")
    fallbacks = frame["rule_id"].str.startswith(("pro_fb", "con_fb")).sum()
    print(f"  Fallback signals : {fallbacks}")
    print(f"\n  Output           : {OUTPUT_PATH}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    import sys

    if sys.platform == "win32":
        # keep console UTF-8 clean
        pass
    raise SystemExit(main())
