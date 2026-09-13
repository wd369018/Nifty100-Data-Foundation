"""Two-page PDF tearsheet generator (Sprint 5, Day 33/34).

Builds an investment tearsheet per company:

  Page 1 - Navy header, six KPI tiles, 10-year Revenue/Net Profit bar
           chart and a dual-axis ROE/ROCE line chart.
  Page 2 - Balance-sheet stacked bar, cash-flow waterfall, green pros,
           red cons and a capital-allocation badge.

Run:  python -m src.reports.tearsheet
"""

import io
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

DB_PATH = Path("db/nifty100.db")
PROS_CONS_PATH = Path("output/pros_cons_generated.csv")
OUT_DIR = Path("reports/tearsheets")

NAVY = colors.HexColor("#0F2B5B")
GOLD = colors.HexColor("#C9A227")
GREEN = colors.HexColor("#1E7D32")
RED = colors.HexColor("#C62828")
GREY = colors.HexColor("#5F6368")
LIGHT = colors.HexColor("#F2F4F8")

MIN_DATA_YEARS = 3

PAGE_WIDTH, PAGE_HEIGHT = A4


def _num(value):
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    import math

    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _fmt(value, decimals=1):
    if value is None:
        return "--"
    if abs(value) >= 1_000_000:
        return f"{value / 1000_000.0:,.1f}M"
    if abs(value) >= 1_000:
        return f"{value:,.0f}"
    return f"{value:,.{decimals}f}"


# ------------------------------------------------------------------
# Data loading
# ------------------------------------------------------------------


def load_company_data(company_id, db_path=DB_PATH):
    """Return every table slice needed for a tearsheet, plus meta."""

    conn = sqlite3.connect(db_path)
    try:
        company = pd.read_sql_query(
            f"SELECT id, company_name FROM companies WHERE id = " f"'{company_id}'",
            conn,
        )
        sectors = pd.read_sql_query(
            f"SELECT broad_sector FROM sectors WHERE company_id = " f"'{company_id}'",
            conn,
        )
        pl = pd.read_sql_query(
            "SELECT year, sales, net_profit, operating_profit, "
            "other_income, depreciation, interest FROM profitandloss "
            f"WHERE company_id = '{company_id}' ORDER BY year",
            conn,
        )
        bs = pd.read_sql_query(
            "SELECT year, equity_capital, reserves, borrowings, "
            "investments, total_assets FROM balancesheet "
            f"WHERE company_id = '{company_id}' ORDER BY year",
            conn,
        )
        cf = pd.read_sql_query(
            "SELECT year, operating_activity, investing_activity, "
            "financing_activity FROM cashflow "
            f"WHERE company_id = '{company_id}' ORDER BY year",
            conn,
        )
    finally:
        conn.close()

    name = company["company_name"].iloc[0] if not company.empty else company_id
    sector = sectors["broad_sector"].iloc[0] if not sectors.empty else None
    return {
        "company_id": company_id,
        "company_name": name,
        "sector": sector,
        "pl": pl,
        "bs": bs,
        "cf": cf,
    }


def load_pros_cons(company_id, path=PROS_CONS_PATH):
    """Pros/cons rows (text + type) for one company."""

    frame = pd.read_csv(path)
    frame = frame[frame["company_id"] == company_id]
    pros = frame[frame["type"] == "pro"]["text"].tolist()
    cons = frame[frame["type"] == "con"]["text"].tolist()
    return pros, cons


# ------------------------------------------------------------------
# KPIs
# ------------------------------------------------------------------


def compute_kpis(company):
    """Core KPIs for the six tiles, from latest years."""

    pl = company["pl"].sort_values("year")
    bs = company["bs"].sort_values("year")
    if pl.empty:
        return {}

    latest_row = pl.iloc[-1]
    latest_year = latest_row["year"]

    sales = _num(latest_row.get("sales"))
    net_profit = _num(latest_row.get("net_profit"))
    op = _num(latest_row.get("operating_profit"))
    other = _num(latest_row.get("other_income"))
    dep = _num(latest_row.get("depreciation"))

    eq = res = bor = None
    if not bs.empty:
        bs_latest = bs.iloc[-1]
        eq = _num(bs_latest.get("equity_capital"))
        res = _num(bs_latest.get("reserves"))
        bor = _num(bs_latest.get("borrowings"))

    equity = (eq + res) if (eq is not None and res is not None) else None
    ebit = None
    if op is not None:
        ebit = op + (other or 0.0) + (dep or 0.0)
    if ebit is not None and equity and bor is not None:
        roce = ebit / (equity + bor) * 100.0
    else:
        roce = None

    return {
        "year": str(latest_year),
        "revenue": sales,
        "net_profit": net_profit,
        "opm": (op / sales * 100.0) if (op is not None and sales) else None,
        "roe": (
            (net_profit / equity * 100.0)
            if (net_profit is not None and equity)
            else None
        ),
        "roce": roce,
        "de": (bor / equity) if (bor is not None and equity) else None,
        "equity": equity,
        "borrowings": bor,
    }


