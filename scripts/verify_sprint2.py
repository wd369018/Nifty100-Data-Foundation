import sqlite3

DB = "db/nifty100.db"

with sqlite3.connect(DB) as con:
    cur = con.cursor()

    rows = cur.execute("SELECT COUNT(*) FROM financial_ratios").fetchone()[0]
    coys = cur.execute(
        "SELECT COUNT(DISTINCT company_id) FROM financial_ratios"
    ).fetchone()[0]
    print(f"financial_ratios rows           : {rows}")
    print(f"distinct companies              : {coys}")

    fk = cur.execute("""
        SELECT COUNT(*) FROM financial_ratios f
        LEFT JOIN companies c ON c.id = f.company_id
        WHERE c.id IS NULL
        """).fetchone()[0]
    print(f"FK violations (coys absent)     : {fk}")

    cols = [
        "net_profit_margin_pct",
        "operating_profit_margin_pct",
        "return_on_equity_pct",
        "return_on_assets_pct",
        "debt_to_equity",
        "interest_coverage",
        "asset_turnover",
        "free_cash_flow_cr",
        "capex_cr",
        "earnings_per_share",
        "book_value_per_share",
        "dividend_payout_ratio_pct",
        "total_debt_cr",
        "cash_from_operations_cr",
        "revenue_cagr_5yr",
        "pat_cagr_5yr",
        "eps_cagr_5yr",
        "composite_quality_score",
        "high_leverage_flag",
        "icr_label",
        "icr_warning_flag",
    ]
    null_cols = []
    counts = {}
    for c in cols:
        n = cur.execute(
            f"SELECT COUNT(*) FROM financial_ratios WHERE {c} IS NULL"
        ).fetchone()[0]
        counts[c] = rows - n
        if n == rows:
            null_cols.append(c)
    all_null = null_cols if null_cols else "NONE"
    print(f"all-null computed columns       : {all_null}")
    for c in [
        "return_on_equity_pct",
        "net_profit_margin_pct",
        "debt_to_equity",
        "revenue_cagr_5yr",
        "pat_cagr_5yr",
        "eps_cagr_5yr",
        "composite_quality_score",
    ]:
        print(f"  populated {c:28s}: {counts[c]:5d}")

    hl = cur.execute(
        "SELECT COUNT(*) FROM financial_ratios WHERE high_leverage_flag = 'True'"
    ).fetchone()[0]
    hl_fin = cur.execute("""
        SELECT COUNT(*) FROM financial_ratios f
        JOIN sectors s ON s.company_id = f.company_id
        WHERE f.high_leverage_flag = 'True' AND s.broad_sector = 'Financials'
        """).fetchone()[0]
    labels = [
        r[0] for r in cur.execute("SELECT DISTINCT icr_label FROM financial_ratios")
    ]
    warn = cur.execute(
        "SELECT COUNT(*) FROM financial_ratios WHERE icr_warning_flag = 'True'"
    ).fetchone()[0]
    print(f"high_leverage_flag True         : {hl}")
    print(f"high_leverage_flag True (Fin)   : {hl_fin}")
    print(f"icr_label distinct values       : {labels}")
    print(f"icr_warning_flag True           : {warn}")

    for c in ["high_leverage_flag", "icr_warning_flag"]:
        vals = [r[0] for r in cur.execute(f"SELECT DISTINCT {c} FROM financial_ratios")]
        print(f"distinct {c}: {vals}")

    cap_alloc = __import__("csv").DictReader(open("output/capital_allocation.csv"))
    labels2 = {}
    for r in cap_alloc:
        labels2[r["pattern_label"]] = labels2.get(r["pattern_label"], 0) + 1
    print(f"capital_allocation.csv labels   : {labels2}")

    line_count = sum(1 for _ in open("output/ratio_edge_cases.log"))
    print(f"ratio_edge_cases.log lines      : {line_count}")
