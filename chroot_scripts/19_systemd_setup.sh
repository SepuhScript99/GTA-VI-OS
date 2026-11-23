#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: Systemd Unit Setup
# Installs and enables custom systemd service and timer unit files, aligns
# PipeWire with stock Debian 12 defaults, and masks conflicting/broken units.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

configure_pipewire_dropin() {
    log_info "Ensuring stock Debian 12 PipeWire configuration with WirePlumber VM ALSA tuning..."

    # Remove monolithic /etc/pipewire/pipewire.conf and custom PipeWire/Pulse
    # drop-ins so pure upstream Debian /usr/share/pipewire/*.conf runs cleanly.
    rm -f /etc/pipewire/pipewire.conf
    rm -f /etc/pipewire/pipewire.conf.d/10-vice-audio.conf \
          /etc/pipewire/pipewire-pulse.conf.d/10-vice-pulse.conf

    local wp_src="/vice_payload/config/wireplumber/main.lua.d/51-vice-vm-alsa.lua"
    if [ -f "$wp_src" ]; then
        mkdir -p /etc/wireplumber/main.lua.d
        cp "$wp_src" /etc/wireplumber/main.lua.d/51-vice-vm-alsa.lua
        chown root:root /etc/wireplumber/main.lua.d/51-vice-vm-alsa.lua
        chmod 644 /etc/wireplumber/main.lua.d/51-vice-vm-alsa.lua
    fi

    # Ensure global PipeWire user sockets/services are enabled
    systemctl --global enable pipewire.socket pipewire-pulse.socket pipewire.service pipewire-pulse.service wireplumber.service 2>/dev/null || true
}

install_timesync_dispatcher() {
    local nm_disp_src=""
    if [ -f /vice_payload/config/NetworkManager/90-vice-timesync ]; then
        nm_disp_src="/vice_payload/config/NetworkManager/90-vice-timesync"
    elif [ -f /vice_payload/config/networkmanager/90-vice-timesync ]; then
        nm_disp_src="/vice_payload/config/networkmanager/90-vice-timesync"
    fi

    if [ -n "$nm_disp_src" ]; then
        mkdir -p /etc/NetworkManager/dispatcher.d
        cp "$nm_disp_src" /etc/NetworkManager/dispatcher.d/90-vice-timesync
        chown root:root /etc/NetworkManager/dispatcher.d/90-vice-timesync
        chmod 755 /etc/NetworkManager/dispatcher.d/90-vice-timesync
        log_info "Installed NetworkManager dispatcher: /etc/NetworkManager/dispatcher.d/90-vice-timesync"
    else
        log_warn "NetworkManager dispatcher 90-vice-timesync not found in payload."
    fi
}

configure_boot_service_defaults() {
    log_info "Configuring standard desktop and on-demand security service defaults..."

    # Standard Debian desktop services (enable cleanly if installed)
    local default_enabled_units=(
        "cups.service"
        "cups.socket"
        "bluetooth.service"
        "NetworkManager.service"
        "NetworkManager-dispatcher.service"
        "chrony.service"
        "vice-timesync.service"
        "vice-timesync.timer"
    )
    local unit
    for unit in "${default_enabled_units[@]}"; do
        systemctl enable "$unit" 2>/dev/null || true
    done

    # Keep VPN/Tor/Proxy/Secure-DNS/AV daemons disabled at boot so normal
    # internet/DNS never stalls or breaks Live ISO boot (toggled via Vice Net Shield)
    local on_demand_units=(
        "tor.service"
        "tor@default.service"
        "privoxy.service"
        "dnscrypt-proxy.service"
        "dnscrypt-proxy.socket"
        "stubby.service"
        "unbound.service"
        "unbound-resolvconf.service"
        "openvpn.service"
        "clamav-freshclam.service"
        "clamav-daemon.service"
        "clamav-daemon.socket"
    )
    for unit in "${on_demand_units[@]}"; do
        systemctl disable "$unit" 2>/dev/null || true
    done

    # Mask periodic audit timers/services that require an MTA (mail) or pre-built DB,
    # plus zramswap.service (zram-tools conflicts with zram-setup.service on /dev/zram0)
    local failing_timers=(
        "chkrootkit.service"
        "chkrootkit.timer"
        "dailyaidecheck.service"
        "dailyaidecheck.timer"
        "zramswap.service"
    )
    for unit in "${failing_timers[@]}"; do
        systemctl disable "$unit" 2>/dev/null || true
        systemctl mask "$unit" 2>/dev/null || true
    done
}

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
            local unit_name
            unit_name=$(basename "$unit")
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

    # Vice OS Host Clock & Timezone Sync Service & Timer
    systemctl enable vice-timesync.service 2>/dev/null || { log_error "Failed to enable vice-timesync.service"; exit 1; }
    systemctl enable vice-timesync.timer 2>/dev/null || { log_error "Failed to enable vice-timesync.timer"; exit 1; }

    install_timesync_dispatcher
    configure_boot_service_defaults
    configure_pipewire_dropin

    log_success "Systemd unit setup completed."
}

main "$@"
