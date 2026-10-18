# Release notes

## 0.1.11

**Bug fix**
- Fixed an error message ("Expected class name but found identifier") when OpenMailMerge was opened while Apple Mail was not running. Mail is now started automatically.

**Security fixes** (updating is recommended)
- Merge settings are no longer included in the emails that are sent.
- Images in an email now come only from the letter itself.
- Files attached to every email are now limited to the same file types as per-recipient attachments.
- Settings saved in a document on another computer, by someone else or by an older version of OpenMailMerge are now shown for you to confirm before any Bcc, Cc, Reply-To, attachments or PDF password are used. Documents you save yourself open as before.
- You now get a warning when Cc, Bcc or Reply-To contains a typed address rather than only merge fields. The last check before sending also shows Bcc, Reply-To and the attachments.
