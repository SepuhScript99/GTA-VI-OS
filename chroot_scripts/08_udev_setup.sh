#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: Udev Setup
# Installs custom udev rules to hide live-boot loop devices from desktops.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring Udev rules..."

    local rules_src="/vice_payload/config/90-live-installer.rules"
    local rules_dest="/etc/udev/rules.d/90-live-installer.rules"

    # Ensure the rules directory exists
    mkdir -p /etc/udev/rules.d

    if [ -f "$rules_src" ]; then
        cp "$rules_src" "$rules_dest"
        chown root:root "$rules_dest"
        chmod 644 "$rules_dest"
        log_info "Installed 90-live-installer.rules to hide live loop devices."
    else
        log_error "Udev rules file missing in payload: $rules_src"
        exit 1
    fi

    log_success "Udev configuration completed."
}

main "$@"