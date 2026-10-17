# Feature Map: MapiLab Mail Merge Toolkit → LibreOffice Extension

Reference product: **MapiLab Mail Merge Toolkit (MMT) v7.5** (June 2026), an add-in for Word, Publisher and Outlook on Windows.
Source: https://www.mapilab.com/outlook/mail_merge/ (product page, technical details, version history, video tours, blog posts and 13 screenshots, all reviewed 16 Oct 2026).

Goal: **MailMerge for Outlook Mac**, a free LibreOffice Writer extension for macOS. It does everything MMT does, hands each message to the Outlook app to send (or to Drafts only), and has stronger safeguards against accidental sends.

Legend for LibreOffice (LO) column: **Have** = built-in LO does it · **Partial** = limited · **Missing** = not available · *verify* = still to confirm. LO claims were checked against the dialog definitions in the installed **LibreOffice 26.8.0.3**.

---

## 1. How MMT works (architecture)

- Runs **locally** as an Office add-in. No vendor servers; only licence checks and update notices go to MapiLab (can be turned off).
- Reads the data source already attached to the Word/Publisher merge document.
- Builds **one message per To recipient**, then places it in the Outlook **Outbox** (or **Drafts**). Outlook does the actual sending, so Outlook must stay open for scheduled or throttled sends.
- Settings can be saved and reused as named **configuration items** (v7.5), including attachment passwords.
- Interface and help are in English and German. Logging has several levels. Binaries are code-signed.
- Windows only. **Not compatible with Office for Mac.**
- Trial: 30 days, capped at 50 recipients. Licence: subscription per user. Standard and Professional editions (see §8).

## 2. Entry points

| Where | What |
|---|---|
| Word/Publisher **Mailings** ribbon → group "Mail Merge Toolkit" | **Record Counter** (first / previous / record number / next / last), **Merge & Send** (opens main dialog), **Use SharePoint list as Data Source**, **Help** menu (Registration, etc.) |
| Word Step-by-Step Mail Merge Wizard, final step "Complete the merge" | Extra link **Mail Merge Toolkit** under Print… / Edit individual letters… |
| Windows Start menu | Startup dialog with links to open Word or Publisher (v7.4) |
| Outlook Contacts | Start a merge from selected contacts; opens an existing or new document |
| Configuration selector (v7.5) | Pick a saved settings set before the dialog opens |

## 3. Main dialog: six tabs

Footer on every tab: **"Send N messages"** button (N is a live count of messages to be created), **Cancel**, **Help**.

### 3.1 Message settings

| Control | Options / behaviour |
|---|---|
| Recipients → **To** | Dropdown of data-source fields (e.g. `Email`). Multiple addresses in a field are separated with `;`. |
| **Cc**, **Bcc** | Free text, merge fields (`FIELD"Secondary_Email"`) or both. The `…` button opens the field picker. |
| **Subject** | Free text mixed with merge fields, e.g. `Invoice FIELD"Invoice_Number" for FIELD"Company"`. |
| ☑ **Warn about missing 'To:' recipient** | Safety check for rows with an empty address field. |
| **Insert merge field** sub-dialog | Dropdown of all data columns plus dynamic macros (see §5). |

Known pitfall (FAQ): Cc/Bcc are added to *every* message, so a Cc recipient gets one copy per row.

### 3.2 Attachments

| Control | Options / behaviour |
|---|---|
| **Insert file…** | Static file attached to every message (local or UNC path). |
| **Insert file from merge field…** | Per-recipient file from a data column of full paths (e.g. `C:\Attachments\Payslip-Alex.xlsx`). |
| **Remove attachment** | Removes the selected entry. |
| Attachment list | Columns: checkbox, Attachment name, Path, Size (shows "depends on merge field value" for field-based entries). |
| Wildcards / file masks | e.g. `C:\Folder\*.PDF` attaches every match. Multiple columns allow several files per row. |
| **Compress options** (v7.3) | ☑ Send selected attachments as **ZIP file**; **Custom name** (with merge fields) + `.zip`; **Secure with password**: ☐ Get from merge field [field] / ☑ Set password [****]. |
| Missing-attachment policy (v2.11) | Stop the message, skip it, skip all, or stop sending. The error text is "The following file was not found or is inaccessible and cannot be attached." |

