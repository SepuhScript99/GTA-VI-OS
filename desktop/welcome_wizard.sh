#!/bin/bash
set -Eeuo pipefail

# Vice OS Welcome Wizard Launcher
# Checks if the wizard has already been run before launching.
# This avoids showing the wizard on every boot.

FLAG_FILE="$HOME/.config/vice-os/welcome_completed"
WIZARD="/opt/vice-os/welcome_wizard.py"

if [ -f "$FLAG_FILE" ]; then
    exit 0
fi

if [ ! -f "$WIZARD" ]; then
    echo "Welcome wizard not found: $WIZARD" >&2
    exit 1
fi

exec python3 "$WIZARD"
