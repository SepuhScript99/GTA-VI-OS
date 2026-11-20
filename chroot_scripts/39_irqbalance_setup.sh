#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: IRQBalance Setup
# Installs the custom /etc/default/irqbalance configuration for performance.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring IRQ Balance daemon defaults..."

    local irqbalance_src="/vice_payload/config/default/irqbalance"
    local irqbalance_dest="/etc/default/irqbalance"

    if [ ! -f "$irqbalance_src" ]; then
        log_error "IRQBalance config file missing in payload: $irqbalance_src! Aborting."
        exit 1
    fi

    mkdir -p /etc/default
    cp "$irqbalance_src" "$irqbalance_dest"
    chown root:root "$irqbalance_dest"
    chmod 644 "$irqbalance_dest"
    log_info "Installed custom irqbalance configuration (Daemon enabled)."

    log_success "IRQBalance setup completed."
}

main "$@"