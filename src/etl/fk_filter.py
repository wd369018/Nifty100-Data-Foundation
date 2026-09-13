"""
Foreign-key filtering utilities for the Nifty100 Data Foundation project.

This module separates valid child-table records from orphan records
whose company_id does not exist in the companies master.
"""

from pathlib import Path

import pandas as pd


def filter_company_foreign_keys(
    df,
    companies_df,
    table_name=None,
):
    """
    Separate valid rows from orphan rows using company_id.

    Parameters:
        df (pandas.DataFrame):
            Child-table DataFrame containing company_id.

        companies_df (pandas.DataFrame):
            Companies master DataFrame containing id.

        table_name (str | None):
            Optional table name used in the rejection audit.

    Returns:
        tuple[pandas.DataFrame, pandas.DataFrame]:
            valid_rows, rejected_rows

    Raises:
        ValueError:
            If required columns are missing.
    """

    if "company_id" not in df.columns:
        raise ValueError("Child dataframe must contain 'company_id' column.")

    if "id" not in companies_df.columns:
        raise ValueError("Companies master must contain 'id' column.")

    # Normalize master IDs for comparison only.
    valid_ids = set(companies_df["id"].dropna().astype(str).str.strip().str.upper())

    # Normalize child IDs for comparison only.
    child_ids = df["company_id"].astype(str).str.strip().str.upper()

    valid_mask = child_ids.isin(valid_ids)

    valid_rows = df.loc[valid_mask].copy()
    rejected_rows = df.loc[~valid_mask].copy()

    # Add audit information to rejected rows.
    if not rejected_rows.empty:
        rejected_rows.insert(
            0,
            "rejection_reason",
            "DQ-03: company_id not found in companies master",
        )

        if table_name is not None:
            rejected_rows.insert(
                0,
                "table_name",
                table_name,
            )

    return (
        valid_rows.reset_index(drop=True),
        rejected_rows.reset_index(drop=True),
    )


def save_rejection_audit(
    rejected_rows,
    output_file="output/fk_rejections.csv",
):
    """
    Save rejected foreign-key rows to a CSV audit file.

    Parameters:
        rejected_rows (pandas.DataFrame):
            Rows rejected because of invalid company_id.

        output_file (str | Path):
            Destination CSV path.

    Returns:
        None
    """

    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    if rejected_rows.empty:
        # Create an empty audit file with a standard schema.
        pd.DataFrame(
            columns=[
                "table_name",
                "rejection_reason",
                "company_id",
            ]
        ).to_csv(output_file, index=False)
        return

    rejected_rows.to_csv(
        output_file,
        index=False,
    )
