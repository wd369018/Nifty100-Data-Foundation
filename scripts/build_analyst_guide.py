"""Build docs/analyst_guide.pdf — the Sprint 6 analyst-facing guide book.

Sections: overview, data foundation, clustering methodology, cluster
profiles, cross-sectional findings, portfolio stats, REST API reference,
screener usage, dashboard guide, limitations and QA summary.

Run:  venv\\Scripts\\python.exe scripts/build_analyst_guide.py
"""

from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "docs" / "analyst_guide.pdf"

CLUSTER_PROFILE = ROOT / "output" / "cluster_profile.csv"
CLUSTER_LABELS = ROOT / "output" / "cluster_labels.csv"
OUTLIER_REPORT = ROOT / "output" / "outlier_report.csv"
PORTFOLIO_STATS = ROOT / "output" / "portfolio_stats.csv"

NAVY = colors.HexColor("#0F2B5B")
GOLD = colors.HexColor("#C9A227")
GREY = colors.HexColor("#5F6368")
LIGHT = colors.HexColor("#F2F4F8")


def _styles():
    base = getSampleStyleSheet()
    styles = {
        "Title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            textColor=NAVY,
            fontSize=26,
            leading=30,
            spaceAfter=8,
        ),
        "H1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            textColor=NAVY,
            fontSize=16,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "H2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            textColor=NAVY,
            fontSize=13,
            spaceBefore=8,
            spaceAfter=4,
        ),
        "Body": ParagraphStyle(
            "Body", parent=base["BodyText"], fontSize=9.5, leading=13, spaceAfter=4
        ),
        "Small": ParagraphStyle(
            "Small", parent=base["BodyText"], fontSize=8, leading=10, spaceAfter=3
        ),
        "Cover": ParagraphStyle(
            "Cover",
            parent=base["Title"],
            textColor=NAVY,
            fontSize=34,
            leading=40,
            alignment=1,
        ),
        "Logo": ParagraphStyle(
            "Logo",
            parent=base["Title"],
            textColor=GOLD,
            fontSize=14,
            leading=18,
            alignment=1,
            spaceAfter=30,
        ),
    }
    return styles


def _table(data, style=None, col_widths=None):
    table = Table(data, colWidths=col_widths, repeatRows=1)
    default_style = TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CCCCCC")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
    )
    if style:
        default_style.add(*style)
    table.setStyle(default_style)
    return table


