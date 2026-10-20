"""The MailMerge window: five pages (Data, Message, Attachments, Check & preview, Create).

The window is non-modal, so the document can still be edited (e.g. to insert fields)
while it is open. Settings are saved in the document.
"""

import dataclasses
import os
import re
import subprocess
import tempfile
import traceback
from pathlib import Path

import uno
import unohelper
from com.sun.star.awt import XActionListener, XItemListener, XTopWindowListener

from . import VERSION, campaign, debug, mailapp, merge, office, preflight, release_notes, settings_check

PROJECT_URL = "https://github.com/Westminster45/OpenMailMerge"
PAGES = ["1. Data", "2. Message", "3. Attachments", "4. Check & preview", "5. Create"]
W, H = 340, 290
NONE = "(none)"
BOLD, NORMAL = 150.0, 100.0
TYPED_CONFIRM_OVER = 20
OK, YES = 1, 2
BUTTONS_OK, BUTTONS_OK_CANCEL, BUTTONS_YES_NO = 1, 2, 3

_open = {}  # document URL/title -> MailMergeDialog


def open_dialog(ctx, doc, frame):
    key = id(doc)
    if key in _open:
        _open[key].dlg.setFocus()
        return
    d = MailMergeDialog(ctx, doc, frame)
    _open[key] = d
    d.show()


class _Action(unohelper.Base, XActionListener):
    def __init__(self, ui, fn):
        self.ui, self.fn = ui, fn

    def actionPerformed(self, ev):
        self.ui.safe(self.fn)

    def disposing(self, ev):
        pass


class _Item(unohelper.Base, XItemListener):
    def __init__(self, ui, fn):
        self.ui, self.fn = ui, fn

    def itemStateChanged(self, ev):
        self.ui.safe(self.fn)

    def disposing(self, ev):
        pass


class _Closer(unohelper.Base, XTopWindowListener):
    def __init__(self, ui):
        self.ui = ui

    def windowClosing(self, ev):
        self.ui.safe(self.ui.close)

    def windowOpened(self, ev): pass
    def windowClosed(self, ev): pass
    def windowMinimized(self, ev): pass
    def windowNormalized(self, ev): pass
    def windowActivated(self, ev): pass
    def windowDeactivated(self, ev): pass
    def disposing(self, ev): pass


