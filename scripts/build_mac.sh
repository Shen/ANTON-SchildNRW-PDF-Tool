#!/usr/bin/env bash
set -euo pipefail

# Robust bei Leerzeichen in Pfaden: ins Repo-Root wechseln
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
ONEFILE="${ONEFILE:-1}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python nicht gefunden (gesucht: $PYTHON_BIN). Bitte installieren oder PYTHON_BIN setzen." >&2
  exit 1
fi

"$PYTHON_BIN" -m pip install --upgrade pip pyinstaller
if [ -f "$ROOT_DIR/requirements.txt" ]; then
  "$PYTHON_BIN" -m pip install -r "$ROOT_DIR/requirements.txt"
fi

START_PY="$ROOT_DIR/ANTON-Tool.py"
# App direkt im Projekt-Hauptverzeichnis ablegen
DIST_DIR="$ROOT_DIR"
BUILD_DIR="$ROOT_DIR/build"
SPEC_DIR="$ROOT_DIR"

ARGS=(
  --windowed
  --name "ANTON-Tool"
  --distpath "$DIST_DIR"
  --workpath "$BUILD_DIR"
  --specpath "$SPEC_DIR"
  --noconfirm
  --clean
  "$START_PY"
)
if [ "$ONEFILE" = "1" ]; then
  ARGS+=(--onefile)
else
  ARGS+=(--onedir)
fi

"$PYTHON_BIN" -m PyInstaller "${ARGS[@]}"

echo "Fertig. Artefakte unter $DIST_DIR" >&2
