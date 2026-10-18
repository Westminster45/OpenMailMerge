"""Settings saved in a document: were they saved by this user?

Anyone can put MailMergeMacSettings into a document and share it. So when the add-on saves the
settings it adds an HMAC-SHA256 (SIGNATURE_KEY, inside the same JSON) keyed by a random secret that
lives in this user's LibreOffice profile, never in a document. On load, settings without a valid
signature are used without the fields that send copies, redirect replies, attach files or set the PDF
password (RISKY_FIELDS) until the user agrees to them.

Pure Python (no UNO): the dialog asks the user and office finds the profile folder.
"""

import hashlib
import hmac
import json
import os
import secrets
import stat
import unicodedata

SIGNATURE_KEY = "_signature"  # in the saved JSON; not a Settings field, so Settings.from_dict ignores it
RISKY_FIELDS = ("bcc", "cc", "reply_to", "static_attachments", "pdf_password")
ADDRESS_FIELDS = ("cc", "bcc", "reply_to")
KEY_BYTES = 32
# The key's file name in the LibreOffice profile. No extension, so merge.ATTACHMENT_TYPES never lets it be
# attached; is_key_file also catches a link to it with an allowed name such as x.pdf.
KEY_FILE_NAME = "OpenMailMerge-settings-key"
_DOMAIN = b"OpenMailMerge saved settings v1\n"

# Characters that show as blank (or not at all) although str.strip() keeps them.
_FILLERS = frozenset("ᅟᅠ⠀ㅤﾠ")
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
_NONBLOCK = getattr(os, "O_NONBLOCK", 0)


# ---------- signing ----------

def _mac(settings, key):
    """HMAC over every key of settings except the signature itself, in canonical JSON."""
    body = {k: v for k, v in settings.items() if k != SIGNATURE_KEY}
    data = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hmac.new(key, _DOMAIN + data.encode("ascii"), hashlib.sha256).hexdigest()


def sign(settings, key):
    """A copy of settings (a dict) with this user's signature added. Without a key it stays unsigned."""
    out = {k: v for k, v in settings.items() if k != SIGNATURE_KEY}
    if key:
        out[SIGNATURE_KEY] = _mac(out, key)
    return out


def verify(saved, key):
    """True only if saved (as read from a document) carries a valid signature made with key."""
    if not key or not isinstance(saved, dict):
        return False
    sig = saved.get(SIGNATURE_KEY)
    if not isinstance(sig, str) or not sig.isascii():
        return False
    try:
        expected = _mac(saved, key)
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(sig, expected)


# ---------- the per-user key ----------

def _read_key(path):
    fd = os.open(path, os.O_RDONLY | _NOFOLLOW | _CLOEXEC | _NONBLOCK)
    with os.fdopen(fd, "rb") as f:
        st = os.fstat(f.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
            raise ValueError("not a private key file of this user")
        key = f.read(KEY_BYTES + 1)
    if len(key) != KEY_BYTES:
        raise ValueError("key file has the wrong length")
    return key


def load_key(path):
    """This user's secret key, read from path, or created there (mode 0600) on first use.

    Never follows a symlink at path. Returns None if the key can't be read or made, or the file isn't
    a regular file private to this user: settings then count as not saved by this user.
    """
    if not path:
        return None
    path = os.fspath(path)
    for _ in range(2):
        try:
            return _read_key(path)
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            return None
        key = secrets.token_bytes(KEY_BYTES)
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW | _CLOEXEC, 0o600)
        except FileExistsError:
            continue  # made by someone else just now: use theirs
        except OSError:
            return None
        try:
            with os.fdopen(fd, "wb") as f:
                os.fchmod(f.fileno(), 0o600)
                f.write(key)
        except OSError:
            try:
                os.unlink(path)
            except OSError:
                pass
            return None
        return key
    return None


def _folded(name):
    return unicodedata.normalize("NFKC", name).casefold()


def is_key_file(path):
    """True if path, after following any links, is a file named KEY_FILE_NAME (in any case): such a file
    is never attached to an email."""
    try:
        name = os.path.basename(os.path.realpath(path))
    except (OSError, ValueError):
        name = os.path.basename(path)
    return _folded(name) == _folded(KEY_FILE_NAME)


# ---------- loading ----------

def _blank(ch):
    return ch.isspace() or ch in _FILLERS or unicodedata.category(ch) in ("Cc", "Cf", "Zs", "Zl", "Zp")


def strip_blanks(text):
    """text without blank or invisible characters at either end (spaces, NBSP, zero-width, U+2800...)."""
    start, end = 0, len(text)
    while start < end and _blank(text[start]):
        start += 1
    while end > start and _blank(text[end - 1]):
        end -= 1
    return text[start:end]


def one_line(text):
    """text for showing to the user: every run of blank or invisible characters becomes one space."""
    out = []
    for ch in str(text):
        if not _blank(ch):
            out.append(ch)
        elif out and out[-1] != " ":
            out.append(" ")
    return "".join(out).rstrip(" ")


def check_saved(saved, key):
    """Split the settings read from a document into (settings to use now, held back).

    Cc, Bcc and Reply-To are trimmed of blank characters at both ends. If the settings carry a valid
    signature made with key, all of them are used and nothing is held back. Otherwise every field in
    RISKY_FIELDS is taken out, and those with a value are held back for the user to approve.
    """
    if not isinstance(saved, dict):
        return saved, {}
    verified = verify(saved, key)
    use = {k: v for k, v in saved.items() if k != SIGNATURE_KEY}
    for name in ADDRESS_FIELDS:
        if isinstance(use.get(name), str):
            use[name] = strip_blanks(use[name])
    if verified:
        return use, {}
    held = {}
    for name in RISKY_FIELDS:
        if name in use:
            value = use.pop(name)
            if value:
                held[name] = value
    return use, held


def restore(use, held):
    """The settings with the held-back fields put back (after the user agreed)."""
    out = dict(use)
    out.update(held)
    return out


def describe(held):
    """Lines listing the held-back settings for the user. A PDF password is never shown."""
    lines = []
    for name, label in (("bcc", "Also send a copy to (Bcc): "), ("cc", "Copy to (Cc): "),
                        ("reply_to", "Replies go to: ")):
        if name in held:
            lines.append(label + one_line(held[name]))
    if "static_attachments" in held:
        files = held["static_attachments"]
        lines.append("Files attached to every email:")
        lines += ["  • " + one_line(f) for f in (files if isinstance(files, list) else [files])]
    if "pdf_password" in held:
        lines.append("PDF password: set")
    return lines


def leave_blank_note(held):
    """An extra line for the prompt, next to its buttons: what leaving the settings blank also means.
    Only when a PDF password is held back; otherwise ""."""
    return "If you leave these blank, the PDFs won't have a password." if "pdf_password" in held else ""
