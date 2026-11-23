#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: Chrony Setup
# Installs Chrony, masks systemd-timesyncd, and configures NTP.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

# Define safe apt options for retries and lock timeouts
APT_OPTS=(
    "-o" "Acquire::Retries=3"
    "-o" "Dpkg::Lock::Timeout=300"
    "-o" "Dpkg::Options::=--force-confold"
    "-o" "Dpkg::Options::=--force-confdef"
)

main() {
    log_info "Configuring Chrony (NTP) time synchronization..."

    # 1. Install Chrony package if not already installed by 01_install_packages.sh
    if ! command -v chronyd >/dev/null 2>&1; then
        log_info "Installing chrony package..."
        apt-get "${APT_OPTS[@]}" install -y --no-install-recommends chrony
    else
        log_info "Chrony package already installed."
    fi

    # 2. Mask systemd-timesyncd to prevent conflicts
    log_info "Masking systemd-timesyncd to prevent NTP conflicts..."
    systemctl mask systemd-timesyncd.service 2>/dev/null || true

    # 3. Install and tune Chrony configuration
    local chrony_src="/vice_payload/config/default/chrony"
    local chrony_dest="/etc/chrony/chrony.conf"

    if [ ! -f "$chrony_src" ]; then
        log_error "Chrony config file missing in payload: $chrony_src! Aborting."
        exit 1
    fi

    mkdir -p /etc/chrony
    cp "$chrony_src" "$chrony_dest"

    # Allow instant clock step whenever offset > 1s (essential for VM suspend/resume & Live ISO)
    if grep -qE '^[[:space:]]*makestep[[:space:]]+' "$chrony_dest"; then
        sed -i -E 's/^[[:space:]]*makestep[[:space:]]+.*/makestep 1 -1/' "$chrony_dest"
    else
        printf '\nmakestep 1 -1\n' >> "$chrony_dest"
    fi

    # Keep hardware RTC synchronized to system clock
    if ! grep -qE '^[[:space:]]*rtcsync([[:space:]]|$)' "$chrony_dest"; then
        printf 'rtcsync\n' >> "$chrony_dest"
    fi

    chown root:root "$chrony_dest"
    chmod 644 "$chrony_dest"
    log_info "Installed and tuned chrony.conf (makestep 1 -1, rtcsync)."

    # 4. Enable Chrony service
    log_info "Enabling chrony service..."
    systemctl enable chrony.service 2>/dev/null || { log_error "Failed to enable chrony.service"; exit 1; }

    log_success "Chrony setup completed."
}

main "$@"
