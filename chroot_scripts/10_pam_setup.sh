#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: PAM Setup
# Installs the custom PAM configuration for 'su' to prevent login hangs.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring PAM (Pluggable Authentication Modules)..."

    local pam_src="/vice_payload/config/pam.d/su"
    local pam_dest="/etc/pam.d/su"

    # Ensure the destination directory exists
    mkdir -p /etc/pam.d

    if [ -f "$pam_src" ]; then
        cp "$pam_src" "$pam_dest"
        chown root:root "$pam_dest"
        chmod 644 "$pam_dest"
        log_info "Installed custom PAM configuration for 'su' to prevent login freezes."
    else
        log_warn "PAM config file missing in payload: $pam_src. Skipping PAM setup."
    fi

    log_success "PAM configuration completed."
}

main "$@"