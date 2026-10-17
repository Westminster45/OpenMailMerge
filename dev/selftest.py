"""Headless self-test of the UNO parts, run inside LibreOffice by dev/run_selftest.sh.

Uses a throwaway LibreOffice profile, so the real one is untouched.
Writes results to $MMM_OUT/result.json.
"""

import json
import os
import sys
import traceback
from pathlib import Path

SRC = os.environ.get("MMM_SRC", "")
OUT = Path(os.environ.get("MMM_OUT", "/tmp"))


def run(*args):
    res = {"steps": {}}
    ctx = XSCRIPTCONTEXT.getComponentContext()  # noqa: F821 (provided by LibreOffice)
    desktop = XSCRIPTCONTEXT.getDesktop()  # noqa: F821
    try:
        sys.path.insert(0, SRC)
        import uno
        from mailmerge_mac import campaign, merge, office, preflight

        work = OUT / "work"
        work.mkdir(parents=True, exist_ok=True)

        # 1. Spreadsheet -> table (formatted values)
        calc = desktop.loadComponentFromURL("private:factory/scalc", "_blank", 0, office.props(Hidden=True))
        sheet = calc.Sheets.getByIndex(0)
        cells = [["First_Name", "Email", "Amount"], ["Zoë", "zoe@example.com", 1234.5], ["Bob", "bob@example.com", 7]]
        for r, row in enumerate(cells):
            for c, v in enumerate(row):
                cell = sheet.getCellByPosition(c, r)
                (cell.setValue if isinstance(v, (int, float)) else cell.setString)(v)
        xlsx = work / "people.xlsx"
        office.store(calc, xlsx, "Calc MS Excel 2007 XML")
        calc.close(True)
        table = office.read_table(ctx, xlsx)
        res["steps"]["read_table"] = {"headers": table.headers, "rows": table.rows}

        # 2. Writer document -> html/text template
        doc = desktop.loadComponentFromURL("private:factory/swriter", "_blank", 0, office.props(Hidden=True))
        text = doc.Text
        cur = text.createTextCursor()
        text.insertString(cur, "Dear «First_Name»,", False)
        text.insertControlCharacter(cur, 0, False)  # PARAGRAPH_BREAK
        cur.CharWeight = 150.0
        text.insertString(cur, "You owe «Amount». ", False)
        cur.CharWeight = 100.0
        text.insertString(cur, "Café ✓ {{Email}}", False)
        html, plain = office.export_template(doc)
        res["steps"]["export_template"] = {"html_has_field": "First_Name" in html, "html_len": len(html),
                                           "plain": plain, "html_body_excerpt": html[html.find("<body"):][:600]}

        # 3. Settings stored in the document
        office.save_settings(doc, {"subject": "Hello «First_Name»"})
        res["steps"]["settings"] = office.load_settings(doc)

        # 4. Preflight + PDF with password + campaign export
        s = merge.Settings(from_address="me@example.com", to_column="Email", subject="Hello «First_Name»",
                           attach_pdf=True, pdf_name="Letter «First_Name»", pdf_password="secret")
        rep = preflight.check(s, table, html, plain)
        res["steps"]["preflight"] = rep.text()
        folder = OUT / "campaign"
        (folder / "emails").mkdir(parents=True, exist_ok=True)
        maker = office.PdfMaker(ctx, doc, folder)
        job = campaign.Campaign(folder, ("Me", "me@example.com"), "export", pdf_maker=maker, body_text=plain)
        done, failed, stopped = job.run(rep.emails)
        pdfs = sorted(str(p) for p in folder.rglob("*.pdf"))
        first_pdf = Path(pdfs[0]).read_bytes() if pdfs else b""
        res["steps"]["campaign"] = {"done": len(done), "failed": [(e.record_number, w) for e, w in failed],
                                    "pdfs": pdfs, "pdf_encrypted": b"/Encrypt" in first_pdf,
                                    "emls": sorted(p.name for p in (folder / "emails").glob("*.eml"))}

        # 5. HTML-body mode
        s2 = merge.Settings(from_address="me@example.com", to_column="Email", subject="Hi «First_Name»")
        rep2 = preflight.check(s2, table, html, plain)
        res["steps"]["html_mode"] = {"ok": rep2.ok, "errors": rep2.errors,
                                     "first_html_has_name": "Zoë" in rep2.emails[0].html if rep2.emails else None}

        # 6. Dialog builds (not shown)
        from mailmerge_mac import dialog
        d = dialog.MailMergeDialog(ctx, doc, None)
        d.set_items("from_list", ["Me <me@example.com> – Test"])
        d.accounts = [("Test", "Me", "me@example.com")]
        d.table = table
        d.load_data(str(xlsx))
        d.go(2)
        d.pick_field = lambda: "First_Name"
        d.set_text("cc", "boss@example.com; ")
        d.c("cc").setSelection(uno.createUnoStruct("com.sun.star.awt.Selection", 18, 18))
        d.insert_field_into("cc")
        res["steps"]["field_button"] = d.text("cc")
        d.go(min(d.model.Step + 1, 5))
        res["steps"]["next_from_2"] = d.model.Step
        d.go(5)
        res["steps"]["next_enabled_on_5"] = d.c("next").isEnabled() if hasattr(d.c("next"), "isEnabled") else d.c("next").getModel().Enabled
        res["steps"]["dialog"] = {"controls": len(d.model.getElementNames()), "step": d.model.Step,
                                  "to_col": d.selected("to_col"), "from": d.selected_address(), "att_col": d.selected("att_col"), "importance": d.selected("importance")}
        d.dlg.dispose()
        doc.close(True)
        res["ok"] = True
    except Exception:
        res["ok"] = False
        res["error"] = traceback.format_exc()
    (OUT / "result.json").write_text(json.dumps(res, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    desktop.terminate()


g_exportedScripts = (run,)
