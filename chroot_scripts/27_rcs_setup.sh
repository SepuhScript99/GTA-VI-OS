#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: rcS Setup
# Installs the custom /etc/default/rcS configuration for boot reliability.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring Boot Defaults (rcS)..."

    local rcs_src="/vice_payload/config/default/rcS"
    local rcs_dest="/etc/default/rcS"

    if [ ! -f "$rcs_src" ]; then
        log_error "rcS config file missing in payload: $rcs_src! Aborting."
        exit 1
    fi

    mkdir -p /etc/default
    cp "$rcs_src" "$rcs_dest"
    chown root:root "$rcs_dest"
    chmod 644 "$rcs_dest"
    log_info "Installed custom rcS configuration (UTC, FSCKFIX)."

    log_success "rcS setup completed."
}

main "$@"