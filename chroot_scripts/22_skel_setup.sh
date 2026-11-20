#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: Skeleton (skel) Setup
# Installs all custom user configurations from config/skel/ to /etc/skel
# and /home/vice/.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring user skeleton (skel) directory..."

    local skel_src_dir="/vice_payload/config/skel"
    local skel_dest_dir="/etc/skel"

    if [ ! -d "$skel_src_dir" ]; then
        log_error "Skeleton directory missing in payload: $skel_src_dir! Aborting."
        exit 1
    fi

    # Helper function to copy skeleton and fix permissions safely
    sync_skel() {
        local dest_dir="$1"
        local owner="$2"

        # 1. Copy all contents, including hidden files and nested directories
        cp -r "$skel_src_dir"/. "$dest_dir"/
        chown -R "$owner" "$dest_dir"

        # 2. Ensure standard permissions: 755 for dirs, 644 for files
        find "$dest_dir" -type d -exec chmod 755 {} \;
        find "$dest_dir" -type f -exec chmod 644 {} \;

        # 3. CRITICAL FIX: Restore executable permissions for scripts
        # The openbox and labwc 'autostart' scripts must be executable to run on login
        if [ -f "$dest_dir/.config/openbox/autostart" ]; then
            chmod 755 "$dest_dir/.config/openbox/autostart"
        fi
        if [ -f "$dest_dir/.config/labwc/autostart" ]; then
            chmod 755 "$dest_dir/.config/labwc/autostart"
        fi
    }

    # Ensure /etc/skel exists
    mkdir -p "$skel_dest_dir"

    # 1. Install to system skeleton (for new users created post-install)
    sync_skel "$skel_dest_dir" "root:root"
    log_info "Copied skeleton files to /etc/skel/"

    # 2. Install to vice user (for Live ISO and default physical install)
    if id -u vice >/dev/null 2>&1; then
        local vice_home="/home/vice"
        if [ -d "$vice_home" ]; then
            sync_skel "$vice_home" "vice:vice"
            log_info "Copied skeleton files to /home/vice/"
        else
            log_warn "Home directory for 'vice' not found. Skipping user skel installation."
        fi
    else
        log_warn "User 'vice' not found. Skipping user skel installation."
    fi

    log_success "Skeleton setup completed."
}

main "$@"