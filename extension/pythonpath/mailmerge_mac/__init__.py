"""OpenMailMerge: a LibreOffice Writer mail-merge extension for macOS.

Pure-Python modules (no UNO): template, data, message, merge, preflight, mailapp.
UNO modules: office (document export, spreadsheets), dialog (user interface).
"""

VERSION = "0.1.12"


def debug(message):
    """Append to the file named by MAILMERGE_MAC_DEBUG_LOG, if set (used by tests and support)."""
    import os
    path = os.environ.get("MAILMERGE_MAC_DEBUG_LOG")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(str(message) + "\n")


def release_notes():
    """CHANGELOG.md as plain text for the About window. build.sh puts it at the root of the .oxt;
    when running from the source folder it is one level further up."""
    from pathlib import Path
    here = Path(__file__).resolve().parents
    for path in (here[2] / "CHANGELOG.md", here[3] / "CHANGELOG.md"):
        if path.is_file():
            return format_release_notes(path.read_text(encoding="utf-8"))
    return "The release notes aren't included in this copy of OpenMailMerge."


def format_release_notes(markdown):
    """Strip the Markdown markup the changelog uses, so it reads cleanly in a plain text box."""
    lines = []
    for line in markdown.splitlines():
        if line.startswith("# "):
            continue
        line = line.replace("**", "")
        if line.startswith("## "):
            line = line[3:]
        elif line.startswith("  - "):
            line = "      – " + line[4:]
        elif line.startswith("- "):
            line = "  • " + line[2:]
        lines.append(line)
    return "\n".join(lines).strip() + "\n"
