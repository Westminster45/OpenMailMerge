"""Tests for the pure-Python engine. Run: python3 -m unittest discover -s tests"""

import email
import sys
import tempfile
import unittest
from datetime import datetime
from email import policy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extension" / "pythonpath"))

from mailmerge_mac import data, merge, message, preflight, template  # noqa: E402

NOW = datetime(2026, 10, 16, 9, 30)
ROW = {"First_Name": "Zoë", "Email": "zoe@example.com", "Company": "A & B <Ltd>", "Blank": ""}


class TemplateTests(unittest.TestCase):
    def test_both_marker_styles_and_entities(self):
        text = "Hi «First_Name», {{ Company }} &laquo;First_Name&raquo; &#171;Email&#187;"
        out, missing, empty = template.render(text, ROW)
        self.assertEqual(out, "Hi Zoë, A & B <Ltd> Zoë zoe@example.com")
        self.assertEqual((missing, empty), ([], []))

    def test_html_escaping(self):
        out, _, _ = template.render("<p>«Company»</p>", ROW, escape=True)
        self.assertEqual(out, "<p>A &amp; B &lt;Ltd&gt;</p>")

    def test_case_insensitive_and_builtins(self):
        out, missing, _ = template.render("«first_name» «DATE» «RECORD_NUMBER»", ROW, record_number=7, now=NOW)
        self.assertEqual(out, "Zoë 16/10/2026 7")
        self.assertEqual(missing, [])

    def test_missing_and_empty(self):
        out, missing, empty = template.render("«Nope» «Blank»", ROW)
        self.assertEqual(missing, ["Nope"])
        self.assertEqual(empty, ["Blank"])
        self.assertTrue(template.has_leftover_markers(out))

    def test_split_marker_is_left_over(self):
        out, _, _ = template.render("«<span>First_Name</span>»", ROW)
        self.assertTrue(template.has_leftover_markers(out))

    def test_fields_in(self):
        self.assertEqual(template.fields_in("«A» {{B}} «A»"), ["A", "B"])


