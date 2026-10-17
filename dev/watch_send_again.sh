#!/bin/sh
# Click Message > Send Again on Mail's front window (must be titled $1), then record Mail's window
# titles every 0.3 s for 6 s. Send Again only opens an editable copy; nothing is sent.
# Usage: dev/watch_send_again.sh <window title>
set -e
osascript - "$1" <<'EOF'
on run argv
    set want to item 1 of argv
    tell application "System Events" to tell process "Mail"
        set frontmost to true
        if name of front window is not want then return "Front window is '" & (name of front window) & "', not '" & want & "'. Nothing clicked."
        click menu item "Send Again" of menu "Message" of menu bar 1
        set out to ""
        repeat 20 times
            set names to ""
            repeat with w in windows
                set names to names & "[" & (name of w) & "] "
            end repeat
            set out to out & names & linefeed
            delay 0.3
        end repeat
        return out
    end tell
end run
EOF
