#!/bin/sh
# Read-only: open a .eml in Mail and report its windows and the Message/File menu items with enabled state.
# Clicks nothing. Usage: dev/inspect_mail_window.sh <file.eml>
set -e
open -a Mail "$1"
sleep 4
osascript <<'EOF'
tell application "System Events" to tell process "Mail"
    set frontmost to true
    set out to "Front window: " & (name of front window) & linefeed & "All windows: "
    repeat with w in windows
        set out to out & (name of w) & " | "
    end repeat
    repeat with mname in {"Message", "File"}
        set out to out & linefeed & linefeed & mname & " menu:" & linefeed
        repeat with mi in menu items of menu mname of menu bar 1
            set n to name of mi
            if n is not missing value then set out to out & "  " & n & " = " & (enabled of mi) & linefeed
        end repeat
    end repeat
    return out
end tell
EOF
