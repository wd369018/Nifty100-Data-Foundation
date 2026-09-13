"""20 unit tests for normalize_year() — all format variants + edge cases.

Sprint 6, Day 41 deliverable (tests/etl/test_normalise.py).
"""

from src.etl.normaliser import normalize_year


# Minimal, precise assertions on every format family.
def test_none_returns_none():
    assert normalize_year(None) is None


def test_pd_na_returns_none():
    import pandas as pd

    assert normalize_year(pd.NA) is None


def test_float_nan_returns_none():
    import pandas as pd

    assert normalize_year(float("nan")) is None or pd.isna(normalize_year(float("nan")))


def test_empty_string_returns_none():
    assert normalize_year("") is None


def test_whitespace_string_returns_none():
    assert normalize_year("   ") is None


def test_integer_year_returns_march_close():
    assert normalize_year(2024) == "2024-03"


def test_float_year_returns_march_close():
    assert normalize_year(2023.0) == "2023-03"


def test_two_digit_integer_year_returns_2000s_march():
    assert normalize_year(24) == "2024-03"


def test_string_four_digit_year():
    assert normalize_year("2022") == "2022-03"


def test_string_two_digit_year():
    assert normalize_year("19") == "2019-03"


def test_already_normalized_kept():
    assert normalize_year("2024-06") == "2024-06"


def test_already_normalized_lowercase_uppercased():
    assert normalize_year(" 2023-03 ") == "2023-03"


def test_month_abbrev_dash():
    assert normalize_year("Mar-23") == "2023-03"


def test_month_abbrev_space():
    assert normalize_year("Dec 22") == "2022-12"


def test_month_full_year():
    assert normalize_year("September-2023") == "2023-09"


def test_fy_two_digit():
    assert normalize_year("FY24") == "2024-03"


def test_fy_four_digit_spaced():
    assert normalize_year("FY 2024") == "2024-03"


def test_fy_range():
    assert normalize_year("FY2023-24") == "2024-03"


def test_fy_range_plain():
    assert normalize_year("2023-24") == "2024-03"


def test_year_out_of_range_numeric_returns_none():
    assert normalize_year(1800) is None
    assert normalize_year(2200) is None


def test_garbage_string_returns_none():
    assert normalize_year("not-a-year") is None
    assert normalize_year("Random Text") is None