### 3.3 Message format

| Control | Options / behaviour |
|---|---|
| **Send message as** | HTML · Plain text · HTML attachment (*.mht) · RTF attachment · PDF attachment (optimized for printing) · PDF attachment (optimized for viewing) · DOCX attachment. Also an "HTML-filtered" smaller-HTML mode, per the comparison table. |
| Description text | Explains the chosen mode, e.g. "The Microsoft Word document will be converted to PDF format and sent as an attachment…" |
| **Specify the attachment file name** | ◉ Use document name (e.g. `Doc1.pdf`) / ◉ **Custom name** with merge fields + fixed extension. |
| ☑ **Save copy of generated attachment in the following folder** | Folder path + **Change…** (local or network share). |
| **Encrypt the document with a password for…** (collapsible) | **Viewing**: ☐ Get from merge field [field] / ☐ Set password. **Editing**: ☐ Get from merge field / ☐ Set password. |
| PDF permission checkboxes (when an editing password is set) | Allow low resolution printing · Allow high quality printing · Allow document modifying · Allow form fields filling · Allow content copying · Allow copying for accessibility · Allow commenting · Allow document assembly. |
| **Message body** (attachment modes) | ◉ Keep empty · ◉ **Edit message body…** (opens editor) · ◉ Use the text of attached document. Option to choose HTML or Plain Text for shared content (v5.2). |
| ☐ **Hide lines with the blank values in the lists** | Skips list lines whose merge fields are empty (v5.2). |

**Message body editor** sub-dialog: HTML-capable rich text box with Open/Save/Cut/Copy/Paste toolbar, a **Merge fields** list (inserts `<<Full_Name>>` placeholders), **Load previous text**, OK/Cancel.

### 3.4 Sending settings

| Control | Options / behaviour |
|---|---|
| **Sending method** | Outlook for Windows (limited Outlook on the web since v7.1). |
| Account choice | ◉ **Ask for the e-mail accounts for sending messages** (☑ Enable Outlook profile selection) · ◉ Use Outlook default e-mail account. |
| **Choose account** sub-dialog | Profile (link), Choose account (dropdown), "Will be sent from Email address", ☐ **Move sent messages to folder…** |
| **Send from other Email address** sub-dialog | **From…** address picker + "Using [account]". Supports Exchange/365 **Send As** and **Send on Behalf** (Pro). |
| **Have replies sent to** | Reply-To address or merge field (v6.3). |
| **Recipients** (collapsible summary: "Send message to range of recipients from 1 to 1000") | ◉ All recipients [2275] · ◉ Single recipient selected in the document (current item) · ◉ Range of recipients from [1] to [1000]. |
| ☐ **Exclusion list** | Link to edit a stop-list, plus a path/text box. Excluded rows are counted as "Skipped (excluded recipients)". |
| **Delivery options** (collapsible summary: "The messages will be sent immediately, in batches of 1 message every 10 minutes") | **Sending start**: ◉ Start sending messages in [d] days [h] hours [m] minutes · ◉ **Do not deliver before** [date/time picker]. **Rate**: ◉ Send all messages at once · ◉ Send [N] message per [M] minutes. |
| ☐ **Keep messages in 'Drafts' without sending** | Creates everything for review; nothing goes out. |
| **Other options** | ☐ Add digital signature to messages · ☐ Encrypt merged messages · Importance dropdown (Low / Normal / High). |

### 3.5 Tracking settings

