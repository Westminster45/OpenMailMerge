#!/bin/sh
# Open one formatted test email via macOS share-to-Mail, then report (while it is open) which app owns
# the window, whether Mail's scripting can see it, and its layout. Nothing is saved or sent.
mkdir -p /tmp/mmom_share && printf 'Attachment for share test\n' > /tmp/mmom_share/attachment.txt
osascript -l JavaScript <<'EOF'
ObjC.import('AppKit');
$.NSApplication.sharedApplication;
var html = '<p><b>Bold line</b> and <span style="color:#c00000">a red line</span>.</p>' +
           '<p><i>Accents: Grüße, naïve, £€. Emoji: 😀</i></p><ul><li>Bullet one</li><li>Bullet two</li></ul>';
var body = $.NSAttributedString.alloc.initWithHTMLDocumentAttributes($(html).dataUsingEncoding($.NSUTF8StringEncoding), null);
var svc = $.NSSharingService.sharingServiceNamed($.NSSharingServiceNameComposeEmail);
svc.recipients = $(['you@example.com']);
svc.subject = 'MMOM share test';
svc.performWithItems($([body, $.NSURL.fileURLWithPath('/tmp/mmom_share/attachment.txt')]));
delay(1);
EOF
sleep 6
echo "== Mail windows (Mail scripting):"; osascript -e 'tell application "Mail" to get name of every window'
echo "== Mail new emails (Mail scripting):"; osascript -e 'tell application "Mail" to get subject of every outgoing message'
echo "== Apps with a window named MMOM share test:"
osascript <<'EOF'
set out to ""
tell application "System Events"
    repeat with p in (every process whose background only is false)
        try
            repeat with w in windows of p
                if name of w contains "MMOM share test" then set out to out & (name of p) & " | " & (name of w) & linefeed
            end repeat
        end try
    end repeat
end tell
return out
EOF