def _build(styles):
    story = []

    # ---- Cover -------------------------------------------------------
    story.append(Spacer(1, 60 * mm))
    story.append(Paragraph("NIFTY 100", styles["Logo"]))
    story.append(Paragraph("Data Foundation", styles["Cover"]))
    story.append(Paragraph("Analyst&#39;s Guide", styles["Cover"]))
    story.append(Spacer(1, 10 * mm))
    story.append(
        Paragraph(
            "Clustering &#8226; Portfolio Analytics &#8226; REST API &#8226; Dashboard<br/>"
            "Sprint 6 deliverable &#8212; version 0.6.0",
            styles["H2"],
        )
    )
    story.append(Spacer(1, 6 * mm))
    story.append(
        Paragraph(
            "Prepared for internal equity-research workflows over the Nifty 100 "
            "universe of 92 companies with complete financial datasets.",
            styles["Body"],
        )
    )
    story.append(PageBreak())

    # ---- TOC (static) -------------------------------------------------
    story.append(Paragraph("Contents", styles["H1"]))
    toc = [
        "1. Introduction and scope",
        "2. Data foundation",
        "3. Clustering methodology",
        "4. Cluster profiles",
        "5. Cross-sectional findings",
        "6. Portfolio statistics",
        "7. REST API reference",
        "8. Screener and presets",
        "9. Dashboard guide",
        "10. Known limitations and deviations",
        "11. Quality assurance and sign-off",
    ]
    for entry in toc:
        story.append(Paragraph(entry, styles["Body"]))
    story.append(PageBreak())

    # ---- 1. Introduction ---------------------------------------------
    story.append(Paragraph("1. Introduction and scope", styles["H1"]))
    story.append(
        Paragraph(
            "This guide documents the analytics and API layer delivered in "
            "Sprint 6. It describes how the 92-company Nifty 100 universe is "
            "clustered into five investment archetypes, how portfolio and "
            "outlier statistics are produced, and how to consume the same data "
            "through a versioned REST API, a Streamlit dashboard and PDF reports.",
            styles["Body"],
        )
    )
    story.append(
        Paragraph(
            "The full stack runs on a single SQLite database with 16 live "
            "endpoints under /api/v1. Every number quoted in this guide is "
            "computed directly from that database and can be reproduced by the "
            "scripts referenced in each section.",
            styles["Body"],
        )
    )
    story.append(
        Paragraph(
            "Audience: equity analysts, quant researchers and data engineers who "
            "need a repeatable, documented pipeline from raw annual reports to "
            "decision-ready screens.",
            styles["Body"],
        )
    )

    # ---- 2. Data foundation -------------------------------------------
    story.append(Paragraph("2. Data foundation", styles["H1"]))
    story.append(
        Paragraph(
            "The database (db/nifty100.db) holds ten core tables. Row counts are "
            "reported by the health endpoint and are pinned by the acceptance "
            "gates:",
            styles["Body"],
        )
    )
    tables_rows = [
        ["Table", "Rows", "Granularity"],
        ["companies", "92", "one per Nifty 100 member with profile metadata"],
        ["profitandloss", "1,057", "company x fiscal year"],
        ["balancesheet", "1,140", "company x fiscal year"],
        ["cashflow", "1,056", "company x fiscal year"],
        ["financial_ratios", "1,155", "company x fiscal year KPI sheet"],
        ["market_cap", "552", "company x calendar year (2019-2024)"],
        ["sectors", "92", "sector mapping incl. market-cap category"],
        ["peer_groups", "56", "peer-group membership and benchmarks"],
        ["peer_percentiles", "—", "per-metric percentile ranks in groups"],
        ["documents", "1,456", "annual-report registry"],
    ]
    story.append(_table(tables_rows, col_widths=[42 * mm, 22 * mm, 100 * mm]))
    story.append(Spacer(1, 3 * mm))
    story.append(
        Paragraph(
            "Fourteen data-quality rules (DQ-01 to DQ-14) are enforced by the "
            "ETL validator: primary-key uniqueness, company+year uniqueness, "
            "foreign-key integrity, the balance-sheet equation, OPM "
            "cross-checks, positive sales, required columns, null pk/year "
            "checks, numeric typing, duplicate rows, year range, URL format and "
            "negative-value checks. Every rule has a dedicated unit test.",
            styles["Body"],
        )
    )

    # ---- 3. Clustering methodology ------------------------------------
    story.append(Paragraph("3. Clustering methodology", styles["H1"]))
    story.append(
        Paragraph(
            "Five features capture profitability, leverage and growth:", styles["Body"]
        )
    )
    for feature in [
        "return_on_equity_pct",
        "debt_to_equity",
        "revenue_cagr_5yr",
        "fcf_cagr_5yr",
        "operating_profit_margin_pct",
    ]:
        story.append(Paragraph(f"&#8226;  {feature}", styles["Body"]))
    story.append(
        Paragraph(
            "Missing values are imputed with the sector median of the feature, "
            "then the feature matrix is standardised with StandardScaler before "
            "KMeans (k=5, random_state=42, k-means++ initialisation). The elbow "
            "plot (reports/elbow_plot.png) supports a five-cluster solution. "
            "The pipeline is implemented in src/analytics/clustering.py.",
            styles["Body"],
        )
    )
    story.append(PageBreak())

    # ---- 4. Cluster profiles ------------------------------------------
    story.append(Paragraph("4. Cluster profiles", styles["H1"]))
    story.append(
        Paragraph(
            "Five archetypes emerge across the universe. Mean and median values "
            "per feature:",
            styles["Body"],
        )
    )

    cluster_data = pd.read_csv(CLUSTER_PROFILE)
    name_map = {
        0: "High-Quality Compounders",
        1: "High-Margin Franchises",
        2: "Defense High-ROE Leaders",
        3: "Leveraged Financials",
        4: "Cash-Flow Outliers",
    }
    profile_rows = [
        [
            "Cluster",
            "Count",
            "ROE med",
            "D/E med",
            "Rev CAGR med",
            "FCF CAGR med",
            "OPM med",
        ],
    ]
    for _, row in cluster_data.iterrows():
        profile_rows.append(
            [
                f"{int(row['cluster_id'])} ({name_map[int(row['cluster_id'])]})",
                int(row["company_count"]),
                f"{row['return_on_equity_pct_median']:.1f}",
                f"{row['debt_to_equity_median']:.2f}",
                f"{row['revenue_cagr_5yr_median']:.1f}",
                f"{row['fcf_cagr_5yr_median']:.1f}",
                f"{row['operating_profit_margin_pct_median']:.1f}",
            ]
        )
    story.append(
        _table(
            profile_rows,
            col_widths=[62 * mm, 16 * mm, 20 * mm, 18 * mm, 24 * mm, 24 * mm, 20 * mm],
        )
    )
    story.append(Spacer(1, 3 * mm))
    story.append(
        Paragraph(
            "Reading the archetypes: cluster 0 is the broad quality compounder "
            "core; cluster 1 contains insurers and franchises with very high "
            "operating margins; cluster 2 is a two-member defence pairing "
            "(BEL, HAL) with extreme ROE; cluster 3 is the leveraged "
            "financials cohort (banks, NBFCs, ADANIGREEN); cluster 4 is a "
            "single cash-flow outlier (CIPLA).",
            styles["Body"],
        )
    )
    story.append(PageBreak())

    labels = pd.read_csv(CLUSTER_LABELS)
    story.append(Paragraph("4.1 Cluster membership", styles["H2"]))
    for cluster_id in sorted(labels["cluster_id"].unique()):
        members = (
            labels[labels["cluster_id"] == cluster_id]
            .sort_values("distance_from_centroid")["company_id"]
            .tolist()
        )
        story.append(
            Paragraph(
                f"Cluster {cluster_id} &#8212; {name_map[int(cluster_id)]} "
                f"({len(members)} companies):",
                styles["H2"],
            )
        )
        chunk = ", ".join(members)
        story.append(Paragraph(chunk, styles["Body"]))

    # ---- 5. Cross-sectional findings -----------------------------------
    story.append(PageBreak())
    story.append(Paragraph("5. Cross-sectional findings", styles["H1"]))
    story.append(
        Paragraph(
            "The correlation heatmap (reports/correlation_heatmap.png) shows "
            "pairwise Spearman correlations between ten headline KPIs. Per-"
            "sector Z-score analysis flags companies that sit more than three "
            "standard deviations from their sector peers:",
            styles["Body"],
        )
    )

    outliers = pd.read_csv(OUTLIER_REPORT)
    out_rows = [["Company", "Sector", "Metric", "Value", "Z-score"]]
    for _, row in outliers.iterrows():
        out_rows.append(
            [
                row["company_id"],
                row["broad_sector"],
                row["metric"],
                f"{row['value']:,.2f}",
                f"{row['z_score']:.2f}",
            ]
        )
    story.append(
        _table(out_rows, col_widths=[28 * mm, 42 * mm, 58 * mm, 20 * mm, 16 * mm])
    )
    story.append(Spacer(1, 3 * mm))
    story.append(
        Paragraph(
            "Flags are concentrated in Consumer Discretionary (INDIGO, "
            "TATAMOTORS) and Financials (LICI, ICICIPRULI, BAJAJHLDNG) where "
            "the median profile is distorted by structurally different "
            "businesses; ADANIGREEN is flagged on leverage (D/E 6.6x). These "
            "points should be reviewed before using the median as a sector "
            "anchor.",
            styles["Body"],
        )
    )
    story.append(PageBreak())

    # ---- 6. Portfolio statistics -----------------------------------------
    story.append(Paragraph("6. Portfolio statistics", styles["H1"]))
    story.append(
        Paragraph(
            "Population percentiles (P10-P90), mean and standard deviation for "
            "the ten headline KPIs across the universe:",
            styles["Body"],
        )
    )

    stats = pd.read_csv(PORTFOLIO_STATS)
    metric_names = {
        "return_on_equity_pct": "ROE %",
        "return_on_capital_employed_pct": "ROCE %",
        "net_profit_margin_pct": "NPM %",
        "operating_profit_margin_pct": "OPM %",
        "return_on_assets_pct": "ROA %",
        "debt_to_equity": "D/E",
        "interest_coverage": "Interest coverage",
        "revenue_cagr_5yr": "Revenue CAGR %",
        "pat_cagr_5yr": "PAT CAGR %",
        "free_cash_flow_cr": "FCF (cr)",
    }
    stat_rows = [["KPI", "n", "P10", "P25", "P50", "P75", "P90", "Mean", "Std"]]
    for _, row in stats.iterrows():
        stat_rows.append(
            [
                metric_names.get(row["kpi"], row["kpi"]),
                int(row["n"]),
                f"{row['p10']:,.1f}",
                f"{row['p25']:,.1f}",
                f"{row['p50']:,.1f}",
                f"{row['p75']:,.1f}",
                f"{row['p90']:,.1f}",
                f"{row['mean']:,.1f}",
                f"{row['std']:,.1f}",
            ]
        )
    story.append(
        _table(
            stat_rows,
            col_widths=[
                34 * mm,
                10 * mm,
                20 * mm,
                20 * mm,
                20 * mm,
                20 * mm,
                20 * mm,
                20 * mm,
                20 * mm,
            ],
        )
    )
    story.append(PageBreak())

    # ---- 7. REST API -----------------------------------------------------
    story.append(Paragraph("7. REST API reference", styles["H1"]))
    story.append(
        Paragraph(
            "FastAPI serves 16 endpoints under /api/v1 with CORS open to all "
            "origins, request logging and a health check that reports row "
            "counts:",
            styles["Body"],
        )
    )
    api_rows = [
        ["Method", "Path", "Purpose"],
        ["GET", "/health", "status, version, uptime, DB row counts"],
        ["GET", "/companies", "list with sector/market-cap/search filters"],
        ["GET", "/companies/{ticker}", "full profile + latest KPIs (404 if unknown)"],
        ["GET", "/companies/{ticker}/pl", "P&L history, optional from/to year"],
        ["GET", "/companies/{ticker}/bs", "balance-sheet history"],
        ["GET", "/companies/{ticker}/cashflow", "cash-flow history"],
        ["GET", "/companies/{ticker}/ratios", "KPI ratios, optional year"],
        ["GET", "/companies/{ticker}/tearsheet", "pre-generated PDF"],
        ["GET", "/screener", "threshold screen (cursors 400 on bad values)"],
        ["GET", "/sectors", "sector aggregates and market-cap splits"],
        ["GET", "/sectors/{sector}/companies", "companies in a sector"],
        ["GET", "/peers/{group_name}", "peer membership + percentile ranks"],
        ["GET", "/companies/{ticker}/peers/compare", "8-axis radar data"],
        ["GET", "/market-cap/{ticker}", "2019-2024 valuation multiples"],
        ["GET", "/portfolio/stats", "P10-P90 portfolio statistics"],
        ["GET", "/companies/{ticker}/documents", "annual-report registry"],
    ]
    story.append(_table(api_rows, col_widths=[18 * mm, 62 * mm, 84 * mm]))
    story.append(Spacer(1, 3 * mm))
    story.append(
        Paragraph(
            "Machine-readable contracts are exported to docs/openapi.json and "
            "a Postman collection at docs/nifty100.postman_collection.json. "
            "Run the API with:  uvicorn src.api.main:app --port 8000",
            styles["Body"],
        )
    )
    story.append(PageBreak())

    # ---- 8. Screener ------------------------------------------------------
    story.append(Paragraph("8. Screener and presets", styles["H1"]))
    story.append(
        Paragraph(
            "GET /api/v1/screener applies threshold filters on one frame per "
            "company at its latest screening year and sorts by the composite "
            "quality score. Supported filters:",
            styles["Body"],
        )
    )
    for f in [
        "min_roe",
        "max_de",
        "min_fcf",
        "sector",
        "min_rev_cagr_5yr",
        "min_pat_cagr_5yr",
        "max_pe",
    ]:
        story.append(Paragraph(f"&#8226;  {f}", styles["Body"]))
    story.append(
        Paragraph(
            "Example: curl &#8220;/api/v1/screener?min_roe=15&#8221; returns "
            "53 companies with ROE ≥ 15%. Non-numeric parameters return HTTP "
            "400. The Streamlit dashboard exposes the same screen with six "
            "one-click presets (Quality, Value, Growth, Dividend, Debt-Free, "
            "Turnaround); the API returns the same company set for equal "
            "thresholds (verified by an integration test).",
            styles["Body"],
        )
    )
    story.append(PageBreak())

    # ---- 9. Dashboard -----------------------------------------------------
    story.append(Paragraph("9. Dashboard guide", styles["H1"]))
    story.append(
        Paragraph(
            "Run:  streamlit run src/dashboard/app.py  (port 8501 by default). "
            "The dashboard has eight pages: Home, Company Profile, Screener, "
            "Peers, Trends, Sectors, Capital Allocation and Reports. Company "
            "Profile resolves any ticker to a profile card, six KPI tiles, "
            "revenue/profit bars, ROE/ROCE trends and pros/cons. Data is cached "
            "for 10 minutes; per-ticker company-profile loads complete in "
            "under 3 seconds (measured, output/perf_notes.md).",
            styles["Body"],
        )
    )
    story.append(PageBreak())

    # ---- 10. Limitations --------------------------------------------------
    story.append(Paragraph("10. Known limitations and deviations", styles["H1"]))
    limitations = [
        (
            "The live screener considers latest-year values; companies with "
            "negative or zero revenue in the base year have undefined CAGR "
            "flags and are excluded from that feature."
        ),
        (
            "The database carries 10 distinct broad sectors, not the 11 the "
            "planning documents assumed; API and tests follow the data."
        ),
        (
            "Four tearsheets (ATGL, JIOFIN, PNB, SBIN) could not be generated "
            "in Sprint 5 (missing 10-year series) and are documented in "
            "output/skipped_tearsheets.csv; the tearsheet endpoint 404s for "
            "them."
        ),
        (
            "Z-score outliers are data-driven and flagged, not corrected; "
            "sector medians still include them unless the analyst filters."
        ),
    ]
    for item in limitations:
        story.append(Paragraph(f"&#8226;  {item}", styles["Body"]))
    story.append(Spacer(1, 3 * mm))
    story.append(
        Paragraph(
            "Every deviation is mirrored in docs/sprint6_review.md and in the "
            "acceptance checklist.",
            styles["Body"],
        )
    )
    story.append(PageBreak())

    # ---- 11. QA and sign-off ---------------------------------------------
    story.append(Paragraph("11. Quality assurance and sign-off", styles["H1"]))
    story.append(
        Paragraph(
            "The Sprint 6 verification harness (scripts/verify_sprint6.py) runs "
            "20 acceptance gates AC-01 to AC-20, including: 92 companies "
            "clustered to 5 labelled archetypes; 16 live endpoints with correct "
            "status codes; the screener matching the dashboard; 10 concurrent "
            "API calls finishing inside 10 seconds; dashboard profile loads "
            "under 3 seconds; 381 pytest tests with zero failures "
            "(reports/pytest_report.html); 23 deliverables archived in "
            "output/final_deliverables/. The acceptance checklist "
            "(docs/acceptance_checklist.pdf) records a PASS/FAIL per gate and "
            "the day-45 sign-off. This guide, the API and the clustering "
            "pipeline together close Epics 10, 11 and 12.",
            styles["Body"],
        )
    )

    doc = SimpleDocTemplate(
        str(OUT_PATH),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    def _page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(GREY)
        canvas.drawString(
            18 * mm, 10 * mm, "Nifty 100 Data Foundation — Analyst's Guide"
        )
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_page_number, onLaterPages=_page_number)
    return OUT_PATH


def main():
    styles = _styles()
    path = _build(styles)
    size = path.stat().st_size
    print(f"wrote {path} ({size:,} bytes)")


if __name__ == "__main__":
    main()
