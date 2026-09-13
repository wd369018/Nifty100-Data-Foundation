"""
KMeans Clustering — Sprint 6, Day 36.

Clusters 92 Nifty-100 companies into 5 archetypes based on 5 financial
features, with sector-median imputation and StandardScaler normalisation.

Outputs:
    - reports/elbow_plot.png
    - output/cluster_labels.csv
"""

import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

DB_PATH = Path("db/nifty100.db")
OUTPUT_CSV = Path("output/cluster_labels.csv")
ELBOW_PNG = Path("reports/elbow_plot.png")

CLUSTER_FEATURES = [
    "return_on_equity_pct",
    "debt_to_equity",
    "revenue_cagr_5yr",
    "fcf_cagr_5yr",
    "operating_profit_margin_pct",
]

CLUSTER_NAMES_DEFAULT = {
    0: "High-Quality Compounders",
    1: "High-Margin Franchises",
    2: "Defense High-ROE Leaders",
    3: "Leveraged Financials",
    4: "Cash-Flow Outliers",
}


def _num(v):
    if v is None or pd.isna(v):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load_clustering_frame(db_path=DB_PATH):
    """Build a 92-row DataFrame with 5 clustering features + sector."""
    from src.screener.engine import load_feature_frame

    frame = load_feature_frame(db_path=db_path)
    sectors = pd.read_sql(
        "SELECT company_id, broad_sector FROM sectors",
        sqlite3.connect(db_path),
    )
    result = frame[["company_id"]].copy()
    result = result.merge(sectors, on="company_id", how="left")
    for col in CLUSTER_FEATURES:
        if col in frame.columns:
            result[col] = frame[col].apply(_num)
        else:
            result[col] = np.nan
    return result


def impute_sector_median(df):
    """Replace NaN values with per-sector median; fallback to global median."""
    result = df.copy()
    for col in CLUSTER_FEATURES:
        missing = result[col].isna()
        for sector, group in result[missing].groupby("broad_sector"):
            med = result.loc[result["broad_sector"] == sector, col].median()
            if pd.isna(med):
                med = result[col].median()
            result.loc[result["broad_sector"] == sector, col] = result.loc[
                result["broad_sector"] == sector, col
            ].fillna(med)
        if result[col].isna().any():
            global_med = result[col].median()
            result.loc[result[col].isna(), col] = global_med
    return result


def compute_clusters(df, n_clusters=5, random_state=42):
    """Run KMeans and return df with cluster_id + distance_from_centroid."""
    features = df[CLUSTER_FEATURES].values
    scaler = StandardScaler()
    X = scaler.fit_transform(features)

    km = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    labels = km.fit_predict(X)
    dists = km.transform(X).min(axis=1)

    result = df.copy()
    result["cluster_id"] = labels
    result["distance_from_centroid"] = dists.round(4)
    return result, km


def generate_elbow_plot(
    k_range=range(2, 11), random_state=42, df=None, output=ELBOW_PNG
):
    """Save inertia-vs-k elbow curve confirming k=5 is near the elbow."""
    features = df[CLUSTER_FEATURES].values
    X = StandardScaler().fit_transform(features)
    inertias = []
    for k in k_range:
        km = KMeans(n_clusters=k, random_state=random_state, n_init=10)
        km.fit(X)
        inertias.append(km.inertia_)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(list(k_range), inertias, "o-", linewidth=2, markersize=6)
    ax.axvline(x=5, color="red", linestyle="--", alpha=0.7, label="k = 5")
    ax.set_xlabel("Number of clusters (k)")
    ax.set_ylabel("Inertia (within-cluster sum of squares)")
    ax.set_title("KMeans Elbow Plot — Nifty 100 Clustering")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return output


def assign_cluster_names(df, names=None):
    """Add human-readable cluster_name column. Names updated in Day 37."""
    if names is None:
        names = CLUSTER_NAMES_DEFAULT
    result = df.copy()
    result["cluster_name"] = result["cluster_id"].map(names)
    return result


def write_outputs(df, csv_path=OUTPUT_CSV):
    """Write cluster_labels.csv with company_id, cluster_id, cluster_name, distance_from_centroid."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    out = df[["company_id", "cluster_id", "cluster_name", "distance_from_centroid"]]
    out.to_csv(csv_path, index=False)
    return csv_path


def main():
    print("=" * 60)
    print("KMEANS CLUSTERING  (Sprint 6, Day 36)")
    print("=" * 60)

    df = load_clustering_frame()
    df = impute_sector_median(df)
    df, _ = compute_clusters(df)
    df = assign_cluster_names(df)

    print(f"\n  Companies : {len(df)}")
    print(f"  Features  : {CLUSTER_FEATURES}")
    print(f"  Clusters  : {df['cluster_id'].nunique()}")
    for cid in sorted(df["cluster_id"].unique()):
        print(f"    Cluster {cid}: {(df['cluster_id']==cid).sum()} companies")

    generate_elbow_plot(df=df)
    print(f"\n  Elbow plot: {ELBOW_PNG}")

    csv = write_outputs(df)
    print(f"  Labels    : {csv}")

    print("\n" + "=" * 60)
    print("CLUSTERING COMPLETE")
    print("=" * 60)
    return df


if __name__ == "__main__":
    main()
