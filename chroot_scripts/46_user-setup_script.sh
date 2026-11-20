#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: User Setup Defaults Installation
# Installs the custom /etc/default/user-setup configuration.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring User Setup defaults..."

    local user_setup_src="/vice_payload/config/default/user-setup"
    local user_setup_dest="/etc/default/user-setup"

    if [ ! -f "$user_setup_src" ]; then
        log_error "User-setup config file missing in payload: $user_setup_src! Aborting."
        exit 1
    fi

    mkdir -p /etc/default
    cp "$user_setup_src" "$user_setup_dest"
    chown root:root "$user_setup_dest"
    chmod 644 "$user_setup_dest"
    log_info "Installed custom user-setup configuration (Default user: vice)."

    log_success "User Setup defaults installation completed."
}

main "$@"