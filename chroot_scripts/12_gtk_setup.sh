#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: GTK3 Setup
# Installs global and user GTK3 configurations (settings.ini and gtk.css)
# to enforce the neon dark theme.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring GTK3 theme settings..."

    local gtk_src_dir="/vice_payload/config/gtk-3.0"

    if [ ! -d "$gtk_src_dir" ]; then
        log_error "GTK3 config directory not found in payload! Aborting."
        exit 1
    fi

    # Helper function to install GTK config files safely and DRYly
    install_gtk_config() {
        local dest_dir="$1"
        local owner="$2"
        
        mkdir -p "$dest_dir"
        
        for file in settings.ini gtk.css; do
            if [ -f "$gtk_src_dir/$file" ]; then
                cp "$gtk_src_dir/$file" "$dest_dir/$file"
                chown "$owner" "$dest_dir/$file"
                chmod 644 "$dest_dir/$file"
            fi
        done
    }

    # 1. Install system-wide configuration (/etc/gtk-3.0/)
    install_gtk_config "/etc/gtk-3.0" "root:root"

    # 2. Install to skeleton (for any new users created post-install)
    install_gtk_config "/etc/skel/.config/gtk-3.0" "root:root"

    # 3. Install to vice user (for Live ISO and default physical install)
    if id -u vice >/dev/null 2>&1; then
        install_gtk_config "/home/vice/.config/gtk-3.0" "vice:vice"
        log_info "GTK3 dark theme (ini + css) installed system-wide, to skeleton, and for 'vice' user."
    else
        log_warn "User 'vice' not found. GTK3 dark theme installed system-wide and to skeleton only."
    fi

    log_success "GTK3 setup completed."
}

main "$@"