# ------------------------------------------------------------------
# Charts (matplotlib -> PNG bytes)
# ------------------------------------------------------------------


def _png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def chart_revenue_profit(company, width_in=9.2, height_in=3.0):
    """10-year Revenue vs Net Profit grouped bar chart."""

    pl = company["pl"].sort_values("year").tail(10)
    if pl.empty:
        return None
    years = [str(y) for y in pl["year"]]
    revenue = [_num(v) for v in pl["sales"]]
    profit = [_num(v) for v in pl["net_profit"]]

    fig, ax = plt.subplots(figsize=(width_in, height_in))
    x = range(len(years))
    ax.bar([i - 0.2 for i in x], revenue, width=0.4, label="Revenue", color="#3B74C4")
    ax.bar([i + 0.2 for i in x], profit, width=0.4, label="Net Profit", color="#C9A227")
    ax.set_xticks(list(x))
    ax.set_xticklabels([y[:4] for y in years], rotation=0, fontsize=7)
    ax.set_title("10-Year Revenue vs Net Profit (Rs Cr)")
    ax.legend(fontsize=7)
    ax.grid(axis="y", alpha=0.3)
    return _png(fig)


def chart_roe_roce(company, width_in=9.2, height_in=3.0):
    """Dual-axis ROE/ROCE line chart over the available history."""

    pl = company["pl"].sort_values("year").tail(10)
    bs = company["bs"].set_index("year")
    if pl.empty or bs.empty:
        return None
    years = [str(y) for y in pl["year"]]

    roe, roce = [], []
    for _, row in pl.iterrows():
        np_ = _num(row.get("net_profit"))
        op = _num(row.get("operating_profit"))
        oi = _num(row.get("other_income"))
        dep = _num(row.get("depreciation"))
        b = bs.get(row["year"], pd.Series(dtype=float))
        eq = _num(b.get("equity_capital")) if isinstance(b, pd.Series) else None
        res = _num(b.get("reserves")) if isinstance(b, pd.Series) else None
        bor = _num(b.get("borrowings")) if isinstance(b, pd.Series) else None
        eqv = None if (eq is None or res is None) else eq + res
        roe.append(np_ / eqv * 100.0 if (np_ is not None and eqv) else None)
        ebit = None
        if op is not None:
            ebit = op + (oi or 0.0) + (dep or 0.0)
        roce.append(
            ebit / (eqv + bor) * 100.0
            if (ebit is not None and eqv is not None and bor is not None and eqv + bor)
            else None
        )

    # bs index may be strings; use exact year match on the series index.
    fig, ax1 = plt.subplots(figsize=(width_in, height_in))
    x = range(len(years))
    ax1.plot(list(x), roe, marker="o", color="#1E7D32", label="ROE")
    ax1.set_ylabel("ROE (%)", fontsize=8)
    ax1.set_ylim(0, max([v for v in roe if v is not None] or [50]) * 1.15)
    ax2 = ax1.twinx()
    ax2.plot(list(x), roce, marker="s", color="#0F2B5B", label="ROCE")
    ax2.set_ylabel("ROCE (%)", fontsize=8)
    ax2.set_ylim(0, max([v for v in roce if v is not None] or [50]) * 1.15)
    ax1.set_xticks(list(x))
    ax1.set_xticklabels([y[:4] for y in years], fontsize=7)
    ax1.set_title("Return on Equity vs Return on Capital")
    lines = ax1.get_lines() + ax2.get_lines()
    ax1.legend(
        lines, [line.get_label() for line in lines], fontsize=7, loc="upper left"
    )
    ax1.grid(axis="y", alpha=0.3)
    return _png(fig)


