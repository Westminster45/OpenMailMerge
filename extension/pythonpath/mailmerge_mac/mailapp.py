"""Apple Mail automation.

Each email is written as a .eml file (From, To, Cc, Bcc, Reply-To, the formatted body, inline images
and attachments). Mail is handed the emails unchanged, so the body is never re-created by script
(Mail wraps script-set bodies as quoted text):
  1. All emails of a run go into one mailbox file, which Mail imports in one go (no windows). The
     import is renamed "OpenMailMerge - <date> <time>" under On My Mac.
  2. Create drafts: each email is moved into the From account's Drafts. Nothing is sent.
     Send: each email is redirected to its To / Cc / Bcc and sent (with "Mail must be offline"
     ticked it waits in the Outbox). Recipients using Apple Mail see Resent-From / Resent-To lines.
  3. The email is looked for in Drafts / Outbox / Sent (by its Message-ID) to confirm it landed.

Safety rule: with "Mail must be offline" ticked, Mail must report all accounts offline before each
email. Needs macOS permissions for LibreOffice: Automation (Mail, System Events) and Accessibility
(only to read Mail's offline state).
"""

import subprocess
import time
from pathlib import Path


class MailError(Exception):
    pass


def osa(script, timeout=30, args=()):
    """Run AppleScript. Text is passed as arguments (argv), never pasted into the script source."""
    try:
        # Bytes in, bytes out: LibreOffice's Python may run with an ASCII locale, so never rely on it.
        cmd = ["osascript", "-e", script, *args]
        p = subprocess.run([c.encode("utf-8") for c in cmd], capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise MailError("Apple Mail didn't respond in time.")
    if p.returncode != 0:
        raise MailError(p.stderr.decode("utf-8", "replace").strip())
    return p.stdout.decode("utf-8", "replace").strip()


def explain(err):
    """Turn macOS permission errors into instructions."""
    text = str(err)
    if "-1743" in text or "Not authorised" in text or "Not authorized" in text:
        return ("macOS blocked LibreOffice from controlling Mail or System Events.\n"
                "System Settings > Privacy & Security > Automation > LibreOffice: turn on Mail and System Events.")
    if "assistive" in text or "-1719" in text or "-25211" in text:
        return ("LibreOffice needs Accessibility permission to click Mail's menus.\n"
                "System Settings > Privacy & Security > Accessibility: add and turn on LibreOffice, then restart LibreOffice.")
    return text


def enabled_accounts():
    """[(account name, full name, address)] for accounts switched on in Mail."""
    osa('tell application id "com.apple.mail" to launch')  # by bundle id: on some Macs Mail's terms (account…) don't compile when it's named
    out = osa(
        'tell application id "com.apple.mail"\nset r to {}\n'
        "repeat with a in (every account whose enabled is true)\n"
        "set fn to full name of a\nif fn is missing value then set fn to \"\"\n"
        'repeat with e in (get email addresses of a)\nset end of r to (name of a) & tab & fn & tab & (contents of e)\nend repeat\n'
        "end repeat\n"
        'set AppleScript\'s text item delimiters to linefeed\nreturn r as text\nend tell'
    )
    return [tuple(line.split("\t", 2)) for line in out.splitlines() if line.count("\t") == 2]


def offline_state():
    """True if Mail reports all accounts offline, False if online, None if unknown."""
    out = osa(
        'tell application "System Events" to tell process "Mail"\n'
        "set r to {}\n"
        'repeat with mi in menu items of menu "Mailbox" of menu bar 1\n'
        "set n to name of mi\n"
        'if n is not missing value and n starts with "Take All Accounts" then set end of r to n & "=" & (enabled of mi)\n'
        "end repeat\n"
        'set AppleScript\'s text item delimiters to ";"\nreturn r as text\nend tell'
    )
    items = dict(p.split("=", 1) for p in out.split(";") if "=" in p)
    if items.get("Take All Accounts Online") == "true" and items.get("Take All Accounts Offline") == "false":
        return True
    if items.get("Take All Accounts Offline") == "true":
        return False
    return None


def check_permissions():
    """Raise MailError with instructions if Mail can't be automated."""
    try:
        osa('tell application id "com.apple.mail" to launch')
        enabled_accounts()
        offline_state()
    except MailError as e:
        raise MailError(explain(e))


# ---------- the email ----------

def read_eml(eml_path):
    """What Mail needs from a MailMerge .eml: {message_id, sender_address, to, cc, bcc}
    (addresses as [(name, address)])."""
    from email import policy
    from email.parser import BytesParser
    from email.utils import getaddresses, parseaddr

    msg = BytesParser(policy=policy.default).parsebytes(Path(eml_path).read_bytes())

    def addrs(name):
        return [(n, a) for n, a in getaddresses([str(v) for v in msg.get_all(name, [])]) if a]

    return {"message_id": str(msg["Message-ID"] or "").strip().strip("<>"),
            "sender_address": parseaddr(str(msg["From"] or ""))[1],
            "to": addrs("To"), "cc": addrs("Cc"), "bcc": addrs("Bcc")}


def write_mbox(eml_paths, mbox_dir, strip_bcc=False):
    """Write the emails as a Mail-importable mailbox: <mbox_dir>/mbox. X-Unsent is dropped; with
    strip_bcc the Bcc header is dropped too (a redirect sends the headers as they are)."""
    import mailbox
    from email import policy
    from email.parser import BytesParser

    mbox_dir = Path(mbox_dir)
    mbox_dir.mkdir(parents=True, exist_ok=True)
    box = mailbox.mbox(str(mbox_dir / "mbox"))
    try:
        for path in eml_paths:
            msg = BytesParser(policy=policy.default).parsebytes(Path(path).read_bytes())
            del msg["X-Unsent"]
            if strip_bcc:
                del msg["Bcc"]
            box.add(mailbox.mboxMessage(msg.as_bytes()))
        box.flush()
    finally:
        box.close()
    return mbox_dir


IMPORT = """on run argv
	set {boxPath, innerName, topName, expected} to argv
	set expected to expected as integer
	tell application id "com.apple.mail"
		set existing to name of every mailbox
		import Mail mailbox at (POSIX file boxPath)
		set top to missing value
		repeat 240 times
			repeat with mb in every mailbox
				if (name of mb) is not in existing then
					try
						if (count of messages of mailbox innerName of mb) = expected then set top to contents of mb
					end try
				end if
			end repeat
			if top is not missing value then exit repeat
			delay 0.5
		end repeat
		if top is missing value then error "Mail didn't import the emails."
		set newName to topName
		set n to 1
		repeat while newName is in (name of every mailbox)
			set n to n + 1
			set newName to topName & " (" & n & ")"
		end repeat
		set name of top to newName
	end tell
	return newName
end run
"""

DELIVER = """on run argv
	set {topName, innerName, msgId, theAction, fromAddr, toList, ccList, bccList} to argv
	set AppleScript's text item delimiters to tab
	tell application id "com.apple.mail"
		set ms to (messages of mailbox innerName of mailbox topName whose message id is msgId)
		if (count of ms) is 0 then error "Couldn't find the email in Mail's mailbox " & topName & "."
		set m to item 1 of ms
		if theAction is "draft" then
			set acct to missing value
			repeat with a in accounts
				if (email addresses of a) contains fromAddr then set acct to contents of a
			end repeat
			if acct is missing value then error "No Mail account has the address " & fromAddr & "."
			move m to mailbox "Drafts" of acct
		else
			set r to redirect m without opening window
			tell r
				repeat with p in paragraphs of toList
					set p to contents of p
					if length of p > 0 then make new to recipient at end of to recipients with properties {address:text item 2 of p}
				end repeat
				repeat with p in paragraphs of ccList
					set p to contents of p
					if length of p > 0 then make new cc recipient at end of cc recipients with properties {address:text item 2 of p}
				end repeat
				repeat with p in paragraphs of bccList
					set p to contents of p
					if length of p > 0 then make new bcc recipient at end of bcc recipients with properties {address:text item 2 of p}
				end repeat
			end tell
			if not (send r) then error "Mail didn't send the email."
		end if
	end tell
	return "ok"
end run
"""


def _lines(pairs):
    return "\n".join(f"{n.replace(chr(9), ' ')}\t{a}" for n, a in pairs)


def import_batch(eml_paths, folder, inner_name, strip_bcc=False, when=None):
    """Import the emails into Mail in one go. Returns (top mailbox name, inner mailbox name):
    'MailMerge - <date> <time>' (or '… (2)') under On My Mac, holding the mailbox inner_name."""
    from datetime import datetime

    mbox_dir = write_mbox(eml_paths, Path(folder) / f"{inner_name}.mbox", strip_bcc)
    top = "OpenMailMerge - " + (when or datetime.now()).strftime("%Y-%m-%d %H%M")
    top = osa(IMPORT, timeout=180, args=[str(mbox_dir), inner_name, top, str(len(eml_paths))])
    return top, inner_name


def create_draft(eml_path, subject, source, require_offline=True):
    """Put the imported email into the From account's Drafts. Nothing is sent."""
    create_message(eml_path, subject, source, "draft", require_offline)


def create_message(eml_path, subject, source, action="draft", require_offline=True):
    """For an email already imported by import_batch (source = its return value):
      action 'draft':  move it into the From account's Drafts. Nothing is sent.
      action 'outbox': redirect it to its To / Cc / Bcc and send it (offline: it waits in the
                       Outbox; online: it is sent).
    Afterwards the email is looked for in Drafts / Outbox / Sent by its Message-ID.
    """
    e = read_eml(eml_path)
    if require_offline and offline_state() is not True:
        raise MailError("Stopped for safety: Mail is online. Choose Mailbox > Take All Accounts Offline in Mail, then continue.")
    if action == "outbox":
        boxes = ["outbox"] if require_offline else ["outbox", "sent mailbox"]
    else:
        boxes = ["drafts mailbox"]

    top, inner = source
    osa(DELIVER, timeout=120, args=[top, inner, e["message_id"], action, e["sender_address"],
                                    _lines(e["to"]), _lines(e["cc"]), _lines(e["bcc"])])

    end = time.time() + (10 if require_offline or action != "outbox" else 60)
    while time.time() < end:
        if sum(count_by_id(e["message_id"], b) for b in boxes) > 0:
            return
        time.sleep(0.5)
    where = ("the Outbox" if require_offline else "the Outbox or Sent") if action == "outbox" else "Drafts"
    raise MailError(f"'{subject}' didn't appear in {where}. Nothing more was done; check Mail before continuing.")


MAILBOXES = {"drafts mailbox", "outbox", "sent mailbox"}


def count_by_id(message_id, mailbox="drafts mailbox"):
    """How many messages in Mail's Drafts / Outbox / Sent have this Message-ID (without <>)."""
    assert mailbox in MAILBOXES
    out = osa('on run argv\ntell application id "com.apple.mail" to '
              f"return count (messages of {mailbox} whose message id is item 1 of argv)\nend run",
              timeout=60, args=[message_id])
    return int(out or 0)


def senders_by_id(message_id, mailbox="drafts mailbox"):
    """Senders of the messages in Mail's Drafts / Outbox / Sent with this Message-ID (without <>)."""
    assert mailbox in MAILBOXES
    out = osa('on run argv\ntell application id "com.apple.mail"\n'
              f"set r to sender of (messages of {mailbox} whose message id is item 1 of argv)\n"
              "end tell\nset AppleScript's text item delimiters to linefeed\nreturn r as text\nend run",
              timeout=60, args=[message_id])
    return [line for line in out.splitlines() if line]


def drafts_matching(subjects, mailbox="drafts mailbox"):
    """[(subject, sender)] for messages in Mail's Drafts / Outbox / Sent whose subject is in subjects
    (Mail does the search, one subject at a time)."""
    assert mailbox in MAILBOXES
    found = []
    for subject in sorted(set(subjects)):
        out = osa('on run argv\ntell application id "com.apple.mail"\n'
                  f"set r to sender of (messages of {mailbox} whose subject is item 1 of argv)\n"
                  "end tell\nset AppleScript's text item delimiters to linefeed\nreturn r as text\nend run",
                  timeout=60, args=[subject])
        found += [(subject, sender) for sender in out.splitlines() if sender]
    return found


def outbox_matching(subjects):
    return drafts_matching(subjects, "outbox")
