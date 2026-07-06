#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: Rsyslog Setup
# Installs the custom /etc/default/rsyslog configuration for security.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring Rsyslog daemon defaults..."

    local rsyslog_src="/vice_payload/config/default/rsyslog"
    local rsyslog_dest="/etc/default/rsyslog"

    if [ ! -f "$rsyslog_src" ]; then
        log_error "Rsyslog config file missing in payload: $rsyslog_src! Aborting."
        exit 1
    fi

    mkdir -p /etc/default
    cp "$rsyslog_src" "$rsyslog_dest"
    chown root:root "$rsyslog_dest"
    chmod 644 "$rsyslog_dest"
    log_info "Installed custom rsyslog configuration (DNS lookup disabled)."

    log_success "Rsyslog setup completed."
}

main "$@"