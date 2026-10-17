#!/bin/sh
# Build dist/OpenMailMerge.oxt from extension/ (an .oxt is a zip file).
set -e
cd "$(dirname "$0")"
python3 -m unittest discover -s tests -q
mkdir -p dist
rm -f dist/OpenMailMerge.oxt
cd extension
zip -r -X ../dist/OpenMailMerge.oxt . -x '*/__pycache__/*' '*.pyc' '.DS_Store' > /dev/null
cd ..
echo "Built dist/OpenMailMerge.oxt"
