"""Quick data inspection script."""

from pathlib import Path

import pandas as pd


def main():
    raw_dir = Path("data/raw")
    supp_dir = Path("data/supporting")

    # Load companies master
    companies_file = raw_dir / "1788501606103-7177b6c2-companies.xlsx"
    comp = pd.read_excel(companies_file, header=1)
    comp = comp.dropna(how="all").reset_index(drop=True)
    comp_ids = set(comp["id"].dropna().astype(str).str.strip().str.upper())
    print(f"Companies master: {len(comp)} rows")
    print(f"Company IDs: {sorted(comp_ids)[:10]}...")
    print()

    # Check each raw file for orphans
    for f in sorted(raw_dir.glob("*.xlsx")):
        name = f.stem.split("-")[-1]
        if name == "companies":
            continue
        try:
            df = pd.read_excel(f, header=1)
            df = df.dropna(how="all").reset_index(drop=True)
            if "company_id" in df.columns:
                child_ids = set(
                    df["company_id"].dropna().astype(str).str.strip().str.upper()
                )
                orphans = child_ids - comp_ids
                print(
                    f"{name}: {len(df)} rows, {len(child_ids)} unique companies, {len(orphans)} orphans"
                )
                if orphans:
                    print(f"  Orphans: {sorted(orphans)}")
            else:
                print(f"{name}: {len(df)} rows, no company_id column")
        except Exception as e:
            print(f"{name}: ERROR - {e}")

    print()

    # Check supporting files
    for f in sorted(supp_dir.glob("*.xlsx")):
        name = f.stem.split("-")[-1]
        try:
            df = pd.read_excel(f, header=0)
            df = df.dropna(how="all").reset_index(drop=True)
            if "company_id" in df.columns:
                child_ids = set(
                    df["company_id"].dropna().astype(str).str.strip().str.upper()
                )
                orphans = child_ids - comp_ids
                print(
                    f"{name}: {len(df)} rows, {len(child_ids)} unique companies, {len(orphans)} orphans"
                )
                if orphans:
                    print(f"  Orphans: {sorted(orphans)}")
            else:
                print(f"{name}: {len(df)} rows, no company_id column")
        except Exception as e:
            print(f"{name}: ERROR - {e}")

    print()

    # Check balancesheet duplicates
    bs_file = raw_dir / "1788501604829-ac8c0874-balancesheet.xlsx"
    bs = pd.read_excel(bs_file, header=1)
    bs = bs.dropna(how="all").reset_index(drop=True)
    dups = bs[bs.duplicated(subset=["company_id", "year"], keep=False)]
    print(f"Balance sheet: {len(bs)} rows, {len(dups)} duplicate rows")
    if not dups.empty:
        dup_companies = dups["company_id"].unique()
        print(f"  Companies with dups: {sorted(dup_companies)}")
        for c in sorted(dup_companies)[:5]:
            sub = bs[bs["company_id"] == c][["company_id", "year"]]
            print(f"  {c}: {len(sub)} rows, years: {list(sub['year'].head(5))}")

    print()

    # Check cashflow year format
    cf_file = raw_dir / "1788501605758-8e951681-cashflow.xlsx"
    cf = pd.read_excel(cf_file, header=1)
    cf = cf.dropna(how="all").reset_index(drop=True)
    print(f"Cashflow years (sample): {list(cf['year'].head(10))}")

    # Check profitandloss year format
    pl_file = raw_dir / "1788501607124-aad40f4f-profitandloss.xlsx"
    pl = pd.read_excel(pl_file, header=1)
    pl = pl.dropna(how="all").reset_index(drop=True)
    print(f"P&L years (sample): {list(pl['year'].head(10))}")


if __name__ == "__main__":
    main()
