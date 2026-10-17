#!/bin/sh
# Read-only: list every app window title (all processes, including background ones).
osascript <<'EOF'
set out to ""
tell application "System Events"
    repeat with p in every process
        try
            repeat with w in windows of p
                set out to out & (name of p) & " | " & (name of w) & linefeed
            end repeat
        end try
    end repeat
end tell
return out
EOF
