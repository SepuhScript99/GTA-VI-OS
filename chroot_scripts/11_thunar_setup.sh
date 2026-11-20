#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: Thunar Setup
# Installs custom Thunar file manager actions for the user and skeleton.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring Thunar custom actions..."

    local uca_src="/vice_payload/config/thunar/uca.xml"

    if [ ! -f "$uca_src" ]; then
        log_error "uca.xml not found in payload! Aborting."
        exit 1
    fi

    # Helper function to install uca.xml safely and DRYly
    install_uca() {
        local target_dir="$1"
        local owner="$2"

        mkdir -p "$target_dir"
        cp "$uca_src" "$target_dir/uca.xml"
        chown "$owner" "$target_dir/uca.xml"
        chmod 644 "$target_dir/uca.xml"
    }

    # 1. Install to skeleton (for any new users created post-install)
    install_uca "/etc/skel/.config/Thunar" "root:root"

    # 2. Install to vice user (for Live ISO and default physical install)
    if id -u vice >/dev/null 2>&1; then
        install_uca "/home/vice/.config/Thunar" "vice:vice"
        log_info "Thunar custom actions installed for 'vice' user and skeleton."
    else
        log_warn "User 'vice' not found. Thunar custom actions installed to skeleton only."
    fi

    log_success "Thunar setup completed."
}

main "$@"