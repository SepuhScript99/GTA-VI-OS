#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: Polkit Setup
# Installs custom polkit rules for desktop authentication and native udisks2
# removable media auto-mounting.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring Polkit (PolicyKit) rules..."

    # Ensure the rules directory exists
    mkdir -p /etc/polkit-1/rules.d

    # Install the Vice OS polkit rules
    if [ -f /vice_payload/config/polkit-1.preset ]; then
        cp /vice_payload/config/polkit-1.preset /etc/polkit-1/rules.d/49-vice-os.rules
        # Defer udisks2 actions so 50-vice-udisks-automount.rules allows passwordless
        # removable USB/optical mount/eject for active local console users in sudo.
        sed -i 's/if (subject.isInGroup("sudo")) {/if (subject.isInGroup("sudo") \&\& action.id.indexOf("org.freedesktop.udisks2.") !== 0) {/' /etc/polkit-1/rules.d/49-vice-os.rules
        # Polkit requires strict permissions for rules files
        chown root:root /etc/polkit-1/rules.d/49-vice-os.rules
        chmod 644 /etc/polkit-1/rules.d/49-vice-os.rules
        log_info "Installed Vice OS polkit rules (49-vice-os.rules)."
    else
        log_error "polkit-1.preset not found in payload! Skipping polkit configuration."
        exit 1
    fi

    # Install modular polkit-1/rules.d rules (e.g. 50-vice-udisks-automount.rules)
    if [ -d /vice_payload/config/polkit-1/rules.d ]; then
        local rule_file
        for rule_file in /vice_payload/config/polkit-1/rules.d/*.rules; do
            if [ -f "$rule_file" ]; then
                local rule_name
                rule_name=$(basename "$rule_file")
                cp "$rule_file" "/etc/polkit-1/rules.d/$rule_name"
                chown root:root "/etc/polkit-1/rules.d/$rule_name"
                chmod 644 "/etc/polkit-1/rules.d/$rule_name"
                log_info "Installed polkit rule: $rule_name"
            fi
        done
    fi

    # Ensure the policykit-1-gnome autostart entry is present system-wide
    # This allows the GUI authentication prompt to appear when actions require elevation
    local gnome_auth_desktop="/usr/share/applications/polkit-gnome-authentication-agent-1.desktop"
    local autostart_dest="/etc/xdg/autostart/polkit-gnome-authentication-agent-1.desktop"
    if [ -f "$gnome_auth_desktop" ]; then
        mkdir -p /etc/xdg/autostart
        cp "$gnome_auth_desktop" /etc/xdg/autostart/ 2>/dev/null || true
        log_info "Enabled Polkit GNOME authentication agent autostart."
    elif [ -f "$autostart_dest" ]; then
        log_info "Polkit GNOME authentication agent autostart already installed by package."
    else
        log_warn "polkit-gnome-authentication-agent-1.desktop not found. Authentication UI might not start automatically."
    fi

    # Note: polkit service is activated via dbus socket activation, no need to explicitly enable it in chroot.

    log_success "Polkit configuration completed."
}

main "$@"
