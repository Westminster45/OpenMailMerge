"""Merge fields: «Field» or {{Field}} placeholders in text and HTML."""

import html
import re
from datetime import datetime

# «Name» (also as HTML entities, as Writer's HTML export may write them) or {{Name}}.
FIELD_RE = re.compile(
    r"(?:«|&laquo;|&#171;|&#xab;)\s*([^«»<>&]+?)\s*(?:»|&raquo;|&#187;|&#xbb;)"
    r"|\{\{\s*([^{}<>]+?)\s*\}\}",
    re.IGNORECASE,
)
# Any marker left after rendering means a field was split by formatting or mistyped.
LEFTOVER_RE = re.compile(r"«|»|&laquo;|&raquo;|&#171;|&#187;|&#xab;|&#xbb;|\{\{|\}\}", re.IGNORECASE)
# A <meta ...> tag (quoted values may contain '>'), with the line break and indent before it.
META_TAG_RE = re.compile(r"""(?:\r?\n[ \t]*)?<meta\b((?:"[^"]*"|'[^']*'|[^"'>])*)>""", re.IGNORECASE)
ATTR_RE = re.compile(r"""([^\s"'<>/=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'<>=`]+)))?""")

BUILTINS = ("DATE", "TIME", "RECORD_NUMBER")


def marker(name):
    return f"«{name}»"


def fields_in(text):
    """Field names used in text, in order of first use."""
    seen = []
    for m in FIELD_RE.finditer(text or ""):
        name = (m.group(1) or m.group(2)).strip()
        if name not in seen:
            seen.append(name)
    return seen


def lookup(name, row, record_number=None, now=None):
    """Value for a field: exact column, then case-insensitive column, then built-ins.

    Returns (value, found).
    """
    if name in row:
        return row[name], True
    lower = {k.lower(): k for k in row}
    if name.lower() in lower:
        return row[lower[name.lower()]], True
    key = name.upper()
    now = now or datetime.now()
    if key == "DATE":
        return now.strftime("%d/%m/%Y"), True
    if key == "TIME":
        return now.strftime("%H:%M"), True
    if key == "RECORD_NUMBER" and record_number is not None:
        return str(record_number), True
    return "", False


def render(text, row, escape=False, record_number=None, now=None):
    """Replace fields in text with row values.

    Returns (result, missing, empty): missing = fields with no such column,
    empty = fields whose value is blank for this row.
    """
    missing, empty = [], []

    def sub(m):
        name = (m.group(1) or m.group(2)).strip()
        value, found = lookup(name, row, record_number, now)
        if not found:
            missing.append(name)
            return m.group(0)
        if not str(value).strip():
            empty.append(name)
        value = str(value)
        if escape:
            value = html.escape(value).replace("\n", "<br>")
        return value

    return FIELD_RE.sub(sub, text or ""), missing, empty


def has_leftover_markers(text):
    return bool(LEFTOVER_RE.search(text or ""))


def drop_meta(text, names):
    """Remove <meta name="..."> tags whose name is in names, leaving everything else as it was."""
    names = set(names)

    def sub(m):
        for a in ATTR_RE.finditer(m.group(1)):
            if a.group(1).lower() == "name":
                value = next((v for v in a.group(2, 3, 4) if v is not None), "")
                return "" if html.unescape(value) in names else m.group(0)
        return m.group(0)

    return META_TAG_RE.sub(sub, text or "")
