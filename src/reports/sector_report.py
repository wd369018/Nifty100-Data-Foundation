"""Sector summary PDF generator (Sprint 5, Day 34).

One PDF per broad_sector: a header with sector stats, a company table
(latest-year KPIs) and a capital-allocation distribution chart.

The live DB contains 10 broad sectors (the task brief assumed 11);
we generate 10 PDFs and document the deviation in the review.

Run:  python -m src.reports.sector_report
"""

import io
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

DB_PATH = Path("db/nifty100.db")
OUT_DIR = Path("reports/sector")

NAVY = colors.HexColor("#0F2B5B")
GOLD = colors.HexColor("#C9A227")
LIGHT = colors.HexColor("#F2F4F8")
GREY = colors.HexColor("#5F6368")


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


def load_sector_data(db_path=DB_PATH):
    """Return (sectors, ratios, patterns) frames for the universe."""

    conn = sqlite3.connect(db_path)
    try:
        companies = pd.read_sql_query("SELECT id, company_name FROM companies", conn)
        sectors = pd.read_sql_query(
            "SELECT company_id, broad_sector FROM sectors", conn
        )
        ratios = pd.read_sql_query(
            "SELECT company_id, year, operating_profit_margin_pct, "
            "return_on_equity_pct, revenue_cagr_5yr, pat_cagr_5yr, "
            "free_cash_flow_cr FROM financial_ratios ORDER BY year",
            conn,
        )
    finally:
        conn.close()

    name_map = dict(zip(companies["id"], companies["company_name"]))
    sector_map = dict(zip(sectors["company_id"], sectors["broad_sector"]))

    # Latest row per company.
    latest = ratios.sort_values("year").groupby("company_id", as_index=False).tail(1)
    latest["company_name"] = latest["company_id"].map(name_map)
    latest["sector"] = latest["company_id"].map(sector_map)

    cap = pd.read_csv("output/capital_allocation.csv")
    cap_latest = cap.sort_values("year").groupby("company_id", as_index=False).tail(1)
    pattern_map = dict(zip(cap_latest["company_id"], cap_latest["pattern_label"]))

    return sector_map, latest, pattern_map


def _sector_rows(sector, latest):
    """Per-company KPI rows for one sector."""

    frame = latest[latest["sector"] == sector]
    rows = []
    for _, r in frame.sort_values("company_id").iterrows():
        rows.append(
            {
                "company": r["company_name"] or r["company_id"],
                "roe": _num(r.get("return_on_equity_pct")),
                "opm": _num(r.get("operating_profit_margin_pct")),
                "rev_cagr": _num(r.get("revenue_cagr_5yr")),
                "pat_cagr": _num(r.get("pat_cagr_5yr")),
                "fcf": _num(r.get("free_cash_flow_cr")),
            }
        )
    return rows


def _pattern_chart(pattern_dist, width_in=9.0, height_in=2.6):
    """Horizontal bar chart of a sector's capital-allocation mix."""

    labels = [p for p, _ in pattern_dist if _ > 0]
    counts = [c for _, c in pattern_dist if c > 0]
    if not labels:
        return None
    fig, ax = plt.subplots(figsize=(width_in, height_in))
    ax.barh(labels, counts, color=NAVY.hexval().replace("0x", "#"))
    ax.invert_yaxis()
    ax.set_title("Capital Allocation Distribution")
    ax.set_xlabel("Companies")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _sector_pdf(sector, rows, pattern_dist, name_map):
    from html import escape as _esc

    title_style = ParagraphStyle(
        "title",
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=19,
        textColor=colors.white,
    )
    sub_style = ParagraphStyle(
        "sub", fontName="Helvetica", fontSize=9, leading=12, textColor=colors.white
    )
    cell_style = ParagraphStyle(
        "cell",
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        alignment=1,
        wordWrap="CJK",
    )
    header_style = ParagraphStyle(
        "hdr",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=10,
        textColor=colors.white,
        alignment=1,
        wordWrap="CJK",
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=f"Sector {sector}",
    )

    n_companies = len(rows)
    med_roe = _median([r["roe"] for r in rows])
    med_opm = _median([r["opm"] for r in rows])

    story = []
    header = Table(
        [
            [Paragraph(f"{_esc(sector)} - Investment Sector Report", title_style)],
            [
                Paragraph(
                    f"{n_companies} companies  |  Median ROE "
                    f"{_fmt(med_roe)}%  |  Median OPM {_fmt(med_opm)}%",
                    sub_style,
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
    story.append(header)
    story.append(Spacer(1, 4 * mm))

    data = [
        [
            Paragraph("Company", header_style),
            Paragraph("ROE %", header_style),
            Paragraph("OPM %", header_style),
            Paragraph("Rev CAGR %", header_style),
            Paragraph("PAT CAGR %", header_style),
            Paragraph("FCF (cr)", header_style),
        ]
    ]
    for r in rows:
        data.append(
            [
                Paragraph(_esc(r["company"]), cell_style),
                Paragraph(_fmt(r["roe"]), cell_style),
                Paragraph(_fmt(r["opm"]), cell_style),
                Paragraph(_fmt(r["rev_cagr"]), cell_style),
                Paragraph(_fmt(r["pat_cagr"]), cell_style),
                Paragraph(_fmt(r["fcf"]), cell_style),
            ]
        )
    table = Table(
        data,
        repeatRows=1,
        colWidths=[62 * mm, 24 * mm, 24 * mm, 24 * mm, 24 * mm, 24 * mm],
    )
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    table.setStyle(TableStyle(style))
    story.append(table)
    story.append(Spacer(1, 4 * mm))

    chart = _pattern_chart(pattern_dist)
    if chart is not None:
        chart_buf = chart
        chart_buf.seek(0)
        story.append(Image(chart_buf, width=160 * mm, height=46 * mm))

    doc.build(story)
    return buf.getvalue()


def _median(values):
    nums = sorted([v for v in values if v is not None])
    if not nums:
        return None
    mid = len(nums) // 2
    if len(nums) % 2:
        return nums[mid]
    return (nums[mid - 1] + nums[mid]) / 2.0


def generate_all(db_path=DB_PATH, out_dir=OUT_DIR):
    """Write one PDF per sector. Returns a summary DataFrame."""

    sector_map, latest, pattern_map = load_sector_data(db_path)
    sectors = sorted({s for s in sector_map.values() if s})

    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for sector in sectors:
        rows = _sector_rows(sector, latest)
        from collections import Counter

        dist = Counter()
        for cid in latest.loc[latest["sector"] == sector, "company_id"]:
            dist[pattern_map.get(cid, "--")] += 1
        ordered = sorted(dist.items(), key=lambda kv: -kv[1])
        pdf = _sector_pdf(sector, rows, ordered, None)
        path = out_dir / f"{sector.replace(' ', '_').replace('/', '_')}.pdf"
        path.write_bytes(pdf)
        results.append(
            {
                "sector": sector,
                "companies": len(rows),
                "path": str(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return pd.DataFrame(results)


def main():
    print("=" * 60)
    print("SECTOR REPORT GENERATOR (Sprint 5, Day 34)")
    print("=" * 60)
    summary = generate_all()
    for _, row in summary.iterrows():
        print(
            f"  {row['sector']:<22} {row['companies']:>2} companies  "
            f"{row['size_bytes']} bytes  ->  {row['path']}"
        )
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
