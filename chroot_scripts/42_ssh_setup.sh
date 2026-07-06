#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: SSH Setup
# Installs the custom /etc/default/ssh configuration for fast remote admin.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring OpenSSH daemon defaults..."

    local ssh_src="/vice_payload/config/default/ssh"
    local ssh_dest="/etc/default/ssh"

    if [ ! -f "$ssh_src" ]; then
        log_error "SSH config file missing in payload: $ssh_src! Aborting."
        exit 1
    fi

    mkdir -p /etc/default
    cp "$ssh_src" "$ssh_dest"
    chown root:root "$ssh_dest"
    chmod 644 "$ssh_dest"
    log_info "Installed custom ssh configuration (Reverse DNS lookup disabled)."

    log_success "SSH setup completed."
}

main "$@"