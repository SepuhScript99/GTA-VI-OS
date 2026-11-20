#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: Systemd Unit Setup
# Installs and enables custom systemd service and timer unit files.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Installing custom systemd units..."

    local src_dir="/vice_payload/config/systemd/system"
    local dest_dir="/etc/systemd/system"

    # Install zram-setup.conf environment file referenced by zram-setup.service
    if [ -f /vice_payload/config/systemd/zram-setup.conf ]; then
        cp /vice_payload/config/systemd/zram-setup.conf /etc/systemd/zram-setup.conf
        chmod 644 /etc/systemd/zram-setup.conf
        log_info "Installed: zram-setup.conf"
    else
        log_warn "zram-setup.conf not found in payload!"
    fi

    if [ ! -d "$src_dir" ]; then
        log_error "Systemd source directory missing: $src_dir! Aborting."
        exit 1
    fi

    # Ensure destination directory exists
    mkdir -p "$dest_dir"

    # Copy all .service and .timer files from the payload to /etc/systemd/system/
    for unit in "$src_dir"/*.service "$src_dir"/*.timer; do
        if [ -f "$unit" ]; then
            local unit_name=$(basename "$unit")
            cp "$unit" "$dest_dir/$unit_name"
            chown root:root "$dest_dir/$unit_name"
            chmod 644 "$dest_dir/$unit_name"
            log_info "Installed unit: $unit_name"
        fi
    done

    log_info "Enabling custom systemd units..."

    # ZRAM Setup
    systemctl enable zram-setup.service 2>/dev/null || { log_error "Failed to enable zram-setup.service"; exit 1; }
    mkdir -p /etc/modules-load.d
    echo "zram" > /etc/modules-load.d/zram.conf

    # Vice OS Auto-Update Timer
    systemctl enable vp-autoupdate.timer 2>/dev/null || { log_error "Failed to enable vp-autoupdate.timer"; exit 1; }

    # Vice OS Firewall Initialization Service
    systemctl enable vp-firewall.service 2>/dev/null || { log_error "Failed to enable vp-firewall.service"; exit 1; }

    log_success "Systemd unit setup completed."
}

main "$@"