"""OpenMailMerge: a LibreOffice Writer mail-merge extension for macOS.

Pure-Python modules (no UNO): template, data, message, merge, preflight, mailapp.
UNO modules: office (document export, spreadsheets), dialog (user interface).
"""

VERSION = "0.1.10"


def debug(message):
    """Append to the file named by MAILMERGE_MAC_DEBUG_LOG, if set (used by tests and support)."""
    import os
    path = os.environ.get("MAILMERGE_MAC_DEBUG_LOG")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(str(message) + "\n")