def chart_balance_sheet(company, width_in=9.2, height_in=3.0):
    """Stacked balance-sheet bar chart (equity, borrowings, other)."""

    bs = company["bs"].sort_values("year").tail(10)
    if bs.empty:
        return None
    years = [str(y) for y in bs["year"]]
    equity, borrowings, other = [], [], []
    for _, row in bs.iterrows():
        eq = _num(row.get("equity_capital")) or 0.0
        res = _num(row.get("reserves")) or 0.0
        bor = _num(row.get("borrowings")) or 0.0
        assets = _num(row.get("total_assets")) or 0.0
        equity.append(eq + res)
        borrowings.append(bor)
        other.append(
            max(0.0, assets - (eq + res) + bor * 0 if assets > eq + res else 0.0)
        )

    fig, ax = plt.subplots(figsize=(width_in, height_in))
    x = range(len(years))
    ax.bar(x, equity, color="#1E7D32", label="Equity")
    ax.bar(x, borrowings, bottom=equity, color="#C62828", label="Borrowings")
    ax.bar(
        x,
        other,
        bottom=[e + b for e, b in zip(equity, borrowings)],
        color="#B0B7C3",
        label="Other Liabilities",
    )
    ax.set_xticks(list(x))
    ax.set_xticklabels([y[:4] for y in years], fontsize=7)
    ax.set_title("Balance Sheet Composition (Rs Cr)")
    ax.legend(fontsize=7)
    ax.grid(axis="y", alpha=0.3)
    return _png(fig)


def chart_cashflow_waterfall(company, width_in=9.2, height_in=3.0):
    """Cash-flow waterfall: CFO, CFI, CFF and the net change."""

    if company["cf"].empty or "year" not in company["cf"].columns:
        return None
    cf = company["cf"].sort_values("year").tail(1)
    if cf.empty:
        return None
    latest = cf.iloc[-1]
    cfo = _num(latest.get("operating_activity")) or 0.0
    cfi = _num(latest.get("investing_activity")) or 0.0
    cff = _num(latest.get("financing_activity")) or 0.0
    net = cfo + cfi + cff

    labels = ["CFO", "CFI", "CFF", "Net"]
    values = [cfo, cfi, cff, net]
    bottoms = [0.0]
    for v in values[:-1]:
        bottoms.append(bottoms[-1] + v)
    colors_list = ["#1E7D32", "#C62828", "#C9A227", "#0F2B5B"]

    fig, ax = plt.subplots(figsize=(width_in, height_in))
    ax.bar(range(4), values, bottom=[b for b in bottoms], color=colors_list, width=0.5)
    for i in range(3):
        ax.plot(
            [i + 0.25, i + 0.75],
            [bottoms[i + 1], bottoms[i + 1]],
            color="#5F6368",
            lw=0.8,
            alpha=0.7,
        )
    ax.set_xticks(range(4))
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_title("Latest-Year Cash Flow Waterfall (Rs Cr)")
    ax.grid(axis="y", alpha=0.3)
    for i, v in enumerate(values):
        ax.annotate(
            f"{v:,.0f}",
            (i, bottoms[i] + v),
            textcoords="offset points",
            xytext=(0, 4),
            ha="center",
            fontsize=7 if v else 0,
        )
    return _png(fig)


# ------------------------------------------------------------------
# PDF assembly
# ------------------------------------------------------------------


def _styles():
    title = ParagraphStyle(
        "title",
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.white,
    )
    subtitle = ParagraphStyle(
        "subtitle", fontName="Helvetica", fontSize=9, leading=12, textColor=colors.white
    )
    kpi_value = ParagraphStyle(
        "kpi_value",
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=17,
        textColor=NAVY,
        alignment=TA_CENTER,
        wordWrap="CJK",
    )
    kpi_label = ParagraphStyle(
        "kpi_label",
        fontName="Helvetica",
        fontSize=7.5,
        leading=9,
        textColor=GREY,
        alignment=TA_CENTER,
        wordWrap="CJK",
    )
    section = ParagraphStyle(
        "section", fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=NAVY
    )
    bullet = ParagraphStyle(
        "bullet",
        fontName="Helvetica",
        fontSize=8.5,
        leading=11.5,
        wordWrap="CJK",
        spaceAfter=2,
    )
    badge = ParagraphStyle(
        "badge",
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.white,
        alignment=TA_CENTER,
    )
    return title, subtitle, kpi_value, kpi_label, section, bullet, badge


