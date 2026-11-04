# Release notes

## Unreleased

**Changes**
- A ? button next to the PDF password explains what the password does and doesn't protect against.
- A line break in the data used in the subject becomes a space, so that email is no longer stopped with an error.
- In log.csv, a value starting with =, +, -, @ or a tab is given a leading ' so a spreadsheet shows it as text instead of running it as a formula. The emails themselves are unchanged.
- After Send… with "Mail must be offline" ticked, the Finished message warns that Mail sometimes reconnects on its own, and suggests turning off Wi-Fi until you've checked the Outbox.

**Bug fixes**
- A CSV file that is neither UTF-8 nor Windows text now gives a clear message asking for CSV UTF-8, instead of an internal error.

**Security**
- Scripts for Apple Mail are now run from a temporary file rather than with osascript -e, so text from the data (such as a subject starting with "-e") can never be read as script.

## 0.1.12

**Bug fixes**
- Fixed the error message ("Expected class name but found identifier") still appearing on some Macs when OpenMailMerge was opened while Apple Mail was not running.
- The check that drafts use the right From address no longer gets confused by other drafts with the same or an empty subject.

**Changes**
- These no longer stop the merge. You get a warning and can continue:
  - an empty subject
  - a merge field that doesn't match any column, or « » / {{ }} left in the text
  - an attachment that can't be found (the email goes without it)
  - a PDF password that is empty for some recipients (their PDF has no password)

## 0.1.11

**Bug fix**
- Fixed an error message ("Expected class name but found identifier") when OpenMailMerge was opened while Apple Mail was not running. Mail is now started automatically.

**Security fixes** (updating is recommended)
- Merge settings are no longer included in the emails that are sent.
- Images in an email now come only from the letter itself.
- Files attached to every email are now limited to the same file types as per-recipient attachments.
- Settings saved in a document on another computer, by someone else or by an older version of OpenMailMerge are now shown for you to confirm before any Bcc, Cc, Reply-To, attachments or PDF password are used. Documents you save yourself open as before.
- You now get a warning when Cc, Bcc or Reply-To contains a typed address rather than only merge fields. The last check before sending also shows Bcc, Reply-To and the attachments.
