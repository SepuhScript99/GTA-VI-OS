#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: Xresources Setup
# Installs .Xresources to theme xterm with the neon aesthetic.
# Note: xrdb is loaded by desktop/dbus_session.sh, so .xprofile is not needed.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring Xresources for terminal theming..."

    local xres_src="/vice_payload/config/Xresources"

    if [ ! -f "$xres_src" ]; then
        log_error "Xresources file not found in payload! Aborting."
        exit 1
    fi

    # Helper function to install .Xresources safely and DRYly
    install_xres_config() {
        local home_dir="$1"
        local owner="$2"
        
        cp "$xres_src" "$home_dir/.Xresources"
        chown "$owner" "$home_dir/.Xresources"
        chmod 644 "$home_dir/.Xresources"
    }

    # 1. Install to skeleton (for any new users created post-install)
    install_xres_config "/etc/skel" "root:root"

    # 2. Install to vice user (for Live ISO and default physical install)
    if id -u vice >/dev/null 2>&1; then
        install_xres_config "/home/vice" "vice:vice"
        log_info "Xresources installed for 'vice' user and skeleton."
    else
        log_warn "User 'vice' not found. Xresources installed to skeleton only."
    fi

    log_success "Xresources setup completed."
}

main "$@"