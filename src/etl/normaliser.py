"""
Data normalization utilities for the Nifty100 Data Foundation project.
"""

import re

import pandas as pd

MONTHS = {
    "JAN": "01",
    "JANUARY": "01",
    "FEB": "02",
    "FEBRUARY": "02",
    "MAR": "03",
    "MARCH": "03",
    "APR": "04",
    "APRIL": "04",
    "MAY": "05",
    "JUN": "06",
    "JUNE": "06",
    "JUL": "07",
    "JULY": "07",
    "AUG": "08",
    "AUGUST": "08",
    "SEP": "09",
    "SEPTEMBER": "09",
    "OCT": "10",
    "OCTOBER": "10",
    "NOV": "11",
    "NOVEMBER": "11",
    "DEC": "12",
    "DECEMBER": "12",
}


def normalize_year(value):
    """Normalize financial year values into YYYY-MM format."""

    if value is None:
        return None

    if pd.isna(value):
        return None

    # Already normalized: YYYY-MM
    if isinstance(value, str):
        cleaned = value.strip().upper()

        if re.fullmatch(r"(19|20)\d{2}-(0[1-9]|1[0-2])", cleaned):
            return cleaned

    # Numeric year: assume March financial-year close
    if isinstance(value, (int, float)):
        if float(value).is_integer():
            year = int(value)

            if 1900 <= year <= 2100:
                return f"{year}-03"

            if 0 <= year <= 99:
                return f"{2000 + year}-03"

        return None

    value = str(value).strip().upper()
    value = re.sub(r"\s+", " ", value)

    if not value:
        return None

    # ---------------------------------------------------------
    # Month + year
    #
    # Mar-23  -> 2023-03
    # Mar 23  -> 2023-03
    # March-2023 -> 2023-03
    # Dec-22  -> 2022-12
    # Jun-23  -> 2023-06
    # ---------------------------------------------------------

    month_year = re.fullmatch(
        r"([A-Z]+)\s*[-/ ]\s*(\d{2}|\d{4})",
        value,
    )

    if month_year:
        month_text = month_year.group(1)
        year_text = month_year.group(2)

        month = MONTHS.get(month_text)

        if month is not None:
            year = int(year_text)

            if len(year_text) == 2:
                year += 2000

            if 1900 <= year <= 2100:
                return f"{year}-{month}"

            return None
        # month_text MONTHS dict mein nahi mila (e.g. "FY 24")
        # -> yahan se return na karo, aage FY-pattern check hone do

    # ---------------------------------------------------------
    # FY formats
    #
    # FY24 -> 2024-03
    # FY 24 -> 2024-03
    # FY2024 -> 2024-03
    # ---------------------------------------------------------

    fy_match = re.fullmatch(
        r"FY\s*(\d{2}|\d{4})",
        value,
    )

    if fy_match:
        year_text = fy_match.group(1)
        year = int(year_text)

        if len(year_text) == 2:
            year += 2000

        if 1900 <= year <= 2100:
            return f"{year}-03"

        return None

    # ---------------------------------------------------------
    # Financial year range
    #
    # 2023-24 -> 2024-03
    # FY2023-24 -> 2024-03
    # FY 2023-24 -> 2024-03
    # ---------------------------------------------------------

    financial_year = re.fullmatch(
        r"(?:FY\s*)?(\d{4})\s*-\s*(\d{2}|\d{4})",
        value,
    )

    if financial_year:
        start_year = int(financial_year.group(1))
        end_part = financial_year.group(2)

        if len(end_part) == 2:
            end_year = (start_year // 100) * 100 + int(end_part)

            if end_year < start_year:
                end_year += 100
        else:
            end_year = int(end_part)

        if 1900 <= end_year <= 2100:
            return f"{end_year}-03"

        return None

    # ---------------------------------------------------------
    # Standalone four-digit year
    #
    # 2023 -> 2023-03
    # ---------------------------------------------------------

    four_digit_year = re.fullmatch(
        r"(19|20)\d{2}",
        value,
    )

    if four_digit_year:
        return f"{int(value)}-03"

    # ---------------------------------------------------------
    # Standalone two-digit year
    #
    # 23 -> 2023-03
    # ---------------------------------------------------------

    two_digit_year = re.fullmatch(
        r"\d{2}",
        value,
    )

    if two_digit_year:
        return f"{2000 + int(value)}-03"

    return None


def normalize_ticker(value):
    """
    Normalize stock ticker symbols.

    Examples:
        "RELIANCE" -> "RELIANCE"
        "reliance" -> "RELIANCE"
        "RELIANCE.NS" -> "RELIANCE"
        " RELIANCE " -> "RELIANCE"
    """

    if value is None:
        return None

    if pd.isna(value):
        return None

    value = str(value).strip().upper()

    if value == "":
        return None

    suffixes = [
        ".NS",
        ".BO",
        "-EQ",
        "_EQ",
    ]

    for suffix in suffixes:
        value = value.removesuffix(suffix)

    value = value.replace(" ", "")

    value = re.sub(
        r"[^A-Z0-9&\-_]",
        "",
        value,
    )

    if value == "":
        return None

    return value
