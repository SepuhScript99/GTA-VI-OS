#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: NTP Setup
# Installs fallback config for legacy ntp and masks the service to prevent
# conflicts with chrony.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring legacy NTP fallback and conflict prevention..."

    local ntp_src="/vice_payload/config/default/ntp"
    local ntp_dest="/etc/default/ntp"

    # 1. Install the configuration file
    if [ -f "$ntp_src" ]; then
        mkdir -p /etc/default
        cp "$ntp_src" "$ntp_dest"
        chown root:root "$ntp_dest"
        chmod 644 "$ntp_dest"
        log_info "Installed legacy ntp configuration."
    else
        log_warn "Legacy ntp config missing in payload. Skipping file copy."
    fi

    # 2. Mask the ntp systemd service
    # This ensures that even if the 'ntp' package is installed later via apt,
    # it will not start and conflict with chronyd (which uses port 123).
    log_info "Masking legacy ntp.service to prevent conflicts with chrony..."
    systemctl mask ntp.service 2>/dev/null || true

    log_success "NTP setup completed."
}

main "$@"