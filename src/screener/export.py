"""
Screener Excel export (Sprint 3, Day 17).

Writes output/screener_output.xlsx - one sheet per preset, 20 KPI
columns, sorted by composite quality score descending, with cells
colour-coded: green when a cell meets its preset threshold, red when
it fails. Non-threshold cells are uncoloured.
"""

from pathlib import Path

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill

from src.screener.engine import KPI_COLUMNS, _resolve_filter

GREEN_FILL = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
RED_FILL = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
HEADER_FILL = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
HEADER_FONT = Font(bold=True, color="FFFFFF")

LEAD_COLUMNS = ["company_id", "company_name"]


def _display_columns(result, config):
    """Column set for a preset sheet: ids + 20 KPIs + filter extras +
    composite score."""

    used_columns = {LEAD_COLUMNS[0], LEAD_COLUMNS[1], "composite_quality_score"}
    filter_columns = []
    for filter_spec in result["filters"]:
        column = _resolve_filter(config, filter_spec)[0]
        filter_columns.append(column)

    extras = [
        column
        for column in filter_columns
        if column not in KPI_COLUMNS and column not in used_columns
    ]
    return LEAD_COLUMNS + KPI_COLUMNS + extras + ["composite_quality_score"]


def single_filter_pass(frame, config, filter_spec):
    """
    Pass/fail of every row for a single threshold (used for cell
    colour-coding). Returns a boolean Series aligned with frame.index.
    """

    column, operator, threshold, skip_financials, debt_free_passes = _resolve_filter(
        config, filter_spec
    )

    values = pd.Series(
        [frame.loc[idx, column] for idx in frame.index], index=frame.index
    )

    threshold_columns = {
        ">": values.apply(lambda v: _above(v, threshold)),
        "<": values.apply(lambda v: _below(v, threshold)),
        ">=": values.apply(lambda v: _above(v, threshold, equal=True)),
        "<=": values.apply(lambda v: _below(v, threshold, equal=True)),
        "==": values.apply(lambda v: _equal(v, threshold)),
        "=": values.apply(lambda v: _equal(v, threshold)),
        "!=": values.apply(lambda v: not _equal(v, threshold)),
    }
    passed = threshold_columns.get(operator, pd.Series(False, index=frame.index))

    if column == "debt_to_equity" and skip_financials and operator in ("<", "<="):
        financial = frame.get("broad_sector") == "Financials"
        passed = passed | financial.fillna(False).astype(bool)

    if debt_free_passes and column == "interest_coverage":
        debt_free = frame.get("icr_label") == "Debt Free"
        passed = passed | debt_free.fillna(False).astype(bool)

    return passed


def _above(value, threshold, equal=False):
    if value is None or pd.isna(value):
        return False
    try:
        return value >= threshold if equal else value > threshold
    except TypeError:
        return False


def _below(value, threshold, equal=False):
    if value is None or pd.isna(value):
        return False
    try:
        return value <= threshold if equal else value < threshold
    except TypeError:
        return False


def _equal(value, threshold):
    if value is None or pd.isna(value):
        return False
    try:
        return abs(float(value) - float(threshold)) < 1e-9
    except (TypeError, ValueError):
        return False


def _sheet_name(name):
    invalid = "\\/?*[]:"
    cleaned = "".join("_" if char in invalid else char for char in name)
    return cleaned[:31] or "Sheet"


def write_screener_workbook(
    results, all_frame, path=Path("output/screener_output.xlsx"), config=None
):
    """
    Write one sheet per preset plus all-company and summary sheets.

    Each preset sheet shows the full 92-company universe sorted by
    composite quality score with threshold cells colour-coded
    (green = passes the threshold, red = fails). The summary sheet
    records the number of companies that pass each preset.

    results: dict of preset_key -> run_preset() output.
    all_frame: the full feature frame (colour-coded rows).
    config: the loaded screener config (used for metric resolution).
    """

    from openpyxl import Workbook

    workbook = Workbook()
    workbook.remove(workbook.active)

    default_sheet = workbook.create_sheet("All Companies")
    _write_plain_sheet(default_sheet, all_frame)

    for key, result in results.items():
        sheet = workbook.create_sheet(_sheet_name(result["name"]))
        columns = _display_columns(result, config)
        _write_preset_sheet(sheet, result, columns, config, all_frame)

    summary = workbook.create_sheet("Summary")
    _write_summary_sheet(summary, results, config)

    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)
    return path


def _write_plain_sheet(sheet, frame):
    columns = LEAD_COLUMNS + KPI_COLUMNS + ["composite_quality_score"]
    ordered = frame.sort_values("composite_quality_score", ascending=False)
    _style_headers(sheet, columns)
    for row_offset, (_, row) in enumerate(ordered.iterrows(), start=2):
        for col_offset, column in enumerate(columns, start=1):
            _write_cell(sheet, row_offset, col_offset, row.get(column))


def _write_preset_sheet(sheet, result, columns, config, all_frame):
    """Write one preset sheet with green/red threshold colour-coding.

    Rows are the full universe sorted by composite score descending, so
    green cells (threshold met) and red cells (threshold failed) are
    both visible.
    """

    frame = all_frame.sort_values("composite_quality_score", ascending=False)

    _style_headers(sheet, columns)

    # Map display column -> pass/fail series for the preset's thresholds.
    pass_maps = {}
    for filter_spec in result["filters"]:
        column = _resolve_filter(config, filter_spec)[0]
        if column in columns:
            pass_maps[column] = single_filter_pass(frame, config, filter_spec)

    for row_offset, (idx, row) in enumerate(frame.iterrows(), start=2):
        for col_offset, column in enumerate(columns, start=1):
            cell = _write_cell(sheet, row_offset, col_offset, row.get(column))
            passed = pass_maps.get(column)
            if passed is not None and column not in LEAD_COLUMNS:
                _colour_cell(cell, passed.loc[idx])


def _write_summary_sheet(sheet, results, config):
    """One row per preset: company count and the applied thresholds."""

    _style_headers(sheet, ["Preset", "Companies (5-50? ok)", "Filters Applied"])

    for key, result in results.items():
        count = len(result["frame"])
        ok = "OK" if 5 <= count <= 50 else "OUT OF RANGE"
        filter_text = "; ".join(
            f"{spec['metric']} {spec['operator']} {spec['value']}"
            for spec in result["filters"]
        )
        sheet.cell(row=sheet.max_row + 1, column=1, value=result["name"])
        sheet.cell(row=sheet.max_row, column=2, value=count)
        sheet.cell(row=sheet.max_row, column=3, value=f"{ok}  ({filter_text})")


def _style_headers(sheet, columns):
    for col_offset, column in enumerate(columns, start=1):
        cell = sheet.cell(row=1, column=col_offset, value=column)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center")
    sheet.freeze_panes = "C2"


def _write_cell(sheet, row, column, value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        cell = sheet.cell(row=row, column=column, value=None)
    elif isinstance(value, bool):
        cell = sheet.cell(row=row, column=column, value=value)
    elif isinstance(value, (int, float)):
        cell = sheet.cell(row=row, column=column, value=round(float(value), 2))
    else:
        cell = sheet.cell(row=row, column=column, value=str(value))
    return cell


def _colour_cell(cell, passed):
    if pd.isna(passed):
        return
    cell.fill = GREEN_FILL if bool(passed) else RED_FILL
