#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: Cron Setup
# Installs the custom /etc/default/cron configuration for expanded PATH.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring Cron daemon defaults..."

    local cron_src="/vice_payload/config/default/cron"
    local cron_dest="/etc/default/cron"

    if [ ! -f "$cron_src" ]; then
        log_error "Cron config file missing in payload: $cron_src! Aborting."
        exit 1
    fi

    mkdir -p /etc/default
    cp "$cron_src" "$cron_dest"
    chown root:root "$cron_dest"
    chmod 644 "$cron_dest"
    log_info "Installed custom cron configuration (PATH expanded)."

    log_success "Cron setup completed."
}

main "$@"