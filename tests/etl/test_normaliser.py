import pytest

from src.etl.normaliser import (
    normalize_ticker,
    normalize_year,
)


@pytest.mark.parametrize(
    "input_value, expected",
    [
        # Standard year
        (2024, "2024-03"),
        (2023, "2023-03"),
        (2000, "2000-03"),
        # Float year
        (2024.0, "2024-03"),
        (2023.0, "2023-03"),
        # String year
        ("2024", "2024-03"),
        (" 2024 ", "2024-03"),
        # FY
        ("FY24", "2024-03"),
        ("FY 24", "2024-03"),
        ("FY2024", "2024-03"),
        # Financial year range
        ("2023-24", "2024-03"),
        ("FY2023-24", "2024-03"),
        ("FY 2023-24", "2024-03"),
        # Month-year
        ("Mar-23", "2023-03"),
        ("Mar 23", "2023-03"),
        ("March-2023", "2023-03"),
        ("Dec-22", "2022-12"),
        ("Jun-23", "2023-06"),
        # Already normalized
        ("2023-03", "2023-03"),
        ("2024-12", "2024-12"),
        # Two-digit year
        ("24", "2024-03"),
        (24, "2024-03"),
        # Invalid
        (None, None),
        ("", None),
        ("   ", None),
        ("Invalid", None),
        ("garbage", None),
        (1800, None),
        (2200, None),
    ],
)
def test_normalize_year(input_value, expected):
    assert normalize_year(input_value) == expected


@pytest.mark.parametrize(
    "input_value, expected",
    [
        ("RELIANCE", "RELIANCE"),
        ("reliance", "RELIANCE"),
        (" RELIANCE ", "RELIANCE"),
        ("RELIANCE.NS", "RELIANCE"),
        ("RELIANCE.BO", "RELIANCE"),
        ("RELIANCE-EQ", "RELIANCE"),
        ("RELIANCE_EQ", "RELIANCE"),
        ("RELI ANCE", "RELIANCE"),
        ("ABC123", "ABC123"),
        ("M&M", "M&M"),
        ("ABC-XYZ", "ABC-XYZ"),
        ("REL@IANCE", "RELIANCE"),
        (None, None),
        ("", None),
        ("   ", None),
    ],
)
def test_normalize_ticker(input_value, expected):
    assert normalize_ticker(input_value) == expected
