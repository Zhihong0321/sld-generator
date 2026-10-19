#!/usr/bin/env bash
# SLD Generator - one-line installer for macOS / Linux
#
#   curl -fsSL https://raw.githubusercontent.com/Zhihong0321/sld-generator/main/install.sh | bash
#
# Downloads (or updates) the repo, installs the `sldgen` command, and runs a health check.
# Re-run any time to update. Set SLD_HOME to choose the folder (default: ~/sld-generator).
# Your projects/ and library/ are never overwritten.
set -euo pipefail

REPO="https://github.com/Zhihong0321/sld-generator"
DIR="${SLD_HOME:-$HOME/sld-generator}"
echo "SLD Generator installer"
echo "  folder: $DIR"

PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  echo "Python 3.10+ not found. Install it (e.g. 'brew install python' or 'sudo apt install python3 python3-pip'), then re-run." >&2
  exit 1
fi
echo "  python: $($PY --version)"

if command -v git >/dev/null 2>&1 && [ -d "$DIR/.git" ]; then
  echo "Updating existing copy (git pull)..."
  git -C "$DIR" pull --ff-only
elif command -v git >/dev/null 2>&1 && [ ! -e "$DIR" ]; then
  echo "Cloning $REPO ..."
  git clone --depth 1 "$REPO" "$DIR"
else
  echo "Downloading tarball..."
  TMP="$(mktemp -d)"
  curl -fsSL "$REPO/archive/refs/heads/main.tar.gz" | tar -xz -C "$TMP"
  SRC="$(find "$TMP" -mindepth 1 -maxdepth 1 -type d | head -1)"
  mkdir -p "$DIR"
  for item in "$SRC"/* "$SRC"/.[!.]*; do
    [ -e "$item" ] || continue
    name="$(basename "$item")"
    if { [ "$name" = projects ] || [ "$name" = library ]; } && [ -e "$DIR/$name" ]; then continue; fi
    cp -R "$item" "$DIR/"
  done
  rm -rf "$TMP"
fi

echo "Installing the sldgen command..."
"$PY" -m pip install --quiet --disable-pip-version-check -e "$DIR" || \
  "$PY" -m pip install --quiet --disable-pip-version-check --user -e "$DIR"

(cd "$DIR" && "$PY" -m sldgen doctor) || true

cat <<EOF

Installed in $DIR
Next:
  cd "$DIR"
  Open this folder in your AI agent (Claude Code, Codex, Cursor, ...) and ask:
    'Follow AGENTS.md: generate an SLD for <your job>'
  Or by hand: sldgen library | sldgen init | sldgen check | sldgen build   (see docs/GUIDE.md)
  If 'sldgen' is not found, use: $PY -m sldgen ...
EOF
