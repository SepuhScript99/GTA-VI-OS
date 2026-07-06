#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: LSB Release Setup
# Installs the custom /etc/lsb-release file for legacy OS identification.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring Legacy OS Identity (/etc/lsb-release)..."

    local lsb_release_src="/vice_payload/config/lsb-release"

    if [ ! -f "$lsb_release_src" ]; then
        log_error "lsb-release file not found in payload! Aborting."
        exit 1
    fi

    # Install to /etc/lsb-release
    cp "$lsb_release_src" /etc/lsb-release
    chown root:root /etc/lsb-release
    chmod 644 /etc/lsb-release

    log_success "Legacy OS identity setup completed."
}

main "$@"