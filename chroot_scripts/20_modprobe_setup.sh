#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: Modprobe Setup
# Installs custom modprobe configurations (blacklists and VM audio clock fixes).
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring Modprobe (Kernel Module) settings..."

    local modprobe_src_dir="/vice_payload/config/modprobe.d"
    local modprobe_dest_dir="/etc/modprobe.d"
    local required_confs=("blacklist.conf" "vice-audio-vm.conf")
    local conf_name

    for conf_name in "${required_confs[@]}"; do
        if [ ! -f "${modprobe_src_dir}/${conf_name}" ]; then
            log_error "Modprobe config file missing in payload: ${modprobe_src_dir}/${conf_name}! Aborting."
            exit 1
        fi
    done

    # Ensure the destination directory exists
    mkdir -p "$modprobe_dest_dir"

    local conf_file
    for conf_file in "${modprobe_src_dir}"/*.conf; do
        [ -f "$conf_file" ] || continue
        conf_name=$(basename "$conf_file")
        cp "$conf_file" "${modprobe_dest_dir}/${conf_name}"
        chown root:root "${modprobe_dest_dir}/${conf_name}"
        chmod 644 "${modprobe_dest_dir}/${conf_name}"
        log_info "Installed modprobe config (${conf_name})."
    done

    log_success "Modprobe setup completed."
}

main "$@"
