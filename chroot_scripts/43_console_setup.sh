#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: Console Setup
# Installs the custom /etc/default/console-setup configuration for TTY fonts.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring Console Setup defaults..."

    local console_src="/vice_payload/config/default/console-setup"
    local console_dest="/etc/default/console-setup"

    if [ ! -f "$console_src" ]; then
        log_error "Console-setup config file missing in payload: $console_src! Aborting."
        exit 1
    fi

    mkdir -p /etc/default
    cp "$console_src" "$console_dest"
    chown root:root "$console_dest"
    chmod 644 "$console_dest"
    log_info "Installed custom console-setup configuration (UTF-8, VGA 8x16)."

    log_success "Console Setup completed."
}

main "$@"