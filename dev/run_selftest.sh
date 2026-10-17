#!/bin/sh
# Run dev/selftest.py inside a headless LibreOffice with a throwaway profile.
# Usage: dev/run_selftest.sh [output-dir]
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$(mktemp -d)}"
PROFILE="$OUT/profile"
mkdir -p "$PROFILE/user/Scripts/python"
cp "$ROOT/dev/selftest.py" "$PROFILE/user/Scripts/python/mmm_selftest.py"
export MMM_SRC="$ROOT/extension/pythonpath" MMM_OUT="$OUT"
/Applications/LibreOffice.app/Contents/MacOS/soffice -env:UserInstallation="file://$PROFILE" \
  --headless --norestore --nologo \
  'vnd.sun.star.script:mmm_selftest.py$run?language=Python&location=user'
cat "$OUT/result.json"
