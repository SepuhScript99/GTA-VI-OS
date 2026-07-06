#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: Desktop Autostart Setup
# Installs XDG autostart entries for the compositor, wallpaper, and shell.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

log_info "Installing XDG Autostart entries..."

# Ensure the system-wide autostart directory exists
mkdir -p /etc/xdg/autostart

# Copy the .desktop files from the payload to the system autostart directory
local autostart_files=(
    "vice-os-compositor.desktop"
    "vice-os-wallpaper.desktop"
    "vice-os-shell.desktop"
)

for file in "${autostart_files[@]}"; do
    if [ -f "/vice_payload/config/$file" ]; then
        cp "/vice_payload/config/$file" "/etc/xdg/autostart/"
        chmod 644 "/etc/xdg/autostart/$file"
        log_info "Installed: $file"
    else
        log_warn "Autostart file missing in payload: $file"
    fi
done

log_success "Desktop autostart configuration completed."