| Control | Options / behaviour |
|---|---|
| ☑ Request delivery receipts / ☐ Request read receipts | Standard Outlook receipt flags. |
| ☑ **Track clicks using UTM parameters in Google Analytics or other service** | Enables the section below. |
| **Custom URL preview** | Live example, e.g. `https://www.example.com/?utm_source=news&utm_medium=email&utm_campaign=july`. |
| Required parameters | **Campaign Source**, **Campaign Medium** (each accepts merge fields via `…`). |
| Optional parameters | ◉ Use subject as a Campaign Name / ◉ Use the following as a Campaign Name; Campaign Term, Campaign Content, Campaign ID. |
| ☐ **Edit links to selected domains only** | Domain box + **Add to list**; default "All links will be updated with UTM parameters." |
| ☑ **Do not update links with existing UTM parameters** | Avoids double-tagging. Tags links in the body *and* in attachments. |

### 3.6 General settings

| Control | Options / behaviour |
|---|---|
| Program interface language | English / German. |
| Turn on logging for | Levels, including "Verbose info". |
| Links | Open add-in log file · Browse Microsoft Outlook add-in logs · Send product logs to the MAPILab Support Team. |
| ☑ **Use current settings for the next mailing** | Remembers the last configuration. |
| ☐ Do not show news from MAPILab Company | Turns off update/news notices. |
| About the program | Version, homepage, support, Change registration code, Purchase/update licence, trial day counter. |

## 4. Other components and dialogs

| Component | Details |
|---|---|
| **Insert merge field** picker | Used by To/Cc/Bcc/Subject/Reply-To/filenames/passwords/UTM/attachment paths. |
| **Message body editor** | See §3.3. |
| **Choose account** / **Send from other address** | See §3.4. |
| **Exclusion list** editor | Stop-list of addresses never to send to (v4.3). |
| **Preview navigation panel** (v7.0) | Steps through the prepared emails, respecting the selected recipient range. |
| **Mail processing for sending** progress dialog | Status: Total records, Messages to be sent, Processed (n [%]), Skipped (excluded recipients); progress bar; Cancel; **Save detailed report…** |
| **Manage report columns** | 26 selectable columns, exported as a spreadsheet: Time stamp, Date stamp, Subject, To, Cc, Bcc, Attachment, Excluded by stop-list, Status, Sending delay, Format, Sender address, E-mail account, Profile, Sent messages folder, Campaign Source, Campaign Name, Missing attachments, Saved document copy, Record counter, Campaign Medium, Campaign Term, Campaign Content, Campaign ID, Tracking domains, Reply to, Importance. Also data source row and attachment path (v5.2). |
| **Export without sending** (v7.1, v7.4) | Export personal messages as **.eml** files, or export personalised PDF/DOCX documents straight to a folder, then show the list of generated files. |
| **Configuration items** (v7.5) | Several named settings sets; selection dialog before the wizard. |
| Installer / deployment | Silent install with registration code, checks for running Office apps, add-in load diagnostics, fixes for disabled add-ins. |

## 5. Merge fields

- All columns of the data source, inserted as `FIELD"Name"` in single-line boxes and `<<Name>>` in the body editor.
- **Dynamic macros** (v7.0): `%DATE%`, `%TIME%`, `%DATETIME%`, `%TIMESTAMP%`, `%MILLISECONDS%`, `%RECORD_NUMBER%`, `%RECORD_COUNTER%`.
- Fields can be used in To, Cc, Bcc, Subject, Reply-To, attachment paths, attachment and ZIP file names, passwords, UTM values and the message body.
- Data-source fields also work inside Word's automated fields (e.g. Database field) (v2.6).

## 6. Data sources

