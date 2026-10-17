#!/bin/sh
# Install the built .oxt into a throwaway LibreOffice profile (headless) and check it registers.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$(mktemp -d)}"
PROFILE="$OUT/profile"
mkdir -p "$PROFILE/user/Scripts/python"
cp "$ROOT/dev/installtest.py" "$PROFILE/user/Scripts/python/mmm_installtest.py"
export MMM_OXT="$ROOT/dist/OpenMailMerge.oxt" MMM_OUT="$OUT"
/Applications/LibreOffice.app/Contents/MacOS/soffice -env:UserInstallation="file://$PROFILE" \
  --headless --norestore --nologo \
  'vnd.sun.star.script:mmm_installtest.py$run?language=Python&location=user'
cat "$OUT/install.json"
