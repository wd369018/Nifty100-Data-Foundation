"""Portfolio summary PDF (Sprint 5, Day 35).

One page per company (alphabetical). Each page shows YoY trend arrows
(up / down / flat within 2%) for the core KPIs plus an auto-generated
retrospective paragraph.

Run:  python -m src.reports.portfolio_report
"""

import io
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

DB_PATH = Path("db/nifty100.db")
OUT_PATH = Path("reports/portfolio/portfolio_summary.pdf")

NAVY = colors.HexColor("#0F2B5B")
GOLD = colors.HexColor("#C9A227")
GREEN = colors.HexColor("#1E7D32")
RED = colors.HexColor("#C62828")
GREY = colors.HexColor("#5F6368")
LIGHT = colors.HexColor("#F2F4F8")

FLAT_BAND_PCT = 2.0

UP = "\u2191"
DOWN = "\u2193"
FLAT = "\u2192"


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
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    return f"{value:,.{decimals}f}"


# ------------------------------------------------------------------
# Data
# ------------------------------------------------------------------


def _year_series(company_id, db_path):
    """Return per-year metric dicts (oldest -> newest) for one company."""

    conn = sqlite3.connect(db_path)
    try:
        pl = pd.read_sql_query(
            "SELECT year, sales, net_profit, operating_profit, "
            "other_income, depreciation FROM profitandloss "
            f"WHERE company_id = '{company_id}' ORDER BY year",
            conn,
        )
        bs = pd.read_sql_query(
            "SELECT year, equity_capital, reserves, borrowings, investments "
            "FROM balancesheet "
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

    bs_by_year = {}
    for _, r in bs.iterrows():
        eq = _num(r.get("equity_capital"))
        res = _num(r.get("reserves"))
        bor = _num(r.get("borrowings"))
        bs_by_year[str(r["year"])] = (
            (eq + res) if (eq is not None and res is not None) else None,
            bor,
        )
    cf_by_year = {}
    for _, r in cf.iterrows():
        cf_by_year[str(r["year"])] = (
            _num(r.get("operating_activity")),
            _num(r.get("investing_activity")),
        )

    out = []
    for _, r in pl.iterrows():
        year = str(r["year"])
        sales = _num(r.get("sales"))
        net = _num(r.get("net_profit"))
        op = _num(r.get("operating_profit"))
        oi = _num(r.get("other_income"))
        dep = _num(r.get("depreciation"))
        equity, bor = bs_by_year.get(year, (None, None))
        cfo, cfi = cf_by_year.get(year, (None, None))

        opm = op / sales * 100.0 if (op is not None and sales) else None
        roe = net / equity * 100.0 if (net is not None and equity) else None
        ebit = None
        if op is not None:
            ebit = op + (oi or 0.0) + (dep or 0.0)
        roce = (
            ebit / (equity + bor or 1) * 100.0
            if (
                ebit is not None
                and equity is not None
                and bor is not None
                and equity + bor
            )
            else None
        )
        de = bor / equity if (bor is not None and equity) else None
        fcf = cfo + cfi if (cfo is not None and cfi is not None) else None

        out.append(
            {
                "year": year,
                "revenue": sales,
                "net_profit": net,
                "opm": opm,
                "roe": roe,
                "roce": roce,
                "de": de,
                "fcf": fcf,
            }
        )
    return out


def _delta(label, latest, prior):
    """Return (arrow, delta_text, direction_bad) for a KPI row."""

    if latest is None or prior is None or abs(prior) < 1e-9:
        return FLAT, "--", False

    if label == "Debt / Equity":
        pct = (latest - prior) / abs(prior) * 100.0
        bad = pct > FLAT_BAND_PCT
    else:
        pct = (latest - prior) / abs(prior) * 100.0
        bad = pct < -FLAT_BAND_PCT

    if abs(pct) <= FLAT_BAND_PCT:
        arrow, text = FLAT, "flat"
    elif pct > 0:
        arrow, text = UP, f"+{pct:.1f}%"
    else:
        arrow, text = DOWN, f"{pct:.1f}%"

    return arrow, text, bad


def build_portfolio_rows(db_path=DB_PATH):
    """All company pages: (company_id, name, sector, rows, narrative)."""

    conn = sqlite3.connect(db_path)
    try:
        companies = pd.read_sql_query("SELECT id, company_name FROM companies", conn)
        sectors = pd.read_sql_query(
            "SELECT company_id, broad_sector FROM sectors", conn
        )
    finally:
        conn.close()

    sector_map = dict(zip(sectors["company_id"], sectors["broad_sector"]))
    name_map = dict(zip(companies["id"], companies["company_name"]))

    pages = []
    for company_id in sorted(name_map):
        series = _year_series(company_id, db_path)
        if len(series) < 2:
            continue
        latest = series[-1]
        prior = series[-2]

        metric_rows = []
        for label, key, decimals in (
            ("Revenue (Rs Cr)", "revenue", 0),
            ("Net Profit (Rs Cr)", "net_profit", 0),
            ("Operating Margin %", "opm", 1),
            ("Return on Equity %", "roe", 1),
            ("Return on Capital %", "roce", 1),
            ("Free Cash Flow (Rs Cr)", "fcf", 0),
            ("Debt / Equity", "de", 2),
        ):
            arrow, delta_text, _ = _delta(label, latest[key], prior[key])
            metric_rows.append(
                {
                    "label": label,
                    "latest": _fmt(latest[key], decimals),
                    "prior": _fmt(prior[key], decimals),
                    "arrow": arrow,
                    "delta": delta_text,
                }
            )

        pages.append(
            {
                "company_id": company_id,
                "name": name_map[company_id],
                "sector": sector_map.get(company_id, "--"),
                "year": latest["year"],
                "rows": metric_rows,
                "narrative": _narrative(latest, prior),
            }
        )
    return pages


def _narrative(latest, prior):
    sentences = []

    rev = _growth_pct(latest["revenue"], prior["revenue"])
    profit = _growth_pct(latest["net_profit"], prior["net_profit"])

    if rev is None:
        sentences.append("Revenue trend could not be compared with the " "prior year.")
    elif rev > FLAT_BAND_PCT:
        sentences.append(f"Revenue grew {rev:.1f}% year on year.")
    elif rev < -FLAT_BAND_PCT:
        sentences.append(f"Revenue contracted {rev:.1f}% year on year.")
    else:
        sentences.append("Revenue was broadly flat year on year.")

    if profit is not None:
        if profit > rev + FLAT_BAND_PCT:
            sentences.append(
                "Profit growth outpaced revenue, pointing to "
                "improved operating leverage."
            )
        elif profit < rev - FLAT_BAND_PCT:
            sentences.append(
                "Profit growth lagged revenue, indicating " "margin pressure."
            )

    opm_delta = _pp_delta(latest["opm"], prior["opm"])
    if opm_delta is not None and abs(opm_delta) >= 0.5:
        direction = "improved" if opm_delta > 0 else "compressed"
        sentences.append(
            f"Operating margins {direction} by {abs(opm_delta):.1f} points."
        )

    fcf_delta = _growth_pct(latest["fcf"], prior["fcf"])
    if fcf_delta is not None and abs(fcf_delta) > FLAT_BAND_PCT:
        sentences.append(
            "Free cash flow strengthened."
            if fcf_delta > 0
            else "Free cash flow weakened."
        )

    de_latest, de_prior = latest["de"], prior["de"]
    if de_latest is not None and de_prior is not None:
        if de_latest > de_prior * (1 + FLAT_BAND_PCT / 100.0):
            sentences.append("Leverage increased versus the prior year.")

    return sentences


def _growth_pct(latest, prior):
    if latest is None or prior is None or abs(prior) < 1e-9:
        return None
    return (latest - prior) / abs(prior) * 100.0


def _pp_delta(latest, prior):
    if latest is None or prior is None:
        return None
    return latest - prior


# ------------------------------------------------------------------
# PDF assembly
# ------------------------------------------------------------------


def _page_flowables(page):
    from html import escape as _esc

    title = ParagraphStyle(
        "title",
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=colors.white,
    )
    sub = ParagraphStyle(
        "sub", fontName="Helvetica", fontSize=9, leading=12, textColor=colors.white
    )
    hdr = ParagraphStyle(
        "hdr",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=10,
        textColor=colors.white,
        alignment=1,
        wordWrap="CJK",
    )
    cell = ParagraphStyle(
        "cell",
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        alignment=1,
        wordWrap="CJK",
    )
    narr = ParagraphStyle(
        "narr", fontName="Helvetica", fontSize=9, leading=13, wordWrap="CJK"
    )

    flowables = []

    meta = f"{_esc(page['name'])}  |  {_esc(page['sector'])}  |  FY " f"{page['year']}"
    header = Table(
        [
            [Paragraph(meta, title)],
            [
                Paragraph(
                    f"{_esc(page['company_id'])}  |  Portfolio "
                    f"Summary - Retrospective Review",
                    sub,
                )
            ],
        ]
    )
    header.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), NAVY),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    flowables.append(header)
    flowables.append(Spacer(1, 5 * mm))

    data = [
        [
            Paragraph("Metric", hdr),
            Paragraph("Latest", hdr),
            Paragraph("Prior", hdr),
            Paragraph("Trend", hdr),
            Paragraph("Delta", hdr),
        ]
    ]
    for r in page["rows"]:
        arrow_color = GREEN.hexval().replace("0x", "#")
        if r["arrow"] == DOWN:
            arrow_color = RED.hexval().replace("0x", "#")
        trend = f'<font color="{arrow_color}">{r["arrow"]}</font>'
        data.append(
            [
                Paragraph(r["label"], cell),
                Paragraph(r["latest"], cell),
                Paragraph(r["prior"], cell),
                Paragraph(trend, cell),
                Paragraph(r["delta"], cell),
            ]
        )
    table = Table(
        data, repeatRows=1, colWidths=[74 * mm, 30 * mm, 30 * mm, 22 * mm, 26 * mm]
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    flowables.append(table)
    flowables.append(Spacer(1, 5 * mm))

    heading = ParagraphStyle(
        "heading", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=NAVY
    )
    flowables.append(Paragraph("Retrospective", heading))
    flowables.append(Spacer(1, 2 * mm))
    for sentence in page["narrative"]:
        flowables.append(Paragraph(f"\u2022  {sentence}", narr))
    flowables.append(Spacer(1, 4 * mm))

    return flowables


def build_pdf(pages):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title="Nifty 100 Portfolio Summary",
    )
    story = []
    for i, page in enumerate(pages):
        story.extend(_page_flowables(page))
        if i != len(pages) - 1:
            story.append(PageBreak())
    doc.build(story)
    return buf.getvalue()


def main():
    print("=" * 60)
    print("PORTFOLIO SUMMARY (Sprint 5, Day 35)")
    print("=" * 60)
    pages = build_portfolio_rows()
    pdf = build_pdf(pages)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_bytes(pdf)
    print(f"  Companies   : {len(pages)} pages (alphabetical)")
    print(f"  Output      : {OUT_PATH} ({OUT_PATH.stat().st_size} bytes)")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
