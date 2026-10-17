"""Tests for the Apple Mail step, with Mail replaced by a fake (no real Mail involved).

The route: all emails of a run -> one mailbox file -> Mail imports it once ("OpenMailMerge - <date>")
-> Drafts: each email is moved into the From account's Drafts / Send: each is redirected to its
To / Cc / Bcc and sent -> confirmed in Drafts / Outbox / Sent by Message-ID.
"""

import mailbox
import sys
import tempfile
import unittest
from datetime import datetime
from email import policy
from email.parser import BytesParser
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extension" / "pythonpath"))

from mailmerge_mac import campaign, mailapp, merge, message  # noqa: E402

ME = ("Alex Smith", "alex@example.com")


class FakeMail:
    """Mail's scripting, as seen by mailapp."""

    def __init__(self, lands=True, import_fails=False):
        self.lands, self.import_fails = lands, import_fails
        self.imported = []      # parsed messages from the imported mailbox file
        self.imports = []       # (inner name, top name asked for)
        self.delivered = []     # dicts of what DELIVER was given
        self.drafts, self.outbox = [], []   # Message-IDs

    def osa(self, script, timeout=30, args=()):
        if script is mailapp.IMPORT:
            box_path, inner, top, expected = args
            if self.import_fails:
                raise mailapp.MailError("Mail didn't import the emails.")
            box = mailbox.mbox(str(Path(box_path) / "mbox"))
            self.imported = [BytesParser(policy=policy.default).parsebytes(m.as_bytes()) for m in box]
            box.close()
            assert len(self.imported) == int(expected)
            self.imports.append((inner, top))
            return top
        if script is mailapp.DELIVER:
            top, inner, msg_id, action, sender, to, cc, bcc = args
            self.delivered.append({"source": (top, inner), "id": msg_id, "action": action,
                                   "sender": sender, "to": to, "cc": cc, "bcc": bcc})
            if self.lands:
                (self.drafts if action == "draft" else self.outbox).append(msg_id)
            return "ok"
        raise AssertionError("unexpected script")

    def count(self, msg_id, mailbox="drafts mailbox"):
        box = self.outbox if mailbox == "outbox" else self.drafts if mailbox == "drafts mailbox" else []
        return box.count(msg_id)


def clock():
    t = [0.0]

    def now():
        t[0] += 0.05
        return t[0]
    return now


class MailTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.attachment = self.dir / "letter.pdf"
        self.attachment.write_bytes(b"%PDF-1.4 test")

    def tearDown(self):
        self.tmp.cleanup()

    def mail(self, fake, online=False):
        return [mock.patch.object(mailapp, "osa", fake.osa),
                mock.patch.object(mailapp, "offline_state", lambda: not online),
                mock.patch.object(mailapp, "count_by_id", fake.count),
                mock.patch.object(mailapp.time, "sleep", lambda s: None),
                mock.patch.object(mailapp.time, "time", clock())]

    def run_with(self, fake, fn, online=False):
        patches = self.mail(fake, online)
        for p in patches:
            p.start()
        try:
            return fn()
        finally:
            for p in reversed(patches):
                p.stop()