class DataTests(unittest.TestCase):
    def test_csv_semicolon_bom_blank_rows(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.csv"
            p.write_bytes("﻿Name;Email\nZoë;z@x.com\n;\nBob;b@x.com\n".encode("utf-8"))
            t = data.read_csv(p)
        self.assertEqual(t.headers, ["Name", "Email"])
        self.assertEqual([r["Name"] for r in t.rows], ["Zoë", "Bob"])

    def test_matrix_duplicate_and_blank_headers(self):
        t = data.from_matrix([["", ""], ["A", "", "A"], ["1", "2", "3"]])
        self.assertEqual(t.headers, ["A", "Column2", "A_"])
        self.assertEqual(t.rows[0], {"A": "1", "Column2": "2", "A_": "3"})


class MessageTests(unittest.TestCase):
    def test_build_eml(self):
        with tempfile.TemporaryDirectory() as d:
            att = Path(d) / "Invoice 1.pdf"
            att.write_bytes(b"%PDF-1.4 test")
            png = "iVBORw0KGgo="
            msg = message.build(
                ("Alex Smith", "alex@example.com"), "zoe@example.com; Bob <bob@example.com>",
                "Café ✓ 😀", f'<p>Hi</p><img src="data:image/png;base64,{png}">', "Hi",
                cc="c@example.com", bcc="b@example.com", reply_to="r@example.com",
                attachments=[att], importance="High")
            parsed = email.message_from_bytes(bytes(msg), policy=policy.default)
        self.assertEqual(parsed["From"], "Alex Smith <alex@example.com>")
        self.assertEqual(parsed["To"], "zoe@example.com, Bob <bob@example.com>")
        self.assertEqual(parsed["Subject"], "Café ✓ 😀")
        self.assertEqual((parsed["Cc"], parsed["Bcc"], parsed["Reply-To"]), ("c@example.com", "b@example.com", "r@example.com"))
        self.assertEqual(parsed["Importance"], "High")
        html = parsed.get_body(("html",))
        self.assertIn("cid:", html.get_content())
        types = [p.get_content_type() for p in parsed.walk()]
        self.assertIn("multipart/related", types)
        self.assertIn("image/png", types)
        self.assertEqual([a.get_filename() for a in parsed.iter_attachments()], ["Invoice 1.pdf"])

    def test_view_only_has_no_unsent_header(self):
        msg = message.build(("", "me@example.com"), "a@example.com", "S", "", "x", unsent=False)
        self.assertIsNone(msg["X-Unsent"])
        self.assertEqual(message.build(("", "me@example.com"), "a@example.com", "S", "", "x")["X-Unsent"], "1")

    def test_addresses_never_altered(self):
        self.assertEqual(message.split_addresses("a+x@y.com;b@y.com"), [("", "a+x@y.com"), ("", "b@y.com")])
        self.assertTrue(message.valid_address("a+x@y.co.uk"))
        self.assertFalse(message.valid_address("not an address"))
        self.assertFalse(message.valid_address("a@b"))


class MergeAndPreflightTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        d = Path(self.dir.name)
        (d / "a.pdf").write_bytes(b"x")
        self.table = data.from_matrix([
            ["First_Name", "Email", "File"],
            ["Zoë", "zoe@example.com", str(d / "a.pdf")],
            ["Bob", "bob@example.com", str(d / "missing.pdf")],
            ["", "bad address", ""],
            ["Zoë", "zoe@example.com", str(d / "*.pdf")],
        ])
        self.s = merge.Settings(from_address="me@example.com", to_column="Email",
                                subject="Hello «First_Name»", attachment_column="File", cc="boss@example.com")

    def tearDown(self):
        self.dir.cleanup()

    def test_render_email(self):
        e = merge.render_email(self.s, self.table.rows[0], 1, "<p>Dear «First_Name»</p>", "Dear «First_Name»", now=NOW)
        self.assertEqual((e.to, e.subject, e.html), ("zoe@example.com", "Hello Zoë", "<p>Dear Zoë</p>"))
        self.assertEqual(len(e.attachments), 1)

    def test_preflight_finds_problems(self):
        rep = preflight.check(self.s, self.table, "<p>Dear «First_Name» «Nope»</p>", "Dear «First_Name» «Nope»", now=NOW)
        text = rep.text()
        self.assertFalse(rep.ok)
        self.assertIn("Invalid To address: record 3 (bad address)", text)
        self.assertIn("Attachment not found", text)
        self.assertIn("Field «Nope» doesn't match any column", text)
        self.assertIn("Field «First_Name» is empty: record 3", text)
        self.assertIn("zoe@example.com is a To address in 2 records", text)
        self.assertIn("Cc has a fixed address", text)

    def test_range_and_exclusions(self):
        self.s.record_from, self.s.record_to = 1, 2
        rep = preflight.check(self.s, self.table, "x", "x", exclusions={"zoe@example.com"})
        self.assertEqual(rep.excluded, [1])
        self.assertEqual([e.record_number for e in rep.emails], [2])

    def test_pdf_mode(self):
        self.s.attach_pdf, self.s.pdf_name, self.s.pdf_password = True, "Letter «First_Name»", "«Email»"
        e = merge.render_email(self.s, self.table.rows[0], 1, "<p>«First_Name»</p>", "«First_Name»")
        self.assertEqual((e.pdf_name, e.pdf_password), ("Letter Zoë.pdf", "zoe@example.com"))
        self.assertIn("Dear Zoë", e.text)

    def test_campaign_export(self):
        from mailmerge_mac import campaign
        rep = preflight.check(self.s, data.from_matrix([["First_Name", "Email"], ["Zoë", "zoe@example.com"]]),
                              "<p>Dear «First_Name»</p>", "Dear «First_Name»")
        job = campaign.Campaign(Path(self.dir.name), ("Me", "me@example.com"), "export")
        (Path(self.dir.name) / "emails").mkdir()
        done, failed, stopped = job.run(rep.emails)
        self.assertEqual((len(done), failed, stopped), (1, [], False))
        eml = next((Path(self.dir.name) / "emails").glob("*.eml"))
        parsed = email.message_from_bytes(eml.read_bytes(), policy=policy.default)
        self.assertEqual((parsed["From"], parsed["To"], parsed["Subject"]), ("Me <me@example.com>", "zoe@example.com", "Hello Zoë"))
        self.assertIn("exported", (Path(self.dir.name) / "log.csv").read_text())

    def test_settings_roundtrip_ignores_unknown(self):
        s = merge.Settings.from_dict({"subject": "x", "unknown": 1})
        self.assertEqual(s.subject, "x")


if __name__ == "__main__":
    unittest.main()