def _header_flowable(company, kpis):
    from html import escape as _esc

    title, subtitle, kpi_value, kpi_label, *_ = _styles()
    meta = _esc(company["company_name"])
    if company["sector"]:
        meta += f"  |  {_esc(company['sector'])}"
    meta += f"  |  FY {kpis.get('year', '--')}" if kpis else meta
    table = Table(
        [
            [Paragraph(meta, title)],
            [
                Paragraph(
                    f"{_esc(company['company_id'])}  |  Nifty 100 "
                    f"Investment Tearsheet",
                    subtitle,
                )
            ],
        ]
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    return table


def _kpi_tiles(kpis):
    _, _, kpi_value, kpi_label, *_ = _styles()
    tiles = [
        ("Revenue (Rs Cr)", _fmt(kpis.get("revenue"))),
        ("Net Profit (Rs Cr)", _fmt(kpis.get("net_profit"))),
        ("Operating Margin (%)", _fmt(kpis.get("opm"))),
        ("Return on Equity (%)", _fmt(kpis.get("roe"))),
        ("Return on Capital (%)", _fmt(kpis.get("roce"))),
        ("Debt / Equity", _fmt(kpis.get("de"), 2)),
    ]
    cells = []
    for label, value in tiles:
        cell = Table([[Paragraph(value, kpi_value)], [Paragraph(label, kpi_label)]])
        cell.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.white),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        cells.append(cell)
    grid = Table([cells[0:3], cells[3:6]])
    grid.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                ("GRID", (0, 0), (-1, -1), 1, colors.white),
            ]
        )
    )
    return grid


def _chart_image(chart_bytes, width_mm=175):
    if chart_bytes is None:
        return Spacer(1, 4)
    from PIL import Image as PILImage

    PILImage.MAX_IMAGE_PIXELS = None
    with PILImage.open(chart_bytes) as im:
        w, h = im.size
    width = width_mm * mm
    height = width * h / w
    return Image(chart_bytes, width=width, height=height)


def _section_bullets(texts, color):
    from html import escape as _esc

    _, _, _, _, section, bullet, _ = _styles()
    hex_color = "#" + color.hexval()[2:]
    flowables = (
        [Paragraph("Pros", section)] if color == GREEN else [Paragraph("Cons", section)]
    )
    for text in texts:
        flowables.append(
            Paragraph(
                f'<font color="{hex_color}">\u25cf</font> ' f"{_esc(text)}", bullet
            )
        )
    return flowables


def _badge(pattern):
    _, _, _, _, _, _, badge = _styles()
    if pattern == "Distress Signal":
        color = RED
    elif pattern in ("Growth Funded by Debt", "Pre-Revenue"):
        color = GOLD
    else:
        color = NAVY
    label = f"Capital Allocation: {pattern}" if pattern else "Capital Allocation: --"
    done = Paragraph(label, badge)
    box = Table([[done]])
    box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), color),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return box


def build_tearsheet_pdf(company, pros, cons, kpis=None, pattern=None):
    """Return the two-page PDF as bytes for a single company."""

    kpis = kpis or compute_kpis(company)

    rev_chart = chart_revenue_profit(company)
    rr_chart = chart_roe_roce(company)
    bs_chart = chart_balance_sheet(company)
    cf_chart = chart_cashflow_waterfall(company)

    if any(chart is None for chart in (rev_chart, rr_chart, bs_chart, cf_chart)):
        return None  # not enough data - caller records the skip

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=f"Tearsheet {company['company_id']}",
    )

    story = []
    story.append(_header_flowable(company, kpis))
    story.append(Spacer(1, 5 * mm))
    story.append(_kpi_tiles(kpis))
    story.append(Spacer(1, 4 * mm))
    story.append(_chart_image(rev_chart))
    story.append(Spacer(1, 3 * mm))
    story.append(_chart_image(rr_chart))

    story.append(PageBreak())

    story.append(_header_flowable(company, kpis))
    story.append(Spacer(1, 4 * mm))
    story.append(_chart_image(bs_chart))
    story.append(Spacer(1, 3 * mm))
    story.append(_chart_image(cf_chart))
    story.append(Spacer(1, 4 * mm))

    if pros:
        story.extend(_section_bullets(pros, GREEN))
    if cons:
        story.extend(_section_bullets(cons, RED))
    story.append(Spacer(1, 4 * mm))
    story.append(_badge(pattern))

    doc.build(story)
    return buf.getvalue()


