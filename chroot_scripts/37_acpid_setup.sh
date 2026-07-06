#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: Acpid Setup
# Installs the custom /etc/default/acpid configuration for power management.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring ACPI daemon defaults..."

    local acpid_src="/vice_payload/config/default/acpid"
    local acpid_dest="/etc/default/acpid"

    if [ ! -f "$acpid_src" ]; then
        log_error "Acpid config file missing in payload: $acpid_src! Aborting."
        exit 1
    fi

    mkdir -p /etc/default
    cp "$acpid_src" "$acpid_dest"
    chown root:root "$acpid_dest"
    chmod 644 "$acpid_dest"
    log_info "Installed custom acpid configuration (Socket enabled)."

    log_success "Acpid setup completed."
}

main "$@"