class MailMergeDialog:
    def __init__(self, ctx, doc, frame):
        self.ctx, self.doc, self.frame = ctx, doc, frame
        self.smgr = ctx.ServiceManager
        self.toolkit = self.smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
        self.settings_key = settings_check.load_key(office.settings_key_path(ctx))
        self.settings = merge.Settings.from_dict(self.saved_settings(doc))
        self.table = None
        self.accounts = []  # (account, full name, address)
        self.report = None
        self.preview_index = 0
        self.running = False
        self.stop_requested = False
        self.last_folder = None
        self.listeners = []

        self.model = self.smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialogModel", ctx)
        self.model.Width, self.model.Height = W, H
        self.model.Title = f"OpenMailMerge {VERSION} – {doc.getTitle()}"
        self.model.Moveable = True
        self.model.Closeable = True
        self.dlg = self.smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", ctx)
        self.dlg.setModel(self.model)
        self.build()
        self.apply_settings()

    def saved_settings(self, doc):
        """The settings saved in doc. Unless this user saved them (see settings_check), Cc, Bcc, Reply-To,
        the files attached to every email and the PDF password stay blank unless the user agrees to them."""
        use, held = settings_check.check_saved(office.load_settings(doc), self.settings_key)
        if held:
            debug(f"saved settings not verified; asking about: {', '.join(sorted(held))}")
            try:
                agreed = self.ask_saved_settings(settings_check.describe(held), settings_check.leave_blank_note(held))
            except Exception:
                debug("asking about saved settings failed:\n" + traceback.format_exc())
                agreed = False
            if agreed:
                use = settings_check.restore(use, held)
        return use

    def ask_saved_settings(self, lines, note=""):
        """Show the held-back settings, and note (if any) just above the buttons. True only if the user clicks
        Use these settings; Leave these blank (the default button, focused first), Escape and the close box
        all mean no."""
        more = 12 if note else 0  # room for the note's line
        m = self.smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialogModel", self.ctx)
        m.Width, m.Height, m.Title = 260, 168 + more, "Check these saved settings"
        d = self.smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", self.ctx)
        d.setModel(m)
        controls = [
                ("FixedText", "p", 6, 6, 248, 36, {"MultiLine": True, "Label":
                    "This document includes email settings that were saved on another computer, by someone else, "
                    "or by an older version of OpenMailMerge. Please check you're happy to use them:"}),
                ("Edit", "list", 6, 46, 248, 80, {"Text": "\n".join(lines), "MultiLine": True, "ReadOnly": True,
                                                  "VScroll": True, "TabIndex": 2}),
                ("FixedText", "later", 6, 130, 248, 10, {"Label": "You can change any of these later in the merge window."}),
                ("Button", "use", 90, 148 + more, 80, 14, {"Label": "Use these settings", "PushButtonType": 1, "TabIndex": 1}),
                ("Button", "blank", 174, 148 + more, 80, 14, {"Label": "Leave these blank", "PushButtonType": 2,
                                                              "DefaultButton": True, "TabIndex": 0})]
        if note:
            controls.append(("FixedText", "note", 6, 142, 248, 10, {"Label": note}))
        return self.run_small_dialog(m, d, controls) == 1

    def run_small_dialog(self, m, d, controls):
        """Add controls [(kind, name, x, y, w, h, {property: value})] to dialog d (model m), show it until
        it's closed and return how it was closed (1 = the OK-type button)."""
        for kind, name, x, y, w, h, extra in controls:
            cm = m.createInstance(f"com.sun.star.awt.UnoControl{kind}Model")
            cm.PositionX, cm.PositionY, cm.Width, cm.Height = x, y, w, h
            for k, v in extra.items():
                setattr(cm, k, v)
            m.insertByName(name, cm)
        d.createPeer(self.toolkit, self.frame.getContainerWindow() if self.frame else None)
        result = d.execute()
        d.dispose()
        return result

    def show_about(self):
        m = self.smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialogModel", self.ctx)
        m.Width, m.Height, m.Title = 260, 236, "About OpenMailMerge"
        d = self.smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", self.ctx)
        d.setModel(m)
        self.run_small_dialog(m, d, [
            ("FixedText", "name", 6, 6, 248, 12, {"Label": "OpenMailMerge", "FontWeight": BOLD}),
            ("FixedText", "version", 6, 20, 248, 10, {"Label": f"Version {VERSION}"}),
            ("FixedText", "what", 6, 32, 248, 10, {"Label": "Mail merge from LibreOffice Writer to Apple Mail."}),
            ("FixedText", "licence", 6, 44, 248, 10, {"Label": "Free and open source, under the Mozilla Public License 2.0."}),
            ("FixedHyperlink", "site", 6, 56, 248, 10, {"Label": "Project page, earlier versions and source code",
                                                        "URL": PROJECT_URL}),
            ("FixedText", "l_notes", 6, 74, 248, 10, {"Label": "Release notes and version history:"}),
            ("Edit", "notes", 6, 86, 248, 124, {"Text": release_notes(), "MultiLine": True, "ReadOnly": True,
                                                "VScroll": True}),
            ("Button", "ok", 194, 216, 60, 14, {"Label": "Close", "PushButtonType": 1, "DefaultButton": True})])

    # ---------- small helpers ----------

    def add(self, kind, name, x, y, w, h, page=0, **p):
        m = self.model.createInstance(f"com.sun.star.awt.UnoControl{kind}Model")
        m.Name = name
        m.PositionX, m.PositionY, m.Width, m.Height = x, y, w, h
        m.Step = page
        for k, v in p.items():
            setattr(m, k, v)
        self.model.insertByName(name, m)
        return self.dlg.getControl(name)

    def label(self, name, text, x, y, w, h=10, page=0, **p):
        return self.add("FixedText", name, x, y, w, h, page, Label=text, MultiLine=h > 12, **p)

    def edit(self, name, x, y, w, h=12, page=0, **p):
        return self.add("Edit", name, x, y, w, h, page, **p)

    def button(self, name, text, fn, x, y, w, h=14, page=0, **p):
        c = self.add("Button", name, x, y, w, h, page, Label=text, **p)
        listener = _Action(self, fn)
        self.listeners.append(listener)
        c.addActionListener(listener)
        return c

    def listbox(self, name, x, y, w, h=12, page=0, dropdown=True, on_change=None, **p):
        c = self.add("ListBox", name, x, y, w, h, page, Dropdown=dropdown, LineCount=12, **p)
        if on_change:
            listener = _Item(self, on_change)
            self.listeners.append(listener)
            c.addItemListener(listener)
        return c

    def check(self, name, text, x, y, w, h=10, page=0, on_change=None):
        c = self.add("CheckBox", name, x, y, w, h, page, Label=text)
        if on_change:
            listener = _Item(self, on_change)
            self.listeners.append(listener)
            c.addItemListener(listener)
        return c

    def c(self, name):
        return self.dlg.getControl(name)

    def text(self, name):
        return self.c(name).getText()

    def set_text(self, name, value):
        self.c(name).setText(value or "")

    def set_label(self, name, value):
        self.c(name).getModel().Label = value or ""

    # List boxes are handled through their models, which works with or without a visible window.

    def items(self, name):
        return list(self.c(name).getModel().StringItemList)

    def set_items(self, name, items, select=None):
        m = self.c(name).getModel()
        m.StringItemList = tuple(items)
        if select is not None and select in items:
            self.select_pos(name, list(items).index(select))
        elif items and m.Dropdown:
            self.select_pos(name, 0)
        else:
            self.select_pos(name, -1)

    def select_pos(self, name, pos):
        m = self.c(name).getModel()
        uno.invoke(m, "setPropertyValue", ("SelectedItems", uno.Any("[]short", (pos,) if pos >= 0 else ())))

    def selected_pos(self, name):
        sel = self.c(name).getModel().SelectedItems
        return sel[0] if sel else -1

    def selected(self, name):
        pos, items = self.selected_pos(name), self.items(name)
        item = items[pos] if 0 <= pos < len(items) else ""
        return "" if item == NONE else item

    def checked(self, name):
        return bool(self.c(name).getState())

    def msg(self, text, title="OpenMailMerge", kind="INFOBOX", buttons=BUTTONS_OK):
        box = self.toolkit.createMessageBox(self.dlg.getPeer(), uno.Enum("com.sun.star.awt.MessageBoxType", kind),
                                            buttons, title, text)
        result = box.execute()
        box.dispose()
        return result

    def status(self, text):
        self.set_label("status", text)
        self.pump()

    def pump(self):
        try:
            self.toolkit.processEventsToIdle()
        except Exception:
            pass

    def safe(self, fn):
        try:
            fn()
        except mailapp.MailError as e:
            self.msg(mailapp.explain(e), "Apple Mail", "ERRORBOX")
        except Exception:
            debug("handler failed:\n" + traceback.format_exc())
            self.msg("Something went wrong:\n\n" + traceback.format_exc()[-1500:], "OpenMailMerge error", "ERRORBOX")

    # ---------- layout ----------

    def build(self):
        for i, name in enumerate(PAGES):
            self.button(f"tab{i + 1}", name, lambda n=i + 1: self.go(n), 6 + i * 66, 4, 64, 14)

        # 1. Data
        p = 1
        self.label("l_data", "Recipients – a spreadsheet or CSV file whose first row has the column names:", 6, 26, 328, page=p)
        self.edit("data_file", 6, 38, 270, page=p, ReadOnly=True)
        self.button("data_choose", "Choose…", self.choose_data, 280, 37, 54, page=p)
        self.label("data_info", "No file chosen.", 6, 54, 328, 22, page=p)
        self.label("l_body", "The body of each email is this document. Mark where the data goes with fields such as «First_Name».",
                   6, 80, 328, 18, page=p)
        self.label("l_field", "Field:", 6, 104, 30, page=p)
        self.listbox("field_list", 36, 102, 120, page=p)
        self.button("ins_doc", "Insert in document", self.insert_in_document, 160, 101, 86, page=p)
        self.button("ins_subj", "Add to subject", self.insert_in_subject, 250, 101, 84, page=p)
        self.label("tips1",
                   "Tips:\n"
                   "• Click in the document where the field should go, choose the field, then click Insert in document. "
                   "This window can stay open while you edit.\n"
                   "• You can also type fields: «Name» (Option+\\ and Option+Shift+\\) or {{Name}}.\n"
                   "• Built-in fields: «DATE», «TIME», «RECORD_NUMBER».\n"
                   "• Keep each field in one style (don't make half of it bold), or it can't be found.",
                   6, 124, 328, 70, page=p)

        # 2. Message
        p = 2
        rows = [("From:", 26), ("To column:", 42), ("Cc:", 58), ("Bcc:", 74), ("Reply-To:", 90), ("Subject:", 106), ("Importance:", 122)]
        for i, (t, y) in enumerate(rows):
            self.label(f"l_msg{i}", t, 6, y + 2, 52, page=p)
        self.listbox("from_list", 60, 26, 214, page=p)
        self.button("from_refresh", "Refresh", self.load_accounts, 280, 25, 54, page=p)
        self.listbox("to_col", 60, 42, 274, page=p)
        self.edit("cc", 60, 58, 254, page=p)
        self.button("f_cc", "…", lambda: self.insert_field_into("cc"), 318, 58, 16, 12, page=p, HelpText="Insert a merge field")
        self.edit("bcc", 60, 74, 254, page=p)
        self.button("f_bcc", "…", lambda: self.insert_field_into("bcc"), 318, 74, 16, 12, page=p, HelpText="Insert a merge field")
        self.edit("reply_to", 60, 90, 254, page=p)
        self.button("f_reply_to", "…", lambda: self.insert_field_into("reply_to"), 318, 90, 16, 12, page=p, HelpText="Insert a merge field")
        self.edit("subject", 60, 106, 254, page=p)
        self.button("f_subject", "…", lambda: self.insert_field_into("subject"), 318, 106, 16, 12, page=p, HelpText="Insert a merge field")
        self.listbox("importance", 60, 122, 80, page=p)
        self.label("l_msghint", "Addresses are used exactly as written; separate several with ;. Click … to put a merge field in Subject, Cc, Bcc or Reply-To.",
                   146, 121, 188, 18, page=p)
        self.check("attach_pdf", "Send this document as a PDF attachment instead of in the email body", 6, 144, 328, page=p,
                   on_change=self.update_enabled)
        self.label("l_pdfname", "PDF file name:", 16, 160, 70, page=p)
        self.edit("pdf_name", 90, 158, 224, page=p)
        self.button("f_pdf_name", "…", lambda: self.insert_field_into("pdf_name"), 318, 158, 16, 12, page=p,
                    HelpText="Insert a merge field")
        self.label("l_pdfpw", "PDF password:", 16, 176, 70, page=p)
        self.edit("pdf_password", 90, 174, 206, page=p)
        self.button("pdf_password_help", "?", self.explain_pdf_password, 300, 174, 14, 12, page=p,
                    HelpText="How safe is the PDF password?")
        self.button("f_pdf_password", "…", lambda: self.insert_field_into("pdf_password"), 318, 174, 16, 12, page=p,
                    HelpText="Insert a merge field")
        self.label("l_pdfpwhint", "Optional. Can be a field, e.g. «Postcode», so each person gets their own password.", 90, 188, 244, page=p)
        self.label("l_pdfbody", "Email body to go with the PDF:", 16, 202, 200, page=p)
        self.button("f_pdf_body", "Insert field…", lambda: self.insert_field_into("pdf_body"), 264, 199, 70, 12, page=p)
        self.edit("pdf_body", 16, 213, 318, 44, page=p, MultiLine=True, VScroll=True)

        # 3. Attachments
        p = 3
        self.label("l_static", "Files attached to every email:", 6, 26, 270, page=p)
        self.listbox("static_list", 6, 38, 270, 90, page=p, dropdown=False)
        self.button("static_add", "Add…", self.add_static, 280, 37, 54, page=p)
        self.button("static_remove", "Remove", self.remove_static, 280, 54, 54, page=p)
        self.label("l_attcol", "Different files per recipient – the column that holds their file paths:", 6, 136, 328, page=p)
        self.listbox("att_col", 6, 148, 200, page=p)
        self.label("tips3",
                   "In that column give the full path, e.g. /Users/you/Invoices/1001.pdf. Separate several files with ; "
                   "and use wildcards like /Users/you/Invoices/1001*.pdf. The check reports any file that can't be found.",
                   6, 166, 328, 30, page=p)

        # 4. Check & preview
        p = 4
        self.button("run_check", "Run check", self.run_check, 6, 24, 80, page=p)
        self.label("check_summary", "Run the check to see any problems before creating emails.", 92, 27, 242, page=p)
        self.edit("check_text", 6, 42, 328, 80, page=p, MultiLine=True, ReadOnly=True, VScroll=True)
        self.label("l_prev", "Preview", 6, 128, 60, page=p, FontWeight=BOLD)
        self.button("prev_back", "◀", lambda: self.move_preview(-1), 6, 140, 20, page=p)
        self.label("prev_pos", "", 30, 143, 120, page=p)
        self.button("prev_next", "▶", lambda: self.move_preview(1), 152, 140, 20, page=p)
        self.button("prev_full", "Open full preview", self.open_full_preview, 240, 140, 94, page=p)
        self.label("prev_head", "", 6, 158, 328, 42, page=p)
        self.edit("prev_body", 6, 202, 328, 55, page=p, MultiLine=True, ReadOnly=True, VScroll=True)

        # 5. Create
        p = 5
        self.label("l_rec", "Records:", 6, 27, 40, page=p)
        self.add("RadioButton", "rec_all", 48, 26, 30, 10, p, Label="All")
        self.add("RadioButton", "rec_range", 80, 26, 30, 10, p, Label="From")
        self.edit("rec_from", 112, 24, 30, page=p)
        self.label("l_recto", "to", 146, 27, 12, page=p)
        self.edit("rec_to", 160, 24, 30, page=p)
        self.label("l_excl", "Never email the addresses in this file (exclusion list, optional):", 6, 44, 328, page=p)
        self.edit("excl_file", 6, 55, 238, page=p, ReadOnly=True)
        self.button("excl_choose", "Choose…", self.choose_exclusions, 248, 54, 44, page=p)
        self.button("excl_clear", "Clear", lambda: self.set_text("excl_file", ""), 296, 54, 38, page=p)
        self.check("req_offline", "Mail must be offline while emails are created (recommended: nothing can be sent by accident)",
                   6, 74, 328, page=p)
        self.label("create_info",
                   "Create drafts puts each email in Mail's Drafts, without opening windows. Nothing is sent; "
                   "check and send them yourself from Mail's Drafts.\n"
                   "Each run adds a 'OpenMailMerge - date' mailbox under On My Mac; delete it when done.",
                   6, 88, 328, 36, page=p)
        self.button("perm", "Check permissions", self.check_permissions, 6, 128, 64, page=p)
        self.button("test_draft", "Show in Mail", self.show_in_mail, 73, 128, 64, page=p)
        self.button("export", "Export .eml only", lambda: self.create("export"), 140, 128, 62, page=p)
        self.button("create", "Create drafts", lambda: self.create("drafts"), 205, 128, 62, page=p, FontWeight=BOLD)
        self.button("send", "Send…", lambda: self.create("outbox"), 270, 128, 64, page=p, FontWeight=BOLD)
        self.label("send_info", "Send… with 'Mail must be offline' ticked leaves the emails in Mail's Outbox until you choose "
                   "Mailbox > Take All Accounts Online. Unticked, they are sent straight away.", 6, 146, 328, 18, page=p)
        self.label("progress", "", 6, 166, 328, 46, page=p)
        self.button("stop", "Stop", self.request_stop, 6, 214, 60, page=p, Enabled=False)
        self.button("open_folder", "Open output folder", self.open_output_folder, 70, 214, 90, page=p)

        self.label("status", "", 6, 264, 180, 20)
        about = self.add("FixedHyperlink", "about", 190, 270, 26, 10, Label="About", HelpText="Version and release notes")
        listener = _Action(self, self.show_about)  # with a listener, a click runs it instead of opening a URL
        self.listeners.append(listener)
        about.addActionListener(listener)
        self.button("next", "Next ›", lambda: self.go(min(self.model.Step + 1, len(PAGES))), 220, 266, 56)
        self.button("close", "Close", self.close, 280, 266, 54)
        self.go(1)

    def go(self, page):
        self.model.Step = page
        for i in range(1, len(PAGES) + 1):
            self.c(f"tab{i}").getModel().FontWeight = BOLD if i == page else NORMAL
        self.c("next").setEnable(page < len(PAGES))
        if page == 4 and self.report is None and self.table is not None:
            self.run_check()

    # ---------- settings <-> controls ----------

    def apply_settings(self):
        s = self.settings
        self.set_text("data_file", s.data_file)
        self.set_text("cc", s.cc)
        self.set_text("bcc", s.bcc)
        self.set_text("reply_to", s.reply_to)
        self.set_text("subject", s.subject)
        self.set_items("importance", ["Normal", "High", "Low"], s.importance)
        self.c("attach_pdf").setState(1 if s.attach_pdf else 0)
        self.set_text("pdf_name", s.pdf_name)
        self.set_text("pdf_password", s.pdf_password)
        self.set_text("pdf_body", s.pdf_body)
        self.set_items("static_list", s.static_attachments)
        self.c("rec_range" if s.record_from or s.record_to else "rec_all").setState(True)
        self.set_text("rec_from", str(s.record_from or ""))
        self.set_text("rec_to", str(s.record_to or ""))
        self.set_text("excl_file", s.exclusion_file)
        self.c("req_offline").setState(1 if s.require_offline else 0)
        self.update_enabled()

    def collect(self):
        s = self.settings
        s.data_file = self.text("data_file")
        s.from_address = self.selected_address()
        s.to_column = self.selected("to_col")
        s.cc, s.bcc, s.reply_to = self.text("cc"), self.text("bcc"), self.text("reply_to")
        s.subject = self.text("subject")
        s.importance = self.selected("importance") or "Normal"
        s.attach_pdf = self.checked("attach_pdf")
        s.pdf_name, s.pdf_password, s.pdf_body = self.text("pdf_name"), self.text("pdf_password"), self.text("pdf_body")
        s.static_attachments = self.items("static_list")
        s.attachment_column = self.selected("att_col")
        if self.c("rec_range").getState():
            s.record_from, s.record_to = self.number("rec_from"), self.number("rec_to")
        else:
            s.record_from = s.record_to = 0
        s.exclusion_file = self.text("excl_file")
        s.require_offline = self.checked("req_offline")
        office.save_settings(self.doc, settings_check.sign(dataclasses.asdict(s), self.settings_key))
        return s

    def number(self, name):
        digits = re.sub(r"\D", "", self.text(name))
        return int(digits) if digits else 0

    def update_enabled(self):
        on = self.checked("attach_pdf")
        for name in ("l_pdfname", "pdf_name", "l_pdfpw", "pdf_password", "l_pdfpwhint", "l_pdfbody", "pdf_body",
                     "f_pdf_name", "f_pdf_password", "f_pdf_body"):
            self.c(name).setEnable(on)

    def explain_pdf_password(self):
        self.msg("The password stops people opening the PDF without it, for example if the email "
                 "goes to the wrong person or is forwarded on.\n\n"
                 "It is not strong protection:\n"
                 "• The password is saved in this document as plain text. Anyone with a copy of the "
                 "document can find it.\n"
                 "• If you use a field such as «Postcode» or a date of birth, anyone who knows or can "
                 "guess that detail can open the PDF.\n\n"
                 "Think of it as a lock against casual looking, not as a way to keep sensitive "
                 "information secure.", title="About the PDF password")

    # ---------- page 1: data ----------

    def choose_data(self):
        files = office.pick_files(self.ctx, "Choose the recipients file",
                                  [("Spreadsheets and CSV", "*.xlsx;*.xls;*.ods;*.csv;*.numbers"), ("All files", "*.*")])
        if files:
            self.set_text("data_file", files[0])
            self.load_data(files[0])
            self.collect()

    def load_data(self, path):
        if not path:
            return
        if not Path(path).is_file():
            self.set_label("data_info", f"File not found: {path}")
            return
        self.status("Reading recipients…")
        self.table = office.read_table(self.ctx, path)
        self.report = None
        t = self.table
        self.set_label("data_info", f"{len(t)} records. Columns: {', '.join(t.headers)}")
        self.set_items("field_list", t.headers)
        guess = self.settings.to_column if self.settings.to_column in t.headers else \
            next((h for h in t.headers if "mail" in h.lower()), None)
        self.set_items("to_col", t.headers, guess)
        att = [NONE] + t.headers
        self.set_items("att_col", att, self.settings.attachment_column or NONE)
        self.status(f"Loaded {len(t)} records.")

    def insert_in_document(self):
        name = self.selected("field_list")
        if name:
            office.insert_field(self.doc, name)
            self.report = None
            self.status(f"Inserted «{name}» at the cursor in the document.")

    def insert_in_subject(self):
        name = self.selected("field_list")
        if name:
            self.set_text("subject", (self.text("subject") + f" «{name}»").strip())
            self.go(2)

    # ---------- page 2: accounts ----------

    def load_accounts(self):
        self.status("Asking Apple Mail for its accounts…")
        try:
            self.accounts = mailapp.enabled_accounts()
        except mailapp.MailError as e:
            self.accounts = []
            self.set_items("from_list", [])
            self.status("Couldn't read Apple Mail's accounts.")
            self.msg(mailapp.explain(e), "Apple Mail", "WARNINGBOX")
            return
        items = [self.account_label(a) for a in self.accounts]
        current = next((self.account_label(a) for a in self.accounts
                        if a[2].lower() == (self.settings.from_address or "").lower()), None)
        self.set_items("from_list", items, current)
        self.status(f"{len(items)} sending address(es) found in Apple Mail." if items else
                    "No accounts are switched on in Apple Mail (Mail > Settings > Accounts).")

    @staticmethod
    def account_label(a):
        account, name, address = a
        return f"{name} <{address}> – {account}" if name else f"{address} – {account}"

    def selected_account(self):
        pos = self.selected_pos("from_list")
        return self.accounts[pos] if 0 <= pos < len(self.accounts) else None

    def selected_address(self):
        a = self.selected_account()
        return a[2] if a else ""

    # ---------- page 3: attachments ----------

    def add_static(self):
        files = office.pick_files(self.ctx, "Files to attach to every email", multi=True)
        existing = self.items("static_list")
        self.set_items("static_list", existing + [f for f in files if f not in existing])
        self.report = None

    def remove_static(self):
        pos, items = self.selected_pos("static_list"), self.items("static_list")
        if 0 <= pos < len(items):
            del items[pos]
            self.set_items("static_list", items)
            self.report = None

    # ---------- page 4: check & preview ----------

    def run_check(self):
        s = self.collect()
        if self.table is None and s.data_file:
            self.load_data(s.data_file)
        if self.table is None:
            self.set_text("check_text", "Choose the recipients file on page 1 first.")
            return None
        self.status("Checking every email…")
        self.template = office.export_template(self.doc)
        exclusions = merge.read_exclusions(s.exclusion_file)
        self.report = preflight.check(s, self.table, self.template[0], self.template[1], exclusions)
        rep = self.report
        self.set_text("check_text", rep.text())
        self.set_label("check_summary",
                       f"{len(rep.errors)} error(s), {len(rep.warnings)} warning(s), {len(rep.emails)} email(s).")
        self.preview_index = 0
        self.show_preview()
        self.status("Check finished." if rep.ok else "Check found errors – see page 4.")
        return rep

    def show_preview(self):
        rep = self.report
        if not rep or not rep.emails:
            self.set_label("prev_pos", "No emails")
            self.set_label("prev_head", "")
            self.set_text("prev_body", "")
            return
        self.preview_index %= len(rep.emails)
        e = rep.emails[self.preview_index]
        self.set_label("prev_pos", f"Email {self.preview_index + 1} of {len(rep.emails)} (record {e.record_number})")
        atts = [Path(a).name for a in e.attachments]
        if self.settings.attach_pdf:
            atts.insert(0, e.pdf_name + (" (password protected)" if e.pdf_password else ""))
        head = [f"To: {e.to}"]
        if e.cc:
            head.append(f"Cc: {e.cc}")
        if e.bcc:
            head.append(f"Bcc: {e.bcc}")
        if e.reply_to:
            head.append(f"Reply-To: {e.reply_to}")
        head.append(f"Subject: {e.subject}")
        head.append(f"Attachments: {', '.join(atts) if atts else 'none'}")
        self.set_label("prev_head", "\n".join(head))
        self.set_text("prev_body", e.text)

    def move_preview(self, step):
        if self.report and self.report.emails:
            self.preview_index += step
            self.show_preview()

    def open_full_preview(self):
        if not self.report or not self.report.emails:
            self.run_check()
        if not self.report or not self.report.emails:
            return
        import html
        e = self.report.emails[self.preview_index]
        head = "".join(f"<tr><th align=left>{k}</th><td>{html.escape(v)}</td></tr>" for k, v in (
            ("From", self.selected_address()), ("To", e.to), ("Cc", e.cc), ("Bcc", e.bcc), ("Reply-To", e.reply_to),
            ("Subject", e.subject), ("Attachments", ", ".join(Path(a).name for a in e.attachments))) if v)
        banner = (f'<div style="font-family:-apple-system,sans-serif;background:#eef;padding:8px;margin-bottom:12px">'
                  f"<b>Preview of email {self.preview_index + 1} (record {e.record_number})</b><table>{head}</table></div>")
        body = e.html
        body = re.sub(r"(<body[^>]*>)", lambda m: m.group(1) + banner, body, count=1, flags=re.I) \
            if re.search(r"<body", body, re.I) else banner + body
        path = Path(tempfile.gettempdir()) / "mailmerge-mac-preview.html"
        path.write_text(body, encoding="utf-8")
        subprocess.run(["open", str(path)])

    # ---------- page 5: create ----------

    def choose_exclusions(self):
        files = office.pick_files(self.ctx, "Exclusion list (text or CSV file containing email addresses)")
        if files:
            self.set_text("excl_file", files[0])
            self.report = None

    def check_permissions(self):
        self.status("Checking Apple Mail permissions…")
        mailapp.check_permissions()
        state = mailapp.offline_state()
        self.load_accounts()
        self.msg("LibreOffice can control Apple Mail.\n\n"
                 f"Mail is currently {'OFFLINE' if state else 'ONLINE' if state is False else 'in an unknown state'}.",
                 "Permissions OK")

    def request_stop(self):
        self.stop_requested = True
        self.set_label("progress", "Stopping after the current email…")

    def open_output_folder(self):
        folder = self.last_folder or campaign.OUTPUT_ROOT
        folder.mkdir(parents=True, exist_ok=True)
        subprocess.run(["open", str(folder)])

    def insert_field_into(self, target):
        """Ask which merge field, then insert «Field» at the cursor in the `target` box."""
        if self.table is None:
            self.msg("Choose the recipients file on page 1 first, so the fields are known.", "No data", "WARNINGBOX")
            return
        name = self.pick_field()
        if not name:
            return
        box = self.c(target)
        sel, text = box.getSelection(), box.getText()
        if sel.Min == sel.Max == 0 and text:  # cursor never placed in the box: add at the end
            box.setText(text + f"«{name}»")
        else:
            box.insertText(sel, f"«{name}»")
        self.report = None

    def pick_field(self):
        """Small box listing the merge fields. Returns the chosen field name, or None."""
        fields = list(self.table.headers) + ["DATE", "TIME", "RECORD_NUMBER"]
        m = self.smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialogModel", self.ctx)
        m.Width, m.Height, m.Title = 180, 150, "Insert merge field"
        d = self.smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", self.ctx)
        d.setModel(m)
        for kind, name, x, y, w, h, extra in (
                ("FixedText", "p", 6, 4, 168, 10, {"Label": "Select the merge field to insert:"}),
                ("ListBox", "list", 6, 16, 168, 108, {"StringItemList": tuple(fields)}),
                ("Button", "ok", 70, 130, 50, 14, {"Label": "OK", "PushButtonType": 1, "DefaultButton": True}),
                ("Button", "cancel", 124, 130, 50, 14, {"Label": "Cancel", "PushButtonType": 2})):
            cm = m.createInstance(f"com.sun.star.awt.UnoControl{kind}Model")
            cm.PositionX, cm.PositionY, cm.Width, cm.Height = x, y, w, h
            for k, v in extra.items():
                setattr(cm, k, v)
            m.insertByName(name, cm)
        uno.invoke(m.getByName("list"), "setPropertyValue", ("SelectedItems", uno.Any("[]short", (0,))))
        d.createPeer(self.toolkit, self.dlg.getPeer())
        chosen = None
        if d.execute() == 1:
            sel = m.getByName("list").SelectedItems
            chosen = fields[sel[0]] if sel else None
        d.dispose()
        return chosen

    def ask_typed(self, title, prompt, expected):
        """Modal box where the user must type `expected` to continue."""
        m = self.smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialogModel", self.ctx)
        m.Width, m.Height, m.Title = 220, 80, title
        d = self.smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", self.ctx)
        d.setModel(m)
        for kind, name, x, y, w, h, extra in (
                ("FixedText", "p", 6, 6, 208, 30, {"Label": prompt, "MultiLine": True}),
                ("Edit", "e", 6, 40, 208, 12, {}),
                ("Button", "ok", 110, 60, 50, 14, {"Label": "OK", "PushButtonType": 1, "DefaultButton": True}),
                ("Button", "cancel", 164, 60, 50, 14, {"Label": "Cancel", "PushButtonType": 2})):
            cm = m.createInstance(f"com.sun.star.awt.UnoControl{kind}Model")
            cm.PositionX, cm.PositionY, cm.Width, cm.Height = x, y, w, h
            for k, v in extra.items():
                setattr(cm, k, v)
            m.insertByName(name, cm)
        d.createPeer(self.toolkit, self.dlg.getPeer())
        ok = d.execute() == 1 and d.getControl("e").getText().strip() == str(expected)
        d.dispose()
        return ok

    def ready(self):
        """Run the check; return (report, account) if emails can be made, else None (after telling the user)."""
        rep = self.run_check()
        if rep is None:
            return None
        if not rep.ok:
            self.go(4)
            self.msg("The check found errors. Fix them first – they're listed on page 4.", "Not ready", "WARNINGBOX")
            return None
        if not rep.emails:
            self.msg("There are no emails to create.", "Nothing to do", "WARNINGBOX")
            return None
        account = self.selected_account()
        if not account:
            self.go(2)
            self.msg("Choose the From account on page 2 (click Refresh if the list is empty).", "No From account", "WARNINGBOX")
            return None
        return rep, account

    def show_in_mail(self):
        """Open the first email in Apple Mail to view only. Nothing is saved, sent or clicked."""
        if self.running:
            return
        checked = self.ready()
        if not checked:
            return
        rep, account = checked
        e = rep.emails[0]
        s = self.settings
        folder = campaign.campaign_folder(Path(self.doc.getTitle()).stem, "PREVIEW ")
        self.last_folder = folder
        pdf_maker = office.PdfMaker(self.ctx, self.doc, folder) if s.attach_pdf else None
        job = campaign.Campaign(folder, (account[1], account[2]), "export", pdf_maker=pdf_maker, body_text=self.template[1])
        eml = job.write_eml(e, 1, unsent=False)  # view-only: Mail shows no Send button
        job.log(e, "shown in Mail (view only)", eml=eml.name)
        subprocess.run(["open", "-a", "Mail", str(eml)])
        self.status(f"Opened email {e.record_number} in Mail to view. Nothing has been saved or sent.")

    def create(self, mode):
        if self.running:
            return
        checked = self.ready()
        if not checked:
            return
        rep, account = checked
        sender = (account[1], account[2])
        if rep.warnings:
            if self.msg(f"The check found {len(rep.warnings)} warning(s):\n\n" + "\n".join("• " + w for w in rep.warnings[:10])
                        + "\n\nContinue anyway?", "Warnings", "QUERYBOX", BUTTONS_YES_NO) != YES:
                self.go(4)
                return

        emails = rep.emails
        n = len(emails)
        first = emails[0]
        what = {"drafts": f"Create {n} draft(s) in Apple Mail", "export": f"Export {n} .eml file(s)",
                "outbox": f"SEND {n} email(s)"}[mode]
        cc = f"\nCc: {first.cc}" if first.cc else ""
        atts = ([f"{first.pdf_name} (the letter as PDF)"] if self.settings.attach_pdf else []) + list(first.attachments)
        atts = "".join(f"\n  • {a}" for a in atts) or " none"
        summary = (f"{what}\n\nFrom: {self.account_label(account)}\n"
                   f"First email – To: {first.to}{cc}\nSubject: {first.subject}\nAttachments:{atts}\n\n")
        offline = self.settings.require_offline
        summary += {"drafts": "Each email is put in Mail's Drafts. Nothing will be sent.",
                    "export": "Files go to Documents/OpenMailMerge. Nothing is sent.",
                    "outbox": ("With Mail offline, the emails wait in Mail's Outbox. They are sent when you "
                               "choose Mailbox > Take All Accounts Online." if offline else
                               "'Mail must be offline' is unticked, so the emails are sent straight away.")}[mode]
        also = [f"{label}: {settings_check.one_line(value)}" for label, value in
                (("Bcc", first.bcc), ("Reply-To", first.reply_to)) if settings_check.one_line(value)]
        if also:
            summary += "\n\nFirst email – " + "\n".join(also)
        if n > 100 and mode == "outbox":
            summary += ("\n\nNote: many providers limit how many emails you can send per day "
                        "(e.g. about 300 for Outlook.com, 500 for Gmail).")
        if self.msg(summary, "Confirm", "QUERYBOX", BUTTONS_OK_CANCEL) != OK:
            return
        if mode == "outbox" or (mode == "drafts" and n > TYPED_CONFIRM_OVER):
            verb = "send" if mode == "outbox" else "create"
            if not self.ask_typed("Confirm", f"To {verb} {n} email(s), type the number {n} below.", n):
                self.status("Cancelled.")
                return

        s = self.settings
        if mode in ("drafts", "outbox"):
            mailapp.check_permissions()
            while s.require_offline and mailapp.offline_state() is not True:
                if self.msg("Apple Mail is online.\n\nIn Mail choose Mailbox > Take All Accounts Offline, then click OK.",
                            "Take Mail offline", "WARNINGBOX", BUTTONS_OK_CANCEL) != OK:
                    return

        folder = campaign.campaign_folder(Path(self.doc.getTitle()).stem)
        self.last_folder = folder
        pdf_maker = office.PdfMaker(self.ctx, self.doc, folder) if s.attach_pdf else None
        job = campaign.Campaign(folder, sender, mode, s.require_offline, pdf_maker, self.template[1])

        self.running, self.stop_requested = True, False
        for name in ("create", "send", "test_draft", "export", "close"):
            self.c(name).setEnable(False)
        self.c("stop").setEnable(True)

        def progress(i, total, e):
            self.set_label("progress", f"Creating {i} of {total}: {e.to}\n{e.subject}\n\nDon't use the Mac until this finishes.")
            self.pump()

        try:
            done, failed, stopped = job.run(emails, progress, lambda: self.stop_requested)
        finally:
            self.running = False
            for name in ("create", "send", "test_draft", "export", "close"):
                self.c(name).setEnable(True)
            self.c("stop").setEnable(False)

        sent_text = "email(s) waiting in Mail's Outbox." if s.require_offline else "email(s) sent."
        lines = [f"{len(done)} of {n} " + {"drafts": "draft(s) created.", "export": "file(s) exported.",
                                             "outbox": sent_text}[mode]]
        if failed:
            lines.append(f"{len(failed)} failed:")
            lines += [f"• record {e.record_number} ({e.to}): {why}" for e, why in failed[:5]]
        if stopped and len(done) + len(failed) < n:
            lines.append(f"Stopped before the remaining {n - len(done) - len(failed)}.")
        if mode in ("drafts", "outbox") and done:
            try:
                problems = job.verify_senders(done)
                if problems:
                    lines.append("\nWARNING – some emails have the wrong From address:")
                    lines += ["• " + p for p in problems[:5]]
                else:
                    lines.append("All checked: From is " + sender[1] + ".")
            except mailapp.MailError:
                lines.append("(Couldn't check the From address.)")
        if mode == "outbox" and done and s.require_offline:
            lines.append("\nNothing has been sent yet. Check the Outbox in Mail, then choose "
                         "Mailbox > Take All Accounts Online to send. To cancel, delete them from the Outbox first.")
        lines.append(f"\nLog and files: {folder}")
        self.set_label("progress", "\n".join(lines))
        self.status("Finished." if not failed else "Finished with problems – see page 5.")
        self.msg("\n".join(lines), "Finished", "INFOBOX" if not failed else "WARNINGBOX")
        if mode == "export":
            subprocess.run(["open", str(folder / "emails")])

    # ---------- window ----------

    def show(self):
        self.dlg.createPeer(self.toolkit, self.frame.getContainerWindow())
        closer = _Closer(self)
        self.listeners.append(closer)
        self.dlg.addTopWindowListener(closer)
        self.dlg.setVisible(True)
        debug(f"dialog shown: {self.model.Title}; controls={len(self.model.getElementNames())}")
        self.load_data(self.settings.data_file)
        if not os.environ.get("MAILMERGE_MAC_NO_MAIL"):  # set only by the headless install test
            self.load_accounts()

    def close(self):
        if self.running:
            self.request_stop()
            return
        try:
            self.collect()
        except Exception:
            pass
        _open.pop(id(self.doc), None)
        self.dlg.setVisible(False)
        self.dlg.dispose()
