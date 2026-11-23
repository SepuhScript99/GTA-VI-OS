#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: System Tuning & Security
# Applies sysctl, dphys-swapfile, NetworkManager, Fail2ban, Firefox ESR,
# Fontconfig CJK/Emoji fallbacks, and Picom configurations.
# Note: Systemd unit installation is handled by 19_systemd_setup.sh
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

install_firefox_defaults() {
    log_info "Configuring Firefox ESR defaults and policies..."
    local ff_src="/vice_payload/config/firefox"

    if [ -f "$ff_src/vice-os.js" ]; then
        mkdir -p /etc/firefox-esr
        cp "$ff_src/vice-os.js" /etc/firefox-esr/vice-os.js
        chown root:root /etc/firefox-esr/vice-os.js
        chmod 644 /etc/firefox-esr/vice-os.js

        # Also link into browser/defaults/preferences if it is a separate directory
        local ff_pref_dir="/usr/lib/firefox-esr/browser/defaults/preferences"
        if [ -d "$ff_pref_dir" ] && [ ! -L "$ff_pref_dir" ]; then
            ln -sf /etc/firefox-esr/vice-os.js "$ff_pref_dir/vice-os.js"
        fi
        log_info "Installed Firefox ESR preferences (/etc/firefox-esr/vice-os.js)."
    else
        log_warn "config/firefox/vice-os.js not found in payload!"
    fi

    if [ -f "$ff_src/policies.json" ]; then
        mkdir -p /etc/firefox/policies /etc/firefox-esr/policies
        cp "$ff_src/policies.json" /etc/firefox/policies/policies.json
        cp "$ff_src/policies.json" /etc/firefox-esr/policies/policies.json
        chown root:root /etc/firefox/policies/policies.json /etc/firefox-esr/policies/policies.json
        chmod 644 /etc/firefox/policies/policies.json /etc/firefox-esr/policies/policies.json
        log_info "Installed Firefox ESR policies.json."
    fi
}

install_fontconfig_defaults() {
    log_info "Installing Fontconfig CJK and Emoji fallback rules..."
    local fc_src="/vice_payload/config/fontconfig"

    if [ -d "$fc_src" ]; then
        mkdir -p /etc/fonts/conf.avail /etc/fonts/conf.d
        for conf in "$fc_src"/*.conf; do
            if [ -f "$conf" ]; then
                local name
                name=$(basename "$conf")
                cp "$conf" "/etc/fonts/conf.avail/$name"
                chown root:root "/etc/fonts/conf.avail/$name"
                chmod 644 "/etc/fonts/conf.avail/$name"
                ln -sf "../conf.avail/$name" "/etc/fonts/conf.d/$name"
                log_info "Installed fontconfig rule: $name"
            fi
        done
    else
        log_warn "config/fontconfig not found in payload!"
    fi

    if command -v fc-cache > /dev/null 2>&1; then
        log_info "Rebuilding fontconfig cache..."
        fc-cache -f || true
    fi
}

install_picom_config() {
    if [ -f /vice_payload/config/picom.conf ]; then
        mkdir -p /etc/xdg
        cp /vice_payload/config/picom.conf /etc/xdg/picom.conf
        chown root:root /etc/xdg/picom.conf
        chmod 644 /etc/xdg/picom.conf
        log_info "Installed lightweight Picom configuration (/etc/xdg/picom.conf)."
    fi
}

configure_fail2ban() {
    if [ -d /etc/fail2ban ] || command -v fail2ban-server > /dev/null 2>&1; then
        mkdir -p /etc/fail2ban/jail.d
        cat <<'F2B' > /etc/fail2ban/jail.d/99-vice-os.conf
# Debian 12 uses systemd-journald instead of /var/log/auth.log by default
[DEFAULT]
backend = systemd

[sshd]
backend = systemd
F2B
        chown root:root /etc/fail2ban/jail.d/99-vice-os.conf
        chmod 644 /etc/fail2ban/jail.d/99-vice-os.conf
        log_info "Configured Fail2ban sshd jail to use systemd journal backend."
    fi
}

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
    systemctl enable NetworkManager 2>/dev/null || true

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

    configure_fail2ban
    install_firefox_defaults
    install_fontconfig_defaults
    install_picom_config

    # Ensure LibreOffice uses GTK3 VCL plugin across login shells too
    mkdir -p /etc/profile.d
    cat <<'LOENV' > /etc/profile.d/vice-libreoffice.sh
# Use GTK3 VCL plugin so LibreOffice adopts the GTA VI GTK3 theme
export SAL_USE_VCLPLUGIN=gtk3
LOENV
    chown root:root /etc/profile.d/vice-libreoffice.sh
    chmod 644 /etc/profile.d/vice-libreoffice.sh

    # Pre-allow SSH if ufw is operational; first-boot initialization is completed by vp-firewall.service
    ufw allow ssh 2>/dev/null || true
    # Enable the UFW service so the firewall starts on boot
    systemctl enable ufw 2>/dev/null || true

    log_success "System tuning and security configuration completed."
}

main "$@"
