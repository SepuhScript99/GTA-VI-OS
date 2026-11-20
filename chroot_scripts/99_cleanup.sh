#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: Cleanup
# Clears apt caches, temporary files, logs, and sanitizes machine-id.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Cleaning up apt caches..."
    apt-get clean
    rm -rf /var/lib/apt/lists/*

    log_info "Removing temporary files..."
    rm -rf /tmp/* /var/tmp/*
    rm -f /root/.bash_history

    log_info "Sanitizing machine-id..."
    # Ensure /etc/machine-id is empty so systemd generates a unique one on first boot
    rm -f /etc/machine-id
    touch /etc/machine-id

    log_info "Cleaning up logs generated during build..."
    # Remove rotated logs and standard log files
    find /var/log -type f -name '*.log' -delete 2>/dev/null || true
    find /var/log -type f -name '*.gz' -delete 2>/dev/null || true
    # Clear the journal directory directly instead of using journalctl inside chroot
    rm -rf /var/log/journal/*

    log_info "Resetting build-time firewall rules to enable vp-firewall.service on first boot..."
    rm -f /etc/ufw/user.rules /etc/ufw/user.rules.* /etc/ufw/user6.rules /etc/ufw/user6.rules.* 2>/dev/null || true

    log_info "Removing build artifacts..."
    # Remove build metadata file
    rm -f /etc/vice-build.conf
    # Ensure the payload doesn't end up in the squashfs
    rm -rf /vice_payload

    log_success "Chroot cleanup completed."
}

main "$@"