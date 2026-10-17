"""Reading recipient data. CSV is read here; spreadsheets (.xlsx, .ods, .xls) via office.read_spreadsheet."""

import csv
import io
from pathlib import Path

SPREADSHEET_SUFFIXES = {".xlsx", ".xls", ".ods", ".fods", ".numbers"}


class Table:
    """Headers plus rows (each row a dict of header -> text)."""

    def __init__(self, headers, rows, source=""):
        self.headers = headers
        self.rows = rows
        self.source = source

    def __len__(self):
        return len(self.rows)


def from_matrix(matrix, source=""):
    """Build a Table from a list of lists; the first non-empty row is the header row."""
    matrix = [[("" if c is None else str(c)).strip() for c in r] for r in matrix]
    while matrix and not any(matrix[0]):
        matrix.pop(0)
    if not matrix:
        return Table([], [], source)
    headers = []
    for i, h in enumerate(matrix[0]):
        h = h or f"Column{i + 1}"
        while h in headers:
            h += "_"
        headers.append(h)
    rows = []
    for r in matrix[1:]:
        if not any(r):
            continue  # skip blank lines
        r = r + [""] * (len(headers) - len(r))
        rows.append(dict(zip(headers, r[: len(headers)])))
    return Table(headers, rows, source)


def read_csv(path):
    raw = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    return from_matrix(list(csv.reader(io.StringIO(text), dialect)), str(path))


def is_spreadsheet(path):
    return Path(path).suffix.lower() in SPREADSHEET_SUFFIXES
