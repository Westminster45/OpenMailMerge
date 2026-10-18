"""Running a merge: writes one .eml per email and, in Drafts mode, hands each to Apple Mail.

Every email gets a line in log.csv in the campaign folder as it goes, so a stopped
or failed run shows exactly which emails were created.
"""

import csv
import re
from datetime import datetime
from pathlib import Path

from . import mailapp, message

OUTPUT_ROOT = Path.home() / "Documents" / "OpenMailMerge"
LOG_FIELDS = ["time", "record", "to", "cc", "bcc", "subject", "attachments", "status", "detail", "eml"]


def campaign_folder(title, prefix=""):
    stamp = datetime.now().strftime("%Y-%m-%d %H%M%S")
    name = re.sub(r'[\\/:*?"<>|]+', "-", title or "Mail merge").strip() or "Mail merge"
    folder = OUTPUT_ROOT / f"{prefix}{name} {stamp}"
    (folder / "emails").mkdir(parents=True)
    return folder


class Campaign:
    def __init__(self, folder, sender, mode, require_offline=True, pdf_maker=None, body_text=""):
        """mode: 'drafts' (Apple Mail Drafts), 'outbox' (sent into Mail's offline Outbox) or 'export'
        (.eml files only). sender: (name, address)."""
        self.folder = Path(folder)
        self.sender = sender
        self.mode = mode
        self.require_offline = require_offline
        self.pdf_maker = pdf_maker
        self.body_text = body_text
        self.message_ids = {}  # id(email) -> Message-ID of what was handed to Mail
        self.log_path = self.folder / "log.csv"
        with self.log_path.open("w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, LOG_FIELDS).writeheader()

    def log(self, e, status, detail="", eml=""):
        with self.log_path.open("a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, LOG_FIELDS).writerow({
                "time": datetime.now().isoformat(timespec="seconds"), "record": e.record_number,
                "to": e.to, "cc": e.cc, "bcc": e.bcc, "subject": e.subject,
                "attachments": "; ".join(Path(a).name for a in e.attachments),
                "status": status, "detail": detail, "eml": eml})

    def write_eml(self, e, index, unsent=True):
        attachments = list(e.attachments)
        if self.pdf_maker:
            pdf_dir = self.folder / "pdf" / f"{index:04d}"
            pdf_dir.mkdir(parents=True, exist_ok=True)
            attachments.insert(0, str(self.pdf_maker.make(e, self.body_text, pdf_dir / e.pdf_name)))
        msg = message.build(self.sender, e.to, e.subject, e.html, e.text, cc=e.cc, bcc=e.bcc,
                            reply_to=e.reply_to, attachments=attachments, importance=e.importance,
                            unsent=unsent)
        path = self.folder / "emails" / f"{index:04d} record {e.record_number}.eml"
        path.write_bytes(bytes(msg))
        return path

    def run(self, emails, progress=lambda i, n, e: None, should_stop=lambda: False):
        """Create every email. Drafts / Send: all emails are written first, imported into Mail in one
        go, then handed over one by one. Stops at the first Apple Mail problem.
        Returns (done, failed, stopped)."""
        done, failed, built = [], [], []
        for i, e in enumerate(emails, 1):
            if should_stop():
                return done, failed, True
            progress(i, len(emails), e)
            try:
                eml = self.write_eml(e, i, unsent=self.mode == "export")
            except Exception as err:  # e.g. unreadable attachment: skip this email, keep going
                self.log(e, "failed", f"Couldn't build the email: {err}")
                failed.append((e, f"Couldn't build the email: {err}"))
                continue
            if self.mode == "export":
                self.log(e, "exported", eml=eml.name)
                done.append(e)
                continue
            built.append((e, eml))
        if not built:
            return done, failed, False

        try:
            source = mailapp.import_batch([eml for _, eml in built], self.folder, self.folder.name,
                                          strip_bcc=self.mode == "outbox")
        except Exception as err:
            why = mailapp.explain(err) if isinstance(err, mailapp.MailError) else f"{type(err).__name__}: {err}"
            why = f"Couldn't import the emails into Mail: {why}"
            for e, eml in built:
                self.log(e, "failed", why, eml=eml.name)
                failed.append((e, why))
            return done, failed, True

        for i, (e, eml) in enumerate(built, 1):
            if should_stop():
                return done, failed, True
            progress(i, len(built), e)
            try:
                mailapp.create_message(eml, e.subject, source, "outbox" if self.mode == "outbox" else "draft",
                                       self.require_offline)
            except Exception as err:  # any Apple Mail problem stops the whole run
                why = mailapp.explain(err) if isinstance(err, mailapp.MailError) else f"{type(err).__name__}: {err}"
                self.log(e, "failed", why, eml=eml.name)
                failed.append((e, why))
                return done, failed, True
            self.message_ids[id(e)] = mailapp.read_eml(eml)["message_id"]
            status = ("in Outbox" if self.require_offline else "sent") if self.mode == "outbox" else "draft created"
            self.log(e, status, eml=eml.name)
            done.append(e)
        return done, failed, False

    def verify_senders(self, emails):
        """Check the drafts Mail saved use the chosen From address. Returns a list of problems.
        Emails are found by Message-ID, so other drafts with the same (or an empty) subject don't count."""
        if self.mode == "outbox":
            mailbox = "outbox" if self.require_offline else "sent mailbox"
        else:
            mailbox = "drafts mailbox"
        problems = []
        for e in emails:
            message_id = self.message_ids.get(id(e))
            if not message_id:
                continue
            for sender in mailapp.senders_by_id(message_id, mailbox):
                if self.sender[1].lower() not in sender.lower():
                    problems.append(f"record {e.record_number} ('{e.subject}') was saved from {sender}")
        return problems
