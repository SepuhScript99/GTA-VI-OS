#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: Package Installation
# Installs core system packages, kernel, and applications from packages.list.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

# Prevent interactive prompts during package installation
export DEBIAN_FRONTEND=noninteractive

# Pre-seed timezone configuration before packages install
echo "tzdata tzdata/Areas select Etc" | debconf-set-selections
echo "tzdata tzdata/Zones/Etc select UTC" | debconf-set-selections

# Define safe apt options for retries and lock timeouts
APT_OPTS=(
    "-o" "Acquire::Retries=3"
    "-o" "Dpkg::Lock::Timeout=300"
    "-o" "Dpkg::Options::=--force-confold"
    "-o" "Dpkg::Options::=--force-confdef"
)

main() {
    log_info "Installing live-boot BEFORE kernel..."
    # live-boot must be present before the kernel package triggers initramfs generation
    # Explicitly use --no-install-recommends to avoid pulling in unnecessary live-boot extras
    apt-get "${APT_OPTS[@]}" install -y --no-install-recommends live-boot live-config

    log_info "Installing kernel and firmware..."
    apt-get "${APT_OPTS[@]}" install -y --no-install-recommends \
        linux-image-amd64 linux-headers-amd64 initramfs-tools \
        firmware-linux firmware-misc-nonfree

    log_info "Installing packages from list..."
    if [ ! -f /vice_payload/config/packages.list ]; then
        log_error "packages.list not found in payload!"
        exit 1
    fi

    # Read packages line by line, ignoring comments and empty lines.
    # Use --no-run-if-empty to prevent apt-get from crashing if the list is empty.
    # Explicitly use --no-install-recommends as the global apt config isn't installed yet.
    grep -vE '^\s*#' /vice_payload/config/packages.list | xargs --no-run-if-empty apt-get "${APT_OPTS[@]}" install -y --no-install-recommends

    log_info "Generating locales..."
    # Ensure locales package is installed before trying to generate
    apt-get "${APT_OPTS[@]}" install -y --no-install-recommends locales
    sed -i 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen
    locale-gen

    log_info "Installing default locale configuration..."
    if [ -f /vice_payload/config/default/locale ]; then
        mkdir -p /etc/default
        cp /vice_payload/config/default/locale /etc/default/locale
        chown root:root /etc/default/locale
        chmod 644 /etc/default/locale
        # Update the active environment
        update-locale LANG=en_US.UTF-8
    else
        log_warn "config/default/locale not found in payload!"
    fi

    log_info "Installing default keyboard configuration..."
    if [ -f /vice_payload/config/default/keyboard ]; then
        mkdir -p /etc/default
        cp /vice_payload/config/default/keyboard /etc/default/keyboard
        chown root:root /etc/default/keyboard
        chmod 644 /etc/default/keyboard
        # Ensure console-setup is installed and apply the config
        apt-get "${APT_OPTS[@]}" install -y --no-install-recommends console-setup keyboard-configuration
        setupcon --save
    else
        log_warn "config/default/keyboard not found in payload!"
    fi

    log_info "Setting timezone to UTC (universal default)..."
    # tzdata was pre-seeded, but we ensure it's installed and configured cleanly
    apt-get "${APT_OPTS[@]}" install -y --no-install-recommends tzdata
    rm -f /etc/localtime
    ln -s /usr/share/zoneinfo/Etc/UTC /etc/localtime
    dpkg-reconfigure -f noninteractive tzdata

    log_success "Package installation completed."
}

main "$@"