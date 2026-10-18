# OpenMailMerge

Mail merge from LibreOffice Writer to Apple Mail on macOS.

Write your letter in Writer and choose a list of recipients. OpenMailMerge turns the letter into one personalised email per person, sent from an account you already use in Apple Mail.

## Features

- Recipients come from a CSV, Excel, Numbers or Calc file.
- Merge fields work in the letter, subject, Cc, Bcc, Reply-To, PDF name and PDF password. Write them as `«First_Name»` or `{{First_Name}}`. `DATE`, `TIME` and `RECORD_NUMBER` are built in.
- The email keeps the letter's formatting: fonts, colours, lists and links.
- Attachments can go to everyone or be set per recipient. The letter itself can be attached as a PDF, optionally password-protected. Attachments (fixed and per-recipient) are limited to documents, text, HTML, CSV, JSON, zip, spreadsheets, presentations, images, audio and video; other file types (such as code, keys and files with no extension) are blocked.
- Every email is checked before anything is created: invalid or duplicate addresses, empty or unknown fields, and missing attachments.
- **Show in Mail** previews the first email.
- **Create drafts** puts every email in your account's Drafts folder for you to review and send. Nothing is sent.
- **Send** sends every email. With "Mail must be offline" ticked, the emails wait in Mail's Outbox until you take Mail online.
- **Export .eml only** saves the emails as files.
- Large batches and every Send need a typed confirmation. Every email is logged in `~/Documents/OpenMailMerge`.

It works with any account enabled in Apple Mail, such as iCloud, Gmail or Outlook.com. OpenMailMerge never signs in or asks for passwords.

## How it works

Each email is built as a standard `.eml` file. All emails in a run are imported into Mail in one go, as an "OpenMailMerge - date" mailbox under On My Mac; delete it when you're done.

- **Create drafts:** each email is moved into the From account's Drafts.
- **Send:** each email is redirected to its recipients.

Either way, Mail sends the email exactly as it was built. Mail never re-creates the body, so the formatting survives and the body isn't shown as quoted text.

## Requirements

- macOS and LibreOffice 7.0 or later.
- Apple Mail with at least one account set up.
- On first use, macOS asks you to allow LibreOffice to control Mail and System Events, and to give it Accessibility access. Accessibility is used only to read Mail's offline state.

## Install

1. Download `OpenMailMerge.oxt` from [Releases](../../releases).
2. In LibreOffice, choose **Tools › Extensions › Add…** and pick the downloaded file.
3. In a Writer document, choose **Tools › Add-Ons › Mail Merge to Apple Mail…**, or click the envelope button on the OpenMailMerge toolbar.

## Build from source

```sh
python3 -m unittest discover -s tests   # unit tests, no LibreOffice needed
./build.sh                              # runs the tests, then writes dist/OpenMailMerge.oxt
```

`dev/` holds headless LibreOffice checks and a few Mail inspection scripts. `FEATURE_MAP.md` compares the feature set with MapiLab's Mail Merge Toolkit, which inspired this project. OpenMailMerge is not affiliated with MapiLab, Apple or Microsoft.

## Licence

[Mozilla Public License 2.0](LICENSE)
