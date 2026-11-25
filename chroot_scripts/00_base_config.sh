#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: Base Configuration
# Sets up hostname, hosts, fstab, and apt sources from declarative config files.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Installing base configuration files..."

# 1. Hostname
if [ -f /vice_payload/config/hostname ]; then
    cp /vice_payload/config/hostname /etc/hostname
    chown root:root /etc/hostname
    chmod 644 /etc/hostname
else
    log_error "config/hostname not found in payload!"
    exit 1
fi

# 2. Hosts
if [ -f /vice_payload/config/hosts ]; then
    cp /vice_payload/config/hosts /etc/hosts
    chown root:root /etc/hosts
    chmod 644 /etc/hosts
else
    log_error "config/hosts not found in payload!"
    exit 1
fi

# 3. File System Table (fstab)
if [ -f /vice_payload/config/fstab ]; then
    cp /vice_payload/config/fstab /etc/fstab
    chown root:root /etc/fstab
    chmod 644 /etc/fstab
else
    log_error "config/fstab not found in payload!"
    exit 1
fi

# 4. GRUB Defaults
if [ -f /vice_payload/config/default/grub ]; then
    mkdir -p /etc/default
    cp /vice_payload/config/default/grub /etc/default/grub
    chown root:root /etc/default/grub
    chmod 644 /etc/default/grub
    log_info "Installed GRUB defaults."
else
    log_warn "config/default/grub not found in payload. Using defaults."
fi

# 5. APT Sources
if [ -f /vice_payload/config/apt/sources.list ]; then
    cp /vice_payload/config/apt/sources.list /etc/apt/sources.list
    chown root:root /etc/apt/sources.list
    chmod 644 /etc/apt/sources.list
else
    log_error "config/apt/sources.list not found in payload!"
    exit 1
fi

# 6. APT Pinning Preferences (must be installed BEFORE apt-get update / kernel install)
if [ -d /vice_payload/config/apt/preferences.d ]; then
    mkdir -p /etc/apt/preferences.d
    for pref_file in /vice_payload/config/apt/preferences.d/*; do
        if [ -f "$pref_file" ]; then
            pref_name=$(basename "$pref_file")
            cp "$pref_file" "/etc/apt/preferences.d/$pref_name"
            chown root:root "/etc/apt/preferences.d/$pref_name"
            chmod 644 "/etc/apt/preferences.d/$pref_name"
            log_info "Installed APT pinning preference: $pref_name"
        fi
    done
fi

log_info "Updating package lists..."
if ! apt-get update; then
    log_warn "Primary mirror failed. Falling back to US mirror..."
    sed -i 's|deb.debian.org|ftp.us.debian.org|g' /etc/apt/sources.list
    apt-get update
fi

    log_success "Base configuration completed."
}

main "$@"