class MailStepTests(MailTestCase):
    def eml(self, name="1", subject="Hello – test", **kw):
        msg = message.build(ME, '"Smith, Alex" <alex@example.com>', subject,
                            "<p>Dear Alex, this is <b>bold</b>.</p>", "Dear Alex",
                            attachments=[self.attachment], **kw)
        path = self.dir / f"{name}.eml"
        path.write_bytes(bytes(msg))
        return path

    def test_import_names_the_mailbox_by_date_and_drops_x_unsent(self):
        fake = FakeMail()
        emls = [self.eml("1", reply_to="office@example.com"), self.eml("2", bcc="b@example.com")]
        source = self.run_with(fake, lambda: mailapp.import_batch(
            emls, self.dir, "Letter 2026-10-17 150000", when=datetime(2026, 10, 17, 15, 0)))
        self.assertEqual(source, ("OpenMailMerge - 2026-10-17 1500", "Letter 2026-10-17 150000"))
        self.assertEqual(len(fake.imported), 2)
        self.assertTrue(all(m["X-Unsent"] is None for m in fake.imported))
        self.assertEqual(fake.imported[0]["Reply-To"], "office@example.com")  # kept: Mail sends it unchanged
        self.assertEqual(fake.imported[1]["Bcc"], "b@example.com")            # drafts keep Bcc

    def test_send_import_drops_bcc_header(self):
        # A redirect sends the headers as they are, so a Bcc header would show to every recipient.
        fake = FakeMail()
        self.run_with(fake, lambda: mailapp.import_batch([self.eml(bcc="b@example.com")], self.dir, "x",
                                                         strip_bcc=True))
        self.assertIsNone(fake.imported[0]["Bcc"])

    def test_draft_is_moved_into_the_senders_drafts(self):
        fake = FakeMail()
        eml = self.eml(cc="a@example.com", bcc="Bob <b@example.com>")
        self.run_with(fake, lambda: mailapp.create_message(eml, "Hello – test", ("Top", "Inner")))
        d = fake.delivered[0]
        self.assertEqual((d["source"], d["action"], d["sender"]),
                         (("Top", "Inner"), "draft", "alex@example.com"))
        self.assertTrue(d["id"].endswith("@mailmerge-mac.local") and not d["id"].startswith("<"))
        self.assertEqual(fake.drafts, [d["id"]])

    def test_send_redirects_to_to_cc_and_bcc(self):
        fake = FakeMail()
        eml = self.eml(cc="a@example.com", bcc="Bob <b@example.com>")
        self.run_with(fake, lambda: mailapp.create_message(eml, "Hello – test", ("Top", "Inner"), "outbox"))
        d = fake.delivered[0]
        self.assertEqual(d["action"], "outbox")
        self.assertEqual(d["to"], "Smith, Alex\talex@example.com")
        self.assertEqual(d["cc"], "\ta@example.com")
        self.assertEqual(d["bcc"], "Bob\tb@example.com")
        self.assertEqual(fake.outbox, [d["id"]])

    def test_online_with_offline_required_stops_without_doing_anything(self):
        fake = FakeMail()
        eml = self.eml()
        with self.assertRaisesRegex(mailapp.MailError, "Mail is online"):
            self.run_with(fake, lambda: mailapp.create_message(eml, "S", ("T", "I"), "outbox"), online=True)
        self.assertEqual(fake.delivered, [])

    def test_email_not_landing_is_reported(self):
        fake = FakeMail(lands=False)
        eml = self.eml()
        with self.assertRaisesRegex(mailapp.MailError, "didn't appear in Drafts"):
            self.run_with(fake, lambda: mailapp.create_message(eml, "S", ("T", "I")))


class CampaignTests(MailTestCase):
    def emails(self, n):
        out = []
        for i in range(1, n + 1):
            e = merge.Email(record_number=i, row={}, to=f"Person {i} <p{i}@example.com>", subject="Same subject",
                            html=f"<p>Dear {i}</p>", text=f"Dear {i}")
            out.append(e)
        return out

    def job(self, mode):
        folder = self.dir / "Letter 2026-10-17 150000"
        (folder / "emails").mkdir(parents=True)
        return campaign.Campaign(folder, ME, mode)

    def test_drafts_import_once_then_each_email(self):
        fake = FakeMail()
        job = self.job("drafts")
        done, failed, stopped = self.run_with(fake, lambda: job.run(self.emails(3)))
        self.assertEqual((len(done), failed, stopped), (3, [], False))
        self.assertEqual(len(fake.imports), 1)
        self.assertEqual(fake.imports[0][0], "Letter 2026-10-17 150000")
        self.assertEqual([d["action"] for d in fake.delivered], ["draft"] * 3)
        self.assertEqual(len(set(d["id"] for d in fake.delivered)), 3)  # same subject, told apart by Message-ID

    def test_failed_import_fails_every_email_and_stops(self):
        fake = FakeMail(import_fails=True)
        job = self.job("outbox")
        done, failed, stopped = self.run_with(fake, lambda: job.run(self.emails(2)))
        self.assertEqual((done, len(failed), stopped), ([], 2, True))
        self.assertIn("Couldn't import", failed[0][1])
        self.assertEqual(fake.delivered, [])


if __name__ == "__main__":
    unittest.main()
