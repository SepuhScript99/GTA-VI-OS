#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: APT Config Setup
# Installs global APT configurations (no-recommends, unattended-upgrades) and
# backports kernel/firmware pinning preferences for installed systems.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring APT global settings and pinning preferences..."

    local apt_conf_dir="/vice_payload/config/apt/apt.conf.d"
    local apt_conf_src="$apt_conf_dir/99-no-recommends"

    if [ ! -f "$apt_conf_src" ]; then
        log_error "APT config file missing in payload: $apt_conf_src! Aborting."
        exit 1
    fi

    # Install all apt.conf.d drop-ins (99-no-recommends, 20auto-upgrades, 50unattended-upgrades)
    mkdir -p /etc/apt/apt.conf.d
    local conf_file conf_name
    for conf_file in "$apt_conf_dir"/*; do
        if [ -f "$conf_file" ]; then
            conf_name=$(basename "$conf_file")
            cp "$conf_file" "/etc/apt/apt.conf.d/$conf_name"
            chown root:root "/etc/apt/apt.conf.d/$conf_name"
            chmod 644 "/etc/apt/apt.conf.d/$conf_name"
            log_info "Installed APT config: /etc/apt/apt.conf.d/$conf_name"
        fi
    done

    # Persist APT pinning preferences (90-vice-backports-kernel) on installed systems
    local apt_pref_dir="/vice_payload/config/apt/preferences.d"
    if [ -d "$apt_pref_dir" ]; then
        mkdir -p /etc/apt/preferences.d
        local pref_file pref_name
        for pref_file in "$apt_pref_dir"/*; do
            if [ -f "$pref_file" ]; then
                pref_name=$(basename "$pref_file")
                cp "$pref_file" "/etc/apt/preferences.d/$pref_name"
                chown root:root "/etc/apt/preferences.d/$pref_name"
                chmod 644 "/etc/apt/preferences.d/$pref_name"
                log_info "Installed APT preference: /etc/apt/preferences.d/$pref_name"
            fi
        done
    fi

    log_success "APT configuration completed."
}

main "$@"
