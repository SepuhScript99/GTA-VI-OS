#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: Login Setup
# Installs the custom /etc/default/login configuration for base environment.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring Login defaults..."

    local login_src="/vice_payload/config/default/login"
    local login_dest="/etc/default/login"

    if [ ! -f "$login_src" ]; then
        log_error "Login config file missing in payload: $login_src! Aborting."
        exit 1
    fi

    mkdir -p /etc/default
    cp "$login_src" "$login_dest"
    chown root:root "$login_dest"
    chmod 644 "$login_dest"
    log_info "Installed custom login configuration (PATH, UMASK, ULIMIT)."

    log_success "Login setup completed."
}

main "$@"