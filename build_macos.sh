#!/usr/bin/env bash
#
# Build MyMacroRecorder.app on macOS and zip it for distribution.
# Run this ON A MAC (PyInstaller cannot cross-compile a .app from Linux/Windows).
#
# Usage:
#   ./build_macos.sh
#
# Output:
#   dist/MyMacroRecorder.app
#   MyMacroRecorder.app.zip
#
set -euo pipefail

echo ">> Creating virtual environment (.venv)…"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo ">> Installing dependencies…"
pip install --upgrade pip
pip install -r requirements.txt

echo ">> Cleaning previous build artifacts…"
rm -rf build dist MyMacroRecorder.app.zip

echo ">> Building the .app bundle with PyInstaller…"
pyinstaller MyMacroRecorder.spec --noconfirm

echo ">> Zipping the .app (using ditto to preserve macOS metadata)…"
# ditto produces a clean, Finder-friendly archive of the bundle.
ditto -c -k --sequesterRsrc --keepParent "dist/MyMacroRecorder.app" "MyMacroRecorder.app.zip"

echo ""
echo ">> Done."
echo "   App:  dist/MyMacroRecorder.app"
echo "   Zip:  MyMacroRecorder.app.zip"
