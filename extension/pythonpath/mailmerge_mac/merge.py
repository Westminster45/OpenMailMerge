"""Turning one data row into one email (addresses, subject, body, attachments)."""

import glob
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import template

# Characters not allowed in attachment file names.
UNSAFE_NAME_RE = re.compile(r'[\\/:*?"<>|\r\n]+')

# File types the attachment column and the fixed (every-email) attachments may attach. Anything else
# (code, keys, files with no extension) is blocked, so a data file or the settings saved in a document
# can't make the merge send arbitrary files.
ATTACHMENT_TYPES = {
    ".pdf", ".doc", ".docx", ".odt", ".rtf", ".pages", ".txt", ".html", ".htm",
    ".csv", ".json", ".zip",
    ".xls", ".xlsx", ".ods", ".numbers",
    ".ppt", ".pptx", ".odp", ".key",
    ".jpg", ".jpeg", ".png", ".gif", ".heic", ".tif", ".tiff", ".webp", ".bmp",
    ".mp3", ".m4a", ".wav", ".mp4", ".mov", ".m4v", ".avi",
}


@dataclass
class Settings:
    """Everything the user sets in the dialog. Saved with the document as JSON."""
    data_file: str = ""
    from_address: str = ""
    to_column: str = ""
    cc: str = ""
    bcc: str = ""
    reply_to: str = ""
    subject: str = ""
    importance: str = "Normal"
    static_attachments: list = field(default_factory=list)
    attachment_column: str = ""
    attach_pdf: bool = False
    pdf_name: str = "Letter.pdf"
    pdf_password: str = ""
    pdf_body: str = "Dear «First_Name»,\n\nPlease find your letter attached.\n"
    exclusion_file: str = ""
    record_from: int = 0  # 0 = all records
    record_to: int = 0
    require_offline: bool = True

    @classmethod
    def from_dict(cls, d):
        known = {k: v for k, v in (d or {}).items() if k in cls.__dataclass_fields__}
        return cls(**known)


@dataclass
class Email:
    """One rendered email, plus everything wrong with it."""
    record_number: int
    row: dict
    to: str = ""
    cc: str = ""
    bcc: str = ""
    reply_to: str = ""
    subject: str = ""
    importance: str = "Normal"
    html: str = ""
    text: str = ""
    attachments: list = field(default_factory=list)  # existing files
    missing_attachments: list = field(default_factory=list)
    blocked_attachments: list = field(default_factory=list)  # files of a type not in ATTACHMENT_TYPES
    pdf_name: str = ""
    pdf_password: str = ""
    missing_fields: list = field(default_factory=list)
    empty_fields: list = field(default_factory=list)
    leftovers: list = field(default_factory=list)  # where markers were left unrendered


def safe_filename(name, fallback="Letter.pdf"):
    name = UNSAFE_NAME_RE.sub("-", name).strip(" .-")
    return name or fallback


def attachment_paths(value):
    """Split a cell like 'a.pdf; b.pdf' and expand wildcards. Returns (found, missing, blocked):
    blocked = existing files whose type isn't in ATTACHMENT_TYPES."""
    found, missing = [], []
    for part in re.split(r"[;\n]", value or ""):
        part = part.strip().strip('"')
        if not part:
            continue
        part = str(Path(part).expanduser())
        if any(ch in part for ch in "*?["):
            matches = sorted(glob.glob(part))
            (found.extend(matches) if matches else missing.append(part))
        elif Path(part).is_file():
            found.append(part)
        else:
            missing.append(part)
    from .settings_check import is_key_file  # also blocked: the key for saved settings, even via a link
    blocked = [p for p in found if Path(p).suffix.lower() not in ATTACHMENT_TYPES or is_key_file(p)]
    return [p for p in found if p not in blocked], missing, blocked


def render_email(settings, row, record_number, body_html, body_text, now=None):
    """Render one row. body_html/body_text are the document's template (fields unrendered)."""
    e = Email(record_number=record_number, row=row)

    def r(text, escape=False, where=""):
        out, missing, empty = template.render(text, row, escape=escape, record_number=record_number, now=now)
        e.missing_fields += [m for m in missing if m not in e.missing_fields]
        e.empty_fields += [x for x in empty if x not in e.empty_fields]
        if template.has_leftover_markers(out) and where:
            e.leftovers.append(where)
        return out

    e.to = row.get(settings.to_column, "").strip() if settings.to_column else ""
    e.cc = r(settings.cc, where="Cc")
    e.bcc = r(settings.bcc, where="Bcc")
    e.reply_to = r(settings.reply_to, where="Reply-To")
    e.subject = r(settings.subject, where="Subject").strip()
    e.importance = settings.importance

    if settings.attach_pdf:
        e.text = r(settings.pdf_body, where="Email body")
        from .message import text_to_html
        e.html = text_to_html(e.text)
        e.pdf_name = safe_filename(r(settings.pdf_name, where="PDF file name"))
        if not e.pdf_name.lower().endswith(".pdf"):
            e.pdf_name += ".pdf"
        e.pdf_password = r(settings.pdf_password, where="PDF password")
        # The document itself becomes the PDF; its fields are checked too.
        r(body_text, where="Document")
    else:
        e.html = r(body_html, escape=True, where="Document")
        e.text = r(body_text)

    for path in settings.static_attachments:
        if not Path(path).is_file():
            e.missing_attachments.append(path)
        elif Path(path).suffix.lower() not in ATTACHMENT_TYPES:  # same type rule as the attachment column
            e.blocked_attachments.append(path)
        else:
            e.attachments.append(path)
    if settings.attachment_column:
        found, missing, blocked = attachment_paths(row.get(settings.attachment_column, ""))
        e.attachments += found
        e.missing_attachments += missing
        e.blocked_attachments += blocked
    return e


def selected_records(settings, total):
    """1-based record numbers to process, from the range in settings."""
    start = settings.record_from if settings.record_from > 0 else 1
    end = settings.record_to if settings.record_to > 0 else total
    return list(range(max(1, start), min(total, end) + 1))


def read_exclusions(path):
    """Addresses (lower case) from a text/CSV file: any token that looks like an address."""
    if not path or not Path(path).is_file():
        return set()
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return {a.lower() for a in re.findall(r"[^\s,;<>\"']+@[^\s,;<>\"']+", text)}

