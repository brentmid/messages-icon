#!/bin/bash
# Build the dock-badge-reader helper.
#
# Compiles dock-badge-reader.swift with swiftc, ad-hoc signs the result.
# Output: ./dock-badge-reader (sibling of this script)
#
# After building, you must grant Accessibility permission to the produced
# binary in System Settings → Privacy & Security → Accessibility, otherwise
# the helper will exit with code 3.

set -euo pipefail

cd "$(dirname "$0")"

OUT="dock-badge-reader"

echo "Compiling $OUT..."
swiftc -O "$OUT.swift" -o "$OUT"

echo "Ad-hoc signing $OUT..."
codesign -s - --force "$OUT"

echo
echo "Built: $(pwd)/$OUT"
echo
echo "Next steps:"
echo "  1. Open System Settings → Privacy & Security → Accessibility"
echo "  2. Add this binary: $(pwd)/$OUT"
echo "  3. Restart the LaunchAgent:"
echo "       launchctl kickstart -k gui/\$(id -u)/net.midwood.messages-icon"
