#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: System Scripts Installation
# Installs all utility, app, and recovery scripts to /usr/local/, maintaining
# the directory structure so WORKDIR resolution works correctly.
# Creates symlinks in /usr/local/bin/ for CLI and GUI execution.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Installing system scripts and maintaining directory structure..."

    # 1. Install shared library to /usr/local/lib
    mkdir -p /usr/local/lib
    if [ -f /vice_payload/lib/common.sh ]; then
        cp /vice_payload/lib/common.sh /usr/local/lib/
        chmod 644 /usr/local/lib/common.sh
        log_info "Installed: /usr/local/lib/common.sh"
    fi

    # Helper function to install a category of scripts safely
    install_scripts() {
        local category="$1"
        local src_dir="/vice_payload/$category"
        local dest_dir="/usr/local/$category"

        mkdir -p "$dest_dir"

        # Check if directory exists and has files
        if [ ! -d "$src_dir" ]; then
            log_warn "Source directory missing: $src_dir"
            return
        fi

        # Use find to safely handle empty directories and avoid globbing issues
        while IFS= read -r -d '' script; do
            local script_name=$(basename "$script")
            local dest_path="$dest_dir/$script_name"

            cp "$script" "$dest_path"
            chmod 755 "$dest_path"
            chown root:root "$dest_path"

            # Create symlink in /usr/local/bin (force to ensure idempotency)
            local bin_link="/usr/local/bin/$script_name"
            ln -sf "$dest_path" "$bin_link"

            log_info "Installed: $category/$script_name"
        done < <(find "$src_dir" -maxdepth 1 -name "*.sh" -print0)
    }

    # 2. Install system_scripts, system_utils, apps, and recovery scripts
    install_scripts "system_scripts"
    install_scripts "system_utils"
    install_scripts "apps"
    install_scripts "recovery"

    log_success "System utility scripts installation completed."
}

main "$@"