#!/bin/sh
# Look at how Mail lays out a NEW email window. Creates one empty new email (no recipients),
# prints its accessibility layout, then closes it WITHOUT saving. Nothing is saved or sent.
osascript <<'EOF'
tell application "Mail"
    activate
    set m to make new outgoing message with properties {subject:"MMOM layout check", visible:true}
end tell
delay 2
set out to ""
tell application "System Events" to tell process "Mail"
    set w to front window
    set out to "Front window: " & (name of w) & linefeed
    set out to out & my dump(w, 0)
end tell
tell application "Mail" to close m saving no
return out

on dump(el, depth)
    if depth > 7 then return ""
    set s to ""
    tell application "System Events"
        try
            set kids to UI elements of el
        on error
            return ""
        end try
        repeat with k in kids
            set r to ""
            set d to ""
            set n to ""
            try
                set r to role of k
            end try
            try
                set d to description of k
            end try
            try
                set n to name of k
            end try
            set pad to ""
            repeat depth times
                set pad to pad & "  "
            end repeat
            set s to s & pad & r & " | " & d & " | " & n & linefeed
            if r is not in {"AXButton", "AXStaticText", "AXImage", "AXMenuButton", "AXCheckBox", "AXPopUpButton"} then
                set s to s & my dump(k, depth + 1)
            end if
        end repeat
    end tell
    return s
end dump
EOF
