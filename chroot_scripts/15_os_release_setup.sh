#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: OS Release Setup
# Installs the custom /etc/os-release and /usr/lib/os-release files.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring OS Identity (/etc/os-release)..."

    local os_release_src="/vice_payload/config/os-release"

    if [ ! -f "$os_release_src" ]; then
        log_error "os-release file not found in payload! Aborting."
        exit 1
    fi

    # 1. Install to /usr/lib/os-release (Distribution fallback)
    mkdir -p /usr/lib
    cp "$os_release_src" /usr/lib/os-release
    chown root:root /usr/lib/os-release
    chmod 644 /usr/lib/os-release

    # 2. Install to /etc/os-release (System-specific override)
    cp "$os_release_src" /etc/os-release
    chown root:root /etc/os-release
    chmod 644 /etc/os-release

    log_success "OS identity setup completed."
}

main "$@"