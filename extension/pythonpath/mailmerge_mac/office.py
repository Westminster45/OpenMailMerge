"""LibreOffice (UNO) side: document export, spreadsheets, PDFs, settings, file pickers."""

import base64
import json
import mimetypes
import re
import tempfile
from pathlib import Path

import uno
from com.sun.star.beans import PropertyValue

from . import data, template

SETTINGS_KEY = "MailMergeMacSettings"
REMOVEABLE = 128
IMG_SRC_RE = re.compile(r"""(<img\b[^>]*?\bsrc=)(["'])(?!data:|https?:|cid:)([^"']+)\2""", re.I)


def props(**kw):
    return tuple(PropertyValue(Name=k, Value=v) for k, v in kw.items())


def url(path):
    return uno.systemPathToFileUrl(str(Path(path).resolve()))


def path_from_url(u):
    return uno.fileUrlToSystemPath(u)


def store(doc, path, filter_name, filter_options=None, filter_data=None):
    args = [PropertyValue(Name="FilterName", Value=filter_name), PropertyValue(Name="Overwrite", Value=True)]
    if filter_options:
        args.append(PropertyValue(Name="FilterOptions", Value=filter_options))
    if filter_data:
        args.append(PropertyValue(Name="FilterData",
                                  Value=uno.Any("[]com.sun.star.beans.PropertyValue", props(**filter_data))))
    uno.invoke(doc, "storeToURL", (url(path), tuple(args)))


def load_hidden(ctx, path, read_only=True):
    desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    return desktop.loadComponentFromURL(url(path), "_blank", 0, props(Hidden=True, ReadOnly=read_only))


# ---------- recipient data ----------

def read_table(ctx, path):
    if not data.is_spreadsheet(path):
        return data.read_csv(path)
    doc = load_hidden(ctx, path)
    try:
        sheet = doc.Sheets.getByIndex(0)
        cursor = sheet.createCursor()
        cursor.gotoEndOfUsedArea(False)
        end = cursor.RangeAddress
        matrix = [[sheet.getCellByPosition(c, r).getString() for c in range(end.EndColumn + 1)]
                  for r in range(end.EndRow + 1)]
    finally:
        doc.close(True)
    return data.from_matrix(matrix, str(path))


# ---------- document as email template ----------

def export_template(doc):
    """The document as (html, text), fields still unrendered. Images are embedded as data: URIs."""
    with tempfile.TemporaryDirectory() as d:
        html_path, text_path = Path(d) / "body.html", Path(d) / "body.txt"
        store(doc, html_path, "HTML (StarWriter)", "EmbedImages")
        store(doc, text_path, "Text (encoded)", "UTF8,LF,,,")
        html = html_path.read_text(encoding="utf-8", errors="replace")
        text = text_path.read_text(encoding="utf-8", errors="replace").lstrip("﻿")

        def inline(m):  # images LibreOffice wrote as separate files
            f = (Path(d) / m.group(3)).resolve()
            if not f.is_file():
                return m.group(0)
            mime = mimetypes.guess_type(f.name)[0] or "image/png"
            b64 = base64.b64encode(f.read_bytes()).decode()
            return f"{m.group(1)}{m.group(2)}data:{mime};base64,{b64}{m.group(2)}"

        html = IMG_SRC_RE.sub(inline, html)
    return html, text


def insert_field(doc, name):
    vc = doc.getCurrentController().getViewCursor()
    vc.getText().insertString(vc, template.marker(name), False)


# ---------- per-recipient PDF ----------

class PdfMaker:
    """Makes one merged PDF per recipient from a hidden copy of the document."""

    def __init__(self, ctx, doc, workdir):
        self.ctx = ctx
        self.template_path = Path(workdir) / "template.odt"
        store(doc, self.template_path, "writer8")

    def make(self, email, body_text, out_path, now=None):
        copy = load_hidden(self.ctx, self.template_path, read_only=False)
        try:
            seen = set()
            for m in template.FIELD_RE.finditer(body_text):
                exact = m.group(0)
                if exact in seen:
                    continue
                seen.add(exact)
                name = (m.group(1) or m.group(2)).strip()
                value, found = template.lookup(name, email.row, email.record_number, now)
                if not found:
                    continue
                rd = copy.createReplaceDescriptor()
                rd.SearchString = exact
                rd.ReplaceString = str(value)
                rd.SearchRegularExpression = False
                copy.replaceAll(rd)
            fd = {"ExportFormFields": False}
            if email.pdf_password:
                fd.update(EncryptFile=True, DocumentOpenPassword=email.pdf_password)
            store(copy, out_path, "writer_pdf_Export", filter_data=fd)
        finally:
            copy.close(True)
        return out_path


# ---------- settings stored in the document ----------

def load_settings(doc):
    udp = doc.getDocumentProperties().getUserDefinedProperties()
    if udp.getPropertySetInfo().hasPropertyByName(SETTINGS_KEY):
        try:
            return json.loads(udp.getPropertyValue(SETTINGS_KEY))
        except ValueError:
            return {}
    return {}


def save_settings(doc, settings_dict):
    udp = doc.getDocumentProperties().getUserDefinedProperties()
    value = json.dumps(settings_dict)
    if udp.getPropertySetInfo().hasPropertyByName(SETTINGS_KEY):
        if udp.getPropertyValue(SETTINGS_KEY) != value:
            udp.setPropertyValue(SETTINGS_KEY, value)
    else:
        udp.addProperty(SETTINGS_KEY, REMOVEABLE, value)


# ---------- pickers ----------

def pick_files(ctx, title, filters=(), multi=False):
    fp = ctx.ServiceManager.createInstanceWithContext("com.sun.star.ui.dialogs.FilePicker", ctx)
    fp.initialize((0,))  # FILEOPEN_SIMPLE
    fp.setTitle(title)
    for name, pattern in filters:
        fp.appendFilter(name, pattern)
    fp.setMultiSelectionMode(multi)
    if fp.execute() != 1:
        return []
    return [path_from_url(u) for u in fp.getSelectedFiles()]
