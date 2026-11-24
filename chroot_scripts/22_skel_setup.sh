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

        mkdir -p "$dest_dir"

        # 1. Copy all contents recursively, including dotfiles and nested app dirs
        #    (e.g. .config/galculator/, .config/neofetch/, and .config/libreoffice/4/user/)
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
        chmod 755 "$dest_dir"/Desktop/*.desktop 2>/dev/null || true

        if [ -f "$dest_dir/.config/galculator/galculator.conf" ]; then
            log_info "Synced galculator dark config to $dest_dir/.config/galculator/"
        fi
        if [ -f "$dest_dir/.config/neofetch/config.conf" ]; then
            chmod 644 "$dest_dir/.config/neofetch/config.conf"
            log_info "Synced neofetch GTA VI config to $dest_dir/.config/neofetch/"
        fi
        if [ -f "$dest_dir/.config/libreoffice/4/user/registrymodifications.xcu" ]; then
            log_info "Synced LibreOffice GTA VI config to $dest_dir/.config/libreoffice/4/user/"
        fi
        if [ -f "$dest_dir/.config/Code/User/settings.json" ]; then
            chmod 644 "$dest_dir/.config/Code/User/settings.json"
            log_info "Synced VS Code Leonida settings to $dest_dir/.config/Code/User/"
        fi
        if [ -f "$dest_dir/Desktop/vicefetch.desktop" ]; then
            chmod 755 "$dest_dir/Desktop/vicefetch.desktop"
            log_info "Synced Desktop/vicefetch.desktop to $dest_dir/Desktop/"
        fi
        if [ -f "$dest_dir/Desktop/vscode.desktop" ]; then
            chmod 755 "$dest_dir/Desktop/vscode.desktop"
            log_info "Synced Desktop/vscode.desktop to $dest_dir/Desktop/"
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
