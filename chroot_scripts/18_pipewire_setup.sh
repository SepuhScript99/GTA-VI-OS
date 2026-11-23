#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: PipeWire & WirePlumber Setup
# Aligns PipeWire with pure stock Debian 12 pipewire-audio defaults, installs
# minimal WirePlumber 0.4.x VM/AC97 ALSA tuning, and configures RTKit/audio
# privileges.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

ensure_stock_debian_pipewire() {
    # Remove any custom monolithic or drop-in PipeWire overrides so pure upstream
    # Debian 12 /usr/share/pipewire/{pipewire,pipewire-pulse}.conf defaults apply.
    rm -f /etc/pipewire/pipewire.conf \
          /etc/pipewire/pipewire.conf.d/10-vice-audio.conf \
          /etc/pipewire/pipewire-pulse.conf.d/10-vice-pulse.conf
    log_info "Aligned PipeWire with stock Debian 12 configuration."
}

install_wireplumber_config() {
    local wp_src="/vice_payload/config/wireplumber/main.lua.d/51-vice-vm-alsa.lua"
    local wp_dest="/etc/wireplumber/main.lua.d/51-vice-vm-alsa.lua"

    if [ ! -f "$wp_src" ]; then
        log_error "WirePlumber VM ALSA tuning missing in payload: $wp_src! Aborting."
        exit 1
    fi

    mkdir -p /etc/wireplumber/main.lua.d
    cp "$wp_src" "$wp_dest"
    chown root:root "$wp_dest"
    chmod 644 "$wp_dest"
    log_info "Installed WirePlumber 0.4.x VM ALSA tuning ($wp_dest)."
}

configure_realtime_audio() {
    if id -u vice >/dev/null 2>&1; then
        if getent group pipewire >/dev/null 2>&1; then
            usermod -aG pipewire vice 2>/dev/null || true
        fi
        if getent group audio >/dev/null 2>&1; then
            usermod -aG audio vice 2>/dev/null || true
        fi
    fi

    mkdir -p /etc/security/limits.d
    cat <<'LIMITS' > /etc/security/limits.d/95-vice-audio.conf
# Allow PipeWire/audio group members realtime scheduling and memory locking
@audio    - rtprio  95
@audio    - nice    -19
@audio    - memlock unlimited
@pipewire - rtprio  95
@pipewire - nice    -19
@pipewire - memlock unlimited
LIMITS
    chown root:root /etc/security/limits.d/95-vice-audio.conf
    chmod 644 /etc/security/limits.d/95-vice-audio.conf

    # Permit RTKit D-Bus requests before 49-vice-os.rules prompts sudo users
    mkdir -p /etc/polkit-1/rules.d
    cat <<'RTKITPOL' > /etc/polkit-1/rules.d/10-vice-rtkit.rules
// Allow local audio/pipewire/active sessions to use RTKit without interactive auth
polkit.addRule(function(action, subject) {
    if (action.id.indexOf("org.freedesktop.RealtimeKit1.") === 0 &&
        subject.local &&
        (subject.active || subject.isInGroup("pipewire") || subject.isInGroup("audio"))) {
        return polkit.Result.YES;
    }
});
RTKITPOL
    chown root:root /etc/polkit-1/rules.d/10-vice-rtkit.rules
    chmod 644 /etc/polkit-1/rules.d/10-vice-rtkit.rules

    systemctl enable rtkit-daemon.service 2>/dev/null || true
    systemctl --global enable pipewire.socket pipewire-pulse.socket pipewire.service pipewire-pulse.service wireplumber.service 2>/dev/null || true
    log_info "Configured realtime audio limits and RTKit polkit rule."
}

main() {
    log_info "Configuring PipeWire & WirePlumber audio server..."

    ensure_stock_debian_pipewire
    install_wireplumber_config
    configure_realtime_audio

    log_success "PipeWire setup completed."
}

main "$@"
