"""Pre-flight check: everything that could go wrong, found before any email is created.

Errors block creating emails. Warnings must be acknowledged by the user.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from . import merge, message, settings_check

ATTACHMENT_WARN_BYTES = 20 * 1024 * 1024
MAX_ROWS_LISTED = 8
# Only these may sit between merge fields in Cc, Bcc or Reply-To without counting as a typed address.
# Anything else (NBSP, zero-width characters...) counts as typed text.
FIELD_SEPARATORS = frozenset(" \t\r\n,;")
TYPED_ADDRESS_WARNINGS = {
    "Cc": "Every email will also go to {} (Cc). If you didn't add this, remove it on page 2.",
    "Bcc": "Every email will also be copied to {} (Bcc). If you didn't add this, remove it on page 2.",
    "Reply-To": "Replies will go to {} instead of you. If that's not what you want, clear the Reply-To box on page 2.",
}


@dataclass
class Report:
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    emails: list = field(default_factory=list)  # rendered emails to create, in order
    excluded: list = field(default_factory=list)  # record numbers skipped by the exclusion list

    @property
    def ok(self):
        return not self.errors

    def text(self):
        lines = [f"{len(self.emails)} email(s) ready to create."]
        if self.excluded:
            lines.append(f"{len(self.excluded)} record(s) skipped by the exclusion list: {rows(self.excluded)}.")
        lines.append("")
        if self.errors:
            lines.append(f"ERRORS ({len(self.errors)}) - fix these first:")
            lines += [f"  • {e}" for e in self.errors]
            lines.append("")
        if self.warnings:
            lines.append(f"WARNINGS ({len(self.warnings)}) - check these:")
            lines += [f"  • {w}" for w in self.warnings]
            lines.append("")
        if not self.errors and not self.warnings:
            lines.append("No problems found.")
        return "\n".join(lines)


def rows(numbers):
    numbers = list(numbers)
    shown = ", ".join(str(n) for n in numbers[:MAX_ROWS_LISTED])
    return shown + (f" and {len(numbers) - MAX_ROWS_LISTED} more" if len(numbers) > MAX_ROWS_LISTED else "")


def has_typed_address(value):
    """True if an address box holds anything besides merge fields and plain separators, i.e. text that
    goes into every email as typed (e.g. 'x+«RECORD_NUMBER»@example.com' or '«Manager», x@example.com')."""
    rest = merge.template.FIELD_RE.sub("", value or "")
    return any(ch not in FIELD_SEPARATORS for ch in rest)


def check(settings, table, body_html, body_text, exclusions=frozenset(), now=None):
    rep = Report()
    if not settings.from_address:
        rep.errors.append("No sending account chosen (From).")
    if not table.headers:
        rep.errors.append("No recipient data loaded.")
        return rep
    if not settings.to_column:
        rep.errors.append("No column chosen for the To address.")
    elif settings.to_column not in table.headers:
        rep.errors.append(f"The To column '{settings.to_column}' isn't in the data.")
    if not settings.subject.strip():
        rep.warnings.append("The subject is empty.")
    if settings.attachment_column and settings.attachment_column not in table.headers:
        rep.errors.append(f"The attachment column '{settings.attachment_column}' isn't in the data.")

    records = merge.selected_records(settings, len(table))
    if not records:
        rep.errors.append("The record range selects no records.")

    problems = defaultdict(list)  # message -> record numbers
    to_seen = defaultdict(list)
    total_size = 0
    for n in records:
        row = table.rows[n - 1]
        e = merge.render_email(settings, row, n, body_html, body_text, now=now)
        to_pairs = message.split_addresses(e.to)
        if to_pairs and all(a.lower() in exclusions for _, a in to_pairs):
            rep.excluded.append(n)
            continue
        rep.emails.append(e)

        if not to_pairs:
            problems[("error", "No To address")].append(n)
        for label, value in (("To", e.to), ("Cc", e.cc), ("Bcc", e.bcc), ("Reply-To", e.reply_to)):
            for _, addr in message.split_addresses(value):
                if not message.valid_address(addr):
                    problems[("error", f"Invalid {label} address")].append(f"{n} ({addr})")
        for _, addr in to_pairs:
            to_seen[addr.lower()].append(n)
        if not e.subject and settings.subject.strip():  # an empty subject is already warned about above
            problems[("warning", "Subject is empty after merging")].append(n)
        for name in e.missing_fields:
            problems[("warning", f"Field «{name}» doesn't match any column")].append(n)
        for where in e.leftovers:
            problems[("warning", f"{where} still contains « » or {{{{ }}}} after merging (a field may be split by formatting or mistyped)")].append(n)
        for name in e.empty_fields:
            problems[("warning", f"Field «{name}» is empty")].append(n)
        for path in e.missing_attachments:
            problems[("warning", f"Attachment not found (the email goes without it): {path}")].append(n)
        for path in e.blocked_attachments:
            problems[("error", f"Attachment type not allowed (only documents, text, HTML, CSV, JSON, "
                               f"zip, spreadsheets, presentations, images, audio and video): {path}")].append(n)
        if settings.attach_pdf and not e.pdf_password and settings.pdf_password.strip():
            problems[("warning", "PDF password is empty after merging (that PDF has no password)")].append(n)
        size = sum(Path(p).stat().st_size for p in e.attachments)
        total_size = max(total_size, size)
        if size > ATTACHMENT_WARN_BYTES:
            problems[("warning", "Attachments over 20 MB (may be rejected by mail servers)")].append(n)

    for (level, msg), nums in problems.items():
        text = f"{msg}: record {rows(nums)}" if nums else msg
        (rep.errors if level == "error" else rep.warnings).append(text)

    dups = {a: ns for a, ns in to_seen.items() if len(ns) > 1}
    for addr, ns in list(dups.items())[:MAX_ROWS_LISTED]:
        rep.warnings.append(f"{addr} is a To address in {len(ns)} records ({rows(ns)}) and will get {len(ns)} emails.")
    if len(dups) > MAX_ROWS_LISTED:
        rep.warnings.append(f"...and {len(dups) - MAX_ROWS_LISTED} more duplicate To addresses.")

    typed = {label: value for label, value in (("Cc", settings.cc), ("Bcc", settings.bcc), ("Reply-To", settings.reply_to))
             if has_typed_address(value)}
    for label, value in typed.items():
        rep.warnings.append(TYPED_ADDRESS_WARNINGS[label].format(settings_check.one_line(value)))
    for label, value in (("Cc", settings.cc), ("Bcc", settings.bcc)):
        if label not in typed and value.strip() and not merge.template.fields_in(value) and len(rep.emails) > 1:
            rep.warnings.append(
                f"{label} has a fixed address, so it gets a copy of every email ({len(rep.emails)} copies).")
    return rep