# ------------------------------------------------------------------
# Batch generation
# ------------------------------------------------------------------


def generate_one(company_id, db_path=DB_PATH, out_dir=OUT_DIR):
    """Build one tearsheet PDF; returns (path, size_bytes, skip_reason)."""

    out_dir.mkdir(parents=True, exist_ok=True)
    company = load_company_data(company_id, db_path=db_path)
    pros, cons = load_pros_cons(company_id)

    if len(company["pl"]) < MIN_DATA_YEARS:
        return (
            None,
            0,
            (f"only {len(company['pl'])} years of P&L data " f"(< {MIN_DATA_YEARS})"),
        )

    if len(company["bs"]) < MIN_DATA_YEARS or len(company["cf"]) < 1:
        return None, 0, "insufficient balance sheet / cash flow data"

    kpis = compute_kpis(company)

    pattern = _latest_pattern(db_path, company_id)

    pdf = build_tearsheet_pdf(company, pros, cons, kpis=kpis, pattern=pattern)
    if pdf is None:
        return None, 0, "not enough series data for charts"

    path = out_dir / f"{company_id}.pdf"
    path.write_bytes(pdf)
    return path, path.stat().st_size, None


def _latest_pattern(db_path, company_id, cfo_pat_ratio=None):
    """Latest-year capital-allocation pattern label from the live DB."""

    conn = sqlite3.connect(db_path)
    try:
        cf = pd.read_sql_query(
            "SELECT year, operating_activity, investing_activity, "
            "financing_activity FROM cashflow "
            f"WHERE company_id = '{company_id}' ORDER BY year",
            conn,
        )
        pl = pd.read_sql_query(
            "SELECT year, net_profit FROM profitandloss "
            f"WHERE company_id = '{company_id}' ORDER BY year",
            conn,
        )
    finally:
        conn.close()
    if cf.empty:
        return None
    latest = cf["year"].max()
    row = cf[cf["year"] == latest].iloc[-1]
    from src.analytics.cashflow_kpis import capital_allocation_pattern

    cfo = _num(row.get("operating_activity"))
    cfi = _num(row.get("investing_activity"))
    cff = _num(row.get("financing_activity"))
    pat_row = pl[pl["year"] == latest]
    if not pat_row.empty:
        pat = _num(pat_row["net_profit"].iloc[-1])
        ratio = (
            (cfo / pat)
            if (cfo is not None and pat is not None and abs(pat) > 1e-9)
            else None
        )
    else:
        ratio = None
    return capital_allocation_pattern(cfo, cfi, cff, ratio)


def generate_many(company_ids, db_path=DB_PATH, out_dir=OUT_DIR):
    """Batch-generate tearsheets; returns a summary DataFrame.

    Also writes output/skipped_tearsheets.csv with the companies that
    could not be produced (and the reason).
    """

    from src.analytics.capital_allocation_report import load_universe

    vou = load_universe(db_path)
    company_ids = [cid for cid in company_ids if cid in vou]

    results = []
    for company_id in sorted(company_ids):
        path, size, reason = generate_one(company_id, db_path, out_dir)
        results.append(
            {
                "company_id": company_id,
                "generated": path is not None,
                "size_bytes": int(size or 0),
                "skip_reason": reason,
            }
        )
    summary = pd.DataFrame(results)

    skipped = summary[~summary["generated"]][["company_id", "skip_reason"]]
    skip_path = Path("output/skipped_tearsheets.csv")
    skip_path.parent.mkdir(parents=True, exist_ok=True)
    skipped.to_csv(skip_path, index=False)

    return summary


def main():
    import sys

    print("=" * 60)
    print("TEARSHEET GENERATOR (Sprint 5, Days 33/34)")
    print("=" * 60)

    args = sys.argv[1:]
    if args and args[0] == "--all":
        from src.analytics.capital_allocation_report import load_universe

        tickers = sorted(load_universe())
        print(f"  Universe           : {len(tickers)} companies\n")
    else:
        tickers = args or ["TCS", "HDFCBANK", "RELIANCE", "SUNPHARMA", "TATASTEEL"]

    summary = generate_many(tickers)
    for _, row in summary.iterrows():
        status = "OK  " if row["generated"] else "SKIP"
        detail = (
            f"{row['size_bytes']} bytes" if row["generated"] else row["skip_reason"]
        )
        print(f"  [{status}] {row['company_id']:<12} {detail}")

    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
