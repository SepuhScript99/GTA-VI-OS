#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: Systemd Unit Setup
# Installs and enables custom systemd service and timer unit files, and
# ensures PipeWire uses Debian's complete defaults with a clean clock drop-in.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

configure_pipewire_dropin() {
    log_info "Ensuring conflict-free PipeWire drop-in configuration..."

    # Remove monolithic /etc/pipewire/pipewire.conf written by 18_pipewire_setup.sh,
    # which omits context.objects and loads libpipewire-module-protocol-pulse inside
    # the core pipewire daemon (colliding with pipewire-pulse and deadlocking clients).
    if [ -f /etc/pipewire/pipewire.conf ]; then
        rm -f /etc/pipewire/pipewire.conf
        log_info "Removed conflicting /etc/pipewire/pipewire.conf (using stock /usr/share/pipewire/pipewire.conf)."
    fi

    mkdir -p /etc/pipewire/pipewire.conf.d
    cat <<'PWCONF' > /etc/pipewire/pipewire.conf.d/10-vice-audio.conf
# Vice OS PipeWire clock tuning (inherits full Debian /usr/share/pipewire/pipewire.conf)
context.properties = {
    default.clock.rate = 48000
    default.clock.allowed-rates = [ 44100 48000 ]
    default.clock.quantum = 2048
    default.clock.min-quantum = 1024
    default.clock.max-quantum = 4096
}
PWCONF
    chown root:root /etc/pipewire/pipewire.conf.d/10-vice-audio.conf
    chmod 644 /etc/pipewire/pipewire.conf.d/10-vice-audio.conf

    mkdir -p /etc/pipewire/pipewire-pulse.conf.d
    cat <<'PULSECONF' > /etc/pipewire/pipewire-pulse.conf.d/10-vice-pulse.conf
# Vice OS PipeWire-Pulse buffering tuning for VM and desktop playback
pulse.properties = {
    pulse.min.req = 1024/48000
    pulse.default.req = 2048/48000
    pulse.min.quantum = 1024/48000
}
PULSECONF
    chown root:root /etc/pipewire/pipewire-pulse.conf.d/10-vice-pulse.conf
    chmod 644 /etc/pipewire/pipewire-pulse.conf.d/10-vice-pulse.conf

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

    configure_pipewire_dropin

    log_success "Systemd unit setup completed."
}

main "$@"
