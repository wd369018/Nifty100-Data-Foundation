"""Cluster Profiling & Descriptive Statistics — Sprint 6, Day 37.

Profiles the 5 Day-36 clusters (mean/median per feature), generates the
10-KPI Pearson correlation heatmap, the per-sector Z-score outlier report
and the portfolio percentile statistics table.

Outputs:
    - output/cluster_profile.csv
    - reports/correlation_heatmap.png
    - output/outlier_report.csv
    - output/portfolio_stats.csv
"""

import sqlite3
from pathlib import Path

import matplotlib
import seaborn as sns

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.analytics.clustering import (
    CLUSTER_FEATURES,
    impute_sector_median,
    load_clustering_frame,
)

DB_PATH = Path("db/nifty100.db")
CLUSTER_LABELS_PATH = Path("output/cluster_labels.csv")

PROFILE_PATH = Path("output/cluster_profile.csv")
HEATMAP_PATH = Path("reports/correlation_heatmap.png")
OUTLIER_PATH = Path("output/outlier_report.csv")
STATS_PATH = Path("output/portfolio_stats.csv")

# The 10 core KPIs used for correlation heatmap and portfolio stats.
CORE_KPIS = [
    "return_on_equity_pct",
    "return_on_capital_employed_pct",
    "net_profit_margin_pct",
    "operating_profit_margin_pct",
    "return_on_assets_pct",
    "debt_to_equity",
    "interest_coverage",
    "revenue_cagr_5yr",
    "pat_cagr_5yr",
    "free_cash_flow_cr",
]

PERCENTILES = [0.10, 0.25, 0.50, 0.75, 0.90]


def _num(v):
    if v is None or pd.isna(v):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load_kpi_frame(db_path=DB_PATH):
    """92-row latest-year frame with CORE_KPIS + broad_sector."""
    from src.screener.engine import load_feature_frame

    frame = load_feature_frame(db_path=db_path)
    cols = ["company_id"] + [c for c in CORE_KPIS if c in frame.columns]
    out = frame[cols].copy()
    for col in CORE_KPIS:
        if col not in out.columns:
            out[col] = np.nan
        else:
            out[col] = out[col].apply(_num)
    con = sqlite3.connect(db_path)
    sectors = pd.read_sql("SELECT company_id, broad_sector FROM sectors", con)
    con.close()
    return out.merge(sectors, on="company_id", how="left")


# ------------------------------------------------------------------
# Cluster profiling (Day 37)
# ------------------------------------------------------------------


def profile_clusters(df, cluster_labels, features=CLUSTER_FEATURES):
    """Return mean/median of each feature per cluster, plus cluster size."""
    merged = df.merge(cluster_labels[["company_id", "cluster_id"]], on="company_id")
    rows = []
    for cid, group in merged.groupby("cluster_id"):
        row = {"cluster_id": cid, "company_count": len(group)}
        for feat in features:
            row[f"{feat}_mean"] = group[feat].mean()
            row[f"{feat}_median"] = group[feat].median()
        rows.append(row)
    return pd.DataFrame(rows).sort_values("cluster_id").reset_index(drop=True)


def write_profile(profile, path=PROFILE_PATH):
    """Write cluster_profile.csv."""
    path.parent.mkdir(parents=True, exist_ok=True)
    profile.to_csv(path, index=False)
    return path


# ------------------------------------------------------------------
# Correlation heatmap (Day 37)
# ------------------------------------------------------------------


def build_correlation_heatmap(frame, kpis=CORE_KPIS, output=HEATMAP_PATH):
    """Pearson correlation of the 10 KPIs; save annotated seaborn heatmap."""
    corr = frame[kpis].corr(method="pearson")
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(11, 9))
    sns.heatmap(
        corr,
        annot=True,
        fmt=".2f",
        cmap="RdBu_r",
        center=0,
        square=True,
        cbar_kws={"shrink": 0.8},
        ax=ax,
    )
    ax.set_title("Pearson Correlation — 10 Core KPIs (Nifty 100, latest year)")
    fig.tight_layout()
    fig.savefig(output, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output


# ------------------------------------------------------------------
# Outlier detection (Day 37)
# ------------------------------------------------------------------


def detect_outliers(frame, kpis=CORE_KPIS, z_threshold=3.0):
    """Flag companies with |Z-score| > threshold on any KPI within its sector.

    Returns a DataFrame with columns:
        company_id, broad_sector, metric, value, z_score
    """
    rows = []
    for sector, group in frame.groupby("broad_sector"):
        for metric in kpis:
            values = group[metric].dropna()
            if len(values) < 3:
                continue
            mean = values.mean()
            std = values.std(ddof=0)
            if std is None or std == 0 or pd.isna(std):
                continue
            z = (values - mean) / std
            flagged = z[abs(z) > z_threshold]
            for idx, zval in flagged.items():
                rows.append(
                    {
                        "company_id": group.loc[idx, "company_id"],
                        "broad_sector": sector,
                        "metric": metric,
                        "value": values.loc[idx],
                        "z_score": round(float(zval), 4),
                    }
                )
    return pd.DataFrame(
        rows, columns=["company_id", "broad_sector", "metric", "value", "z_score"]
    )


def write_outliers(outliers, path=OUTLIER_PATH):
    """Write output/outlier_report.csv."""
    path.parent.mkdir(parents=True, exist_ok=True)
    outliers.to_csv(path, index=False)
    return path


# ------------------------------------------------------------------
# Portfolio statistics (Day 37)
# ------------------------------------------------------------------


def portfolio_stats(frame, kpis=CORE_KPIS, percentiles=PERCENTILES):
    """P10..P90, mean and std for each KPI across all companies."""
    rows = []
    for metric in kpis:
        values = frame[metric].dropna()
        row = {"kpi": metric, "n": len(values)}
        for pct in percentiles:
            row[f"p{int(pct * 100)}"] = values.quantile(pct)
        row["mean"] = values.mean()
        row["std"] = values.std(ddof=1)
        rows.append(row)
    return pd.DataFrame(rows)


def write_stats(stats, path=STATS_PATH):
    """Write output/portfolio_stats.csv."""
    path.parent.mkdir(parents=True, exist_ok=True)
    stats.to_csv(path, index=False)
    return path


def main():
    print("=" * 60)
    print("CLUSTER PROFILE & STATISTICS  (Sprint 6, Day 37)")
    print("=" * 60)

    frame = load_kpi_frame()
    cluster_frame = impute_sector_median(load_clustering_frame())
    labels = pd.read_csv(CLUSTER_LABELS_PATH)

    profile = profile_clusters(cluster_frame, labels)
    write_profile(profile)
    print(f"\n  Cluster profile : {PROFILE_PATH}")

    heat = build_correlation_heatmap(frame)
    print(f"  Correlation plot: {heat}")

    outliers = detect_outliers(frame)
    write_outliers(outliers)
    print(f"  Outliers        : {OUTLIER_PATH}  ({len(outliers)} flags)")

    stats = portfolio_stats(frame)
    write_stats(stats)
    print(f"  Portfolio stats : {STATS_PATH}")

    print("\n  Outlier z-scores by metric:")
    if not outliers.empty:
        print(outliers["metric"].value_counts().to_string())
    print("\n  Portfolio stats (P50 / mean):")
    print(stats.set_index("kpi")[["p50", "mean"]].round(2).to_string())

    print("\n" + "=" * 60)
    print("DAY 37 COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
