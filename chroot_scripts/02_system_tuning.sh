#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: System Tuning & Security
# Applies sysctl, dphys-swapfile, and NetworkManager configurations.
# Note: Systemd unit installation is handled by 19_systemd_setup.sh
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Applying kernel tunings..."
    if [ -f /vice_payload/config/sysctl.conf ]; then
        mkdir -p /etc/sysctl.d
        cp /vice_payload/config/sysctl.conf /etc/sysctl.d/99-vice-os.conf
        chown root:root /etc/sysctl.d/99-vice-os.conf
        chmod 644 /etc/sysctl.d/99-vice-os.conf
    else
        log_warn "sysctl.conf not found in payload! Skipping kernel tuning."
    fi

    log_info "Disabling dphys-swapfile to prevent disk swap conflicts with ZRAM..."
    if [ -f /vice_payload/config/dphys-swapfile ]; then
        cp /vice_payload/config/dphys-swapfile /etc/dphys-swapfile
        chown root:root /etc/dphys-swapfile
        chmod 644 /etc/dphys-swapfile
        # Mask the service so it doesn't even attempt to start
        systemctl mask dphys-swapfile.service 2>/dev/null || true
    else
        log_warn "dphys-swapfile config not found in payload!"
    fi

    log_info "Configuring Network and Security..."
    # Note: systemd-resolved is intentionally NOT enabled here to prevent DNS
    # conflicts with NetworkManager on the Live ISO. See 05_network_audio_fix.sh.
    systemctl enable NetworkManager

    # Install NetworkManager DNS configuration
    if [ -f /vice_payload/config/NetworkManager/conf.d/10-dns.conf ]; then
        mkdir -p /etc/NetworkManager/conf.d
        cp /vice_payload/config/NetworkManager/conf.d/10-dns.conf /etc/NetworkManager/conf.d/
        chown root:root /etc/NetworkManager/conf.d/10-dns.conf
        chmod 644 /etc/NetworkManager/conf.d/10-dns.conf
        log_info "Installed NetworkManager DNS configuration."
    else
        log_warn "NetworkManager DNS config not found in payload!"
    fi

    # Pre-allow SSH if ufw is operational; first-boot initialization is completed by vp-firewall.service
    ufw allow ssh 2>/dev/null || true
    # Enable the UFW service so the firewall starts on boot
    systemctl enable ufw

    log_success "System tuning and security configuration completed."
}

main "$@"