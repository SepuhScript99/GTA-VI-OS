#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: Polkit Setup
# Installs custom polkit rules for desktop authentication and privileges.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

log_info "Configuring Polkit (PolicyKit) rules..."

# Ensure the rules directory exists
mkdir -p /etc/polkit-1/rules.d

# Install the Vice OS polkit rules
if [ -f /vice_payload/config/polkit-1.preset ]; then
    cp /vice_payload/config/polkit-1.preset /etc/polkit-1/rules.d/49-vice-os.rules
    # Polkit requires strict permissions for rules files
    chown root:root /etc/polkit-1/rules.d/49-vice-os.rules
    chmod 644 /etc/polkit-1/rules.d/49-vice-os.rules
    log_info "Installed Vice OS polkit rules (49-vice-os.rules)."
else
    log_error "polkit-1.preset not found in payload! Skipping polkit configuration."
    exit 1
fi

# Ensure the policykit-1-gnome autostart entry is present system-wide
# This allows the GUI authentication prompt to appear when actions require elevation
local gnome_auth_desktop="/usr/share/applications/polkit-gnome-authentication-agent-1.desktop"
if [ -f "$gnome_auth_desktop" ]; then
    mkdir -p /etc/xdg/autostart
    cp "$gnome_auth_desktop" /etc/xdg/autostart/ 2>/dev/null || true
    log_info "Enabled Polkit GNOME authentication agent autostart."
else
    log_warn "polkit-gnome-authentication-agent-1.desktop not found. Authentication UI might not start automatically."
fi

# Note: polkit service is activated via dbus socket activation, no need to explicitly enable it in chroot.

log_success "Polkit configuration completed."