"""Helpers that keep user-entered spreadsheet text from becoming formulas."""

_RISKY_PREFIXES = ('=', '+', '-', '@', '\t', '\r')


def is_formula_like(value):
    return isinstance(value, str) and value[:1] in _RISKY_PREFIXES


def neutralize(cell):
    """Force a string cell for formula-like text; no-op otherwise."""
    if is_formula_like(cell.value):
        cell.data_type = 's'
    return cell


def set_cell(ws, row, column, value):
    cell = ws.cell(row=row, column=column, value=value)
    return neutralize(cell)


def append_row(ws, values):
    row_values = list(values)
    ws.append(row_values)
    row = ws.max_row
    for index, value in enumerate(row_values, start=1):
        if is_formula_like(value):
            ws.cell(row=row, column=index).data_type = 's'