Excel, CSV, databases (anything Word's merge can open), Outlook Contacts (including custom fields), Exchange address book, **SharePoint lists** (Pro, no admin install needed).

## 7. Safety and control features

**What MMT has:**
1. Warning when the To field is missing.
2. Recipient scope: all, current record only, or a range (good for test sends).
3. Live "Send N messages" count on the button.
4. Exclusion list (stop-list).
5. **Keep in Drafts without sending.**
6. Delayed start ("Start in…" / "Do not deliver before…").
7. Throttling: N messages per M minutes.
8. Missing-attachment policy: stop, skip, skip all, or stop sending.
9. Hide blank lines in lists.
10. Cancel during message generation; partial report can be saved.
11. Preview navigation through prepared messages.
12. Detailed per-message report with 26 columns.
13. Export to .eml or folder instead of sending.

**Weak spots, even in MMT (our chance to be better):**
- No final **confirmation summary** before sending (sender, count, sample message).
- No **send-test-to-myself** button.
- No **pre-flight validation**: invalid or duplicate addresses, empty merge values in subject/body, unresolved fields, oversized attachments.
- Cc/Bcc duplication is only mentioned in the FAQ, not warned about in the dialog.
- No **resume-safe send log**: after a crash it is unclear what was already sent.
- Scheduling and throttling depend on Outlook staying open.

## 8. Editions (MMT's split, for our own free/paid decisions)

| Feature | Built-in Office | MMT Standard | MMT Pro |
|---|---|---|---|
| Personalised campaigns, Outlook contacts, Excel, other sources | ✓ | ✓ | ✓ |
| SharePoint list source | ✗ | ✗ | ✓ |
| Personalised DOCX / PDF attachment | ✗ | ✗ | ✓ |
| Password-protected PDF/DOCX | ✗ | ✗ | ✓ |
| Edit body when sending PDF/DOCX | ✗ | ✓ | ✓ |
| Personalised subject | ✗ | ✓ | ✓ |
| Cc / Bcc | ✗ | ✓ | ✓ |
| Static and per-recipient attachments | ✗ | ✓ | ✓ |
| Change sender account | ✗ | ✓ | ✓ |
| Send As / Send on Behalf | ✗ | ✗ | ✓ |
| Batch delivery (throttling) | ✗ | ✗ | ✓ |
| Delay / schedule | ✗ | ✓ | ✓ |
| Delivery and read receipts | ✗ | ✗ | ✓ |
| Signature and encryption | ✓ | ✓ (all messages) | ✓ (per campaign) |
| UTM tracking | ✗ | ✗ | ✓ |
| Exclusion list | ✗ | ✓ | ✓ |
| HTML / Plain text | ✓ | ✓ | ✓ |
| HTML-filtered, RTF, image maps, Publisher GIF emails | ✗ | ✓ | ✓ |

(MapiLab's own tables are not fully consistent about which edition has which feature.)

## 9. MMT vs LibreOffice built-in, and how we would build it

LO built-in = Writer **Mail Merge Wizard** + **Mailings** toolbar + *Tools › Options › LibreOffice Writer › Mail Merge E-mail* (SMTP settings).
Build route: a **Python (PyUNO) extension** (.oxt) for macOS. Rows mentioning SMTP/IMAP are superseded by the Outlook hand-off in §11.

| Feature | LO built-in | How we build it |
|---|---|---|
| To from a data field | Have | Read the document's registered data source through UNO (`com.sun.star.sdb`), or read Calc/CSV directly. |
| Data sources | Have (Calc, CSV, Base, ODBC/JDBC, Thunderbird/Evolution address books) | Reuse LO's data-source layer; add direct .xlsx/.csv picker. |
| Subject with merge fields | **Missing** (static subject) | Our own template engine for single-line fields. |
| Cc / Bcc | Partial: static Cc/Bcc via **Copy to…** in the Send Documents dialog | Per-campaign static or field-based, with a duplication warning. |
| Reply-To | Partial: static "Send replies to different email address" in Options | Static or per-row field. |
| From / sender choice | Partial: one SMTP identity in options | Several saved sender profiles; From may differ from the login where the server allows it. |
| Body formats | Have: Plain text, HTML | Keep; add HTML-filtered (clean, small) output. |
| Document as attachment | Have: Send as OpenDocument Text, PDF Document, Microsoft Word Document (plus HTML Message, Plain Text bodies) | Add DOCX, ODT, PDF (print/view profiles). |
| Body text when sending an attachment | Partial: **Properties…** opens an "Email Message" box built around salutations (female/male/general) plus free text | Separate body editor with fields; or "use text of document". |
| Attachment file name with fields | Partial: one static "Name of the attachment" for email; file output (not email) can name files from a database field | Template-based name; save a copy to a folder. |
| Password-protected PDF + permissions | Partial: **Save with password** + password field (open password only, no permission flags) | `writer_pdf_Export` FilterData: `EncryptFile`, `DocumentOpenPassword`, `RestrictPermissions`, `PermissionPassword`, `Printing` (0/1/2), `Changes` (0–4), `EnableCopyingOfContent`, `EnableTextAccessForAccessibilityTools`. This maps onto MMT's 8 checkboxes. |
| Password-protected DOCX / ODT | Missing in merge | ODT: native password on save. DOCX: LO's OOXML encrypted export *(verify version support)*. |
| Static attachments | Missing | Attach list with wildcards. |
| Per-recipient attachments | **Missing** | Path column(s) + wildcards; missing-file policy. |
| ZIP attachments with password | Missing | Plain ZIP: Python `zipfile`. AES-encrypted ZIP needs a bundled library *(check licence and size; it may be cleaner to offer password PDF instead)*. |
| Recipient range / current record | Have: Send all documents / From–To | Keep, plus "test send to me". |
| Exclude individual records | Partial: "Exclude recipient" checkbox | Add a reusable exclusion list file. |
| Throttling | **Missing** | Our own queue: N per M minutes. |
| Delayed / scheduled start | **Missing** | Our queue: start time stored in a persistent send log; resume when LO reopens. |
| Keep as drafts | Missing | SMTP backend: IMAP APPEND to Drafts. Outlook for Mac: create without sending. Export: `.eml` with `X-Unsent: 1`. |
| Save to Sent folder | Missing | IMAP APPEND to Sent (optional). |
| Delivery / read receipts | Missing | SMTP DSN (`NOTIFY=SUCCESS` via smtplib rcpt options) and `Disposition-Notification-To` header. |
| Importance | Missing | `Importance` / `X-Priority` headers. |
| UTM link tagging | Missing | Rewrite links in HTML body and in generated PDF/DOCX before export. |
| Hide lines with blank values | Partial: Writer hidden-paragraph and conditional fields | One-click option that applies this automatically. |
| Dynamic macros (date, record no.) | Partial: Writer date and record-number fields in body only | Same macros as MMT, usable everywhere. |
| Send progress / pause / stop | Have: Pause, Cancel, "n of m emails processed", "Emails not sent" count | Richer progress, cancel, resumable log. |
| Detailed report | Missing | CSV/ODS report with selectable columns (MMT's 26 + validation results). |
| Preview each message | Partial: preview of the document records | Full rendered preview including To, Subject, attachments and their names. |
| Export to .eml / folder | Partial: save merged documents | Export .eml, PDFs or DOCX per row, plus a list of generated files. |
| Digital signature / S/MIME encryption | Missing | Hard in pure Python; defer or leave to the email client. |
| Saved configurations | Missing | Named presets stored with the document or in the user profile. |
| SMTP OAuth (Gmail / Microsoft 365) | Missing *(LO uses username/password)* | Needed: Microsoft is retiring basic SMTP auth and Gmail needs app passwords or OAuth. Plan an XOAUTH2 login or recommend the Outlook hand-off. |

## 10. Our "better than MMT" safety design

1. **Pre-flight check** before anything can be sent, which blocks sending until each issue is fixed or accepted:
   - invalid or duplicate addresses;
   - rows with an empty To;
   - empty merge values in the subject or body;
   - unresolved fields;
   - missing or oversized attachments;
   - Cc/Bcc duplication.
2. **Preview every message** as it will actually be sent: headers, body and attachment names, with arrows and a jump to any row.
3. **Send test to me**: sends 1–3 sample rows to the user's own address with a "[TEST]" subject.
4. **Final confirmation** summary showing sender, backend, count, schedule, rate and a sample. For large sends (over e.g. 50 messages), the user must type the number of messages to confirm.
5. **Hold window**: the first batch waits a few minutes and can be cancelled.
6. **Persistent send log** with one entry per row and its status. A crash or restart resumes without sending anything twice.
7. **Safe defaults**: throttle on, Drafts or Export mode suggested for first use, Cc/Bcc off.
8. Live count on the Send button, as in MMT.
