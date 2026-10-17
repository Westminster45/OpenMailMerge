"""UNO component: the OpenMailMerge menu command opens the OpenMailMerge window for the current Writer document."""

import os
import sys
import traceback

# Make the extension's own modules importable (LibreOffice doesn't always add pythonpath/ itself).
_PYTHONPATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pythonpath")
if _PYTHONPATH not in sys.path:
    sys.path.insert(0, _PYTHONPATH)

import uno  # noqa: E402
import unohelper  # noqa: E402
from com.sun.star.task import XJobExecutor  # noqa: E402

IMPLEMENTATION = "io.github.mailmergemac.Job"


def _debug(message):
    path = os.environ.get("MAILMERGE_MAC_DEBUG_LOG")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(message + "\n")


class MailMergeJob(unohelper.Base, XJobExecutor):
    def __init__(self, ctx):
        self.ctx = ctx

    def trigger(self, args):
        if str(args).startswith("test:"):  # headless install test: "test:<debug log path>"
            os.environ["MAILMERGE_MAC_DEBUG_LOG"] = str(args)[5:]
            os.environ["MAILMERGE_MAC_NO_MAIL"] = "1"
        desktop = self.ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", self.ctx)
        doc = desktop.getCurrentComponent()
        frame = desktop.getCurrentFrame()
        try:
            _debug(f"trigger: doc={doc is not None}")
            if doc is None or not doc.supportsService("com.sun.star.text.TextDocument"):
                self.message(frame, "Open the Writer document you want to use as the email, then choose OpenMailMerge again.")
                return
            from mailmerge_mac import dialog
            dialog.open_dialog(self.ctx, doc, frame)
        except Exception:
            _debug("trigger failed:\n" + traceback.format_exc())
            self.message(frame, "OpenMailMerge couldn't start:\n\n" + traceback.format_exc()[-1500:])

    def message(self, frame, text):
        toolkit = self.ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.Toolkit", self.ctx)
        parent = frame.getContainerWindow() if frame else None
        box = toolkit.createMessageBox(parent, uno.Enum("com.sun.star.awt.MessageBoxType", "INFOBOX"), 1, "OpenMailMerge", text)
        box.execute()
        box.dispose()


g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(MailMergeJob, IMPLEMENTATION, ("com.sun.star.task.Job",))
