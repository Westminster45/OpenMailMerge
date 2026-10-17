"""Building .eml files: HTML + plain text body, inline images, attachments."""

import base64
import mimetypes
import re
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from pathlib import Path

ADDRESS_RE = re.compile(r"^[^@\s<>(),;:\"]+@[^@\s<>(),;:\"]+\.[^@\s<>(),;:\"]+$")
DATA_IMG_RE = re.compile(r"""(<img\b[^>]*?\bsrc=)(["'])data:(image/[\w.+-]+);base64,([A-Za-z0-9+/=\s]+)\2""", re.I)


TOKEN_RE = re.compile(r'(?:"[^"]*"|[^,;])+')


def split_addresses(text):
    """'a@x.com; "Smith, Bob" <b@y.com>' -> [('', 'a@x.com'), ('Smith, Bob', 'b@y.com')].

    Addresses are taken exactly as typed (never altered), so invalid ones stay visible to the check.
    """
    pairs = []
    for token in TOKEN_RE.findall(text or ""):
        token = token.strip()
        if not token:
            continue
        m = re.match(r'^(.*?)<([^<>]*)>\s*$', token)
        if m:
            pairs.append((m.group(1).strip().strip('"').strip(), m.group(2).strip()))
        else:
            pairs.append(("", token))
    return pairs


def valid_address(address):
    return bool(ADDRESS_RE.match(address or ""))


def join_addresses(pairs):
    return ", ".join(formataddr(p) if p[0] else p[1] for p in pairs)


def build(sender, to, subject, html_body, text_body, cc="", bcc="", reply_to="",
          attachments=(), importance=None, unsent=True):
    """Return an EmailMessage. sender is (name, address); to/cc/bcc/reply_to are address strings.

    unsent=True adds X-Unsent so Mail opens it ready to send; False makes Mail show it view-only.
    """
    msg = EmailMessage()
    msg["From"] = formataddr(sender) if sender[0] else sender[1]
    msg["To"] = join_addresses(split_addresses(to))
    if split_addresses(cc):
        msg["Cc"] = join_addresses(split_addresses(cc))
    if split_addresses(bcc):
        msg["Bcc"] = join_addresses(split_addresses(bcc))
    if split_addresses(reply_to):
        msg["Reply-To"] = join_addresses(split_addresses(reply_to))
    msg["Subject"] = subject
    if unsent:
        msg["X-Unsent"] = "1"
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="mailmerge-mac.local")
    if importance in ("High", "Low"):
        msg["Importance"] = importance
        msg["X-Priority"] = "1" if importance == "High" else "5"

    msg.set_content(text_body or "")
    if html_body:
        images = []

        def to_cid(m):
            cid = make_msgid(domain="mailmerge-mac.local")
            images.append((cid, m.group(3), base64.b64decode(re.sub(r"\s", "", m.group(4)))))
            return f"{m.group(1)}{m.group(2)}cid:{cid[1:-1]}{m.group(2)}"

        html_body = DATA_IMG_RE.sub(to_cid, html_body)
        msg.add_alternative(html_body, subtype="html")
        html_part = msg.get_payload()[1]
        for cid, mime, data in images:
            maintype, subtype = mime.split("/", 1)
            html_part.add_related(data, maintype=maintype, subtype=subtype, cid=cid)

    for path in attachments:
        path = Path(path)
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        maintype, subtype = mime.split("/", 1)
        msg.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name)
    return msg


def text_to_html(text):
    """Plain text (e.g. a body typed in the dialog) to simple HTML paragraphs."""
    import html as _html
    paras = [p for p in re.split(r"\n\s*\n", text or "")]
    return "".join(f"<p>{_html.escape(p).replace(chr(10), '<br>')}</p>" for p in paras)
