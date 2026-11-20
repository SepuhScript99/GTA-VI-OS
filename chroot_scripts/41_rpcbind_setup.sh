#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: RPCBind Setup
# Installs the custom /etc/default/rpcbind configuration for NFSv3 support.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring RPCBind daemon defaults..."

    local rpcbind_src="/vice_payload/config/default/rpcbind"
    local rpcbind_dest="/etc/default/rpcbind"

    if [ ! -f "$rpcbind_src" ]; then
        log_error "RPCBind config file missing in payload: $rpcbind_src! Aborting."
        exit 1
    fi

    mkdir -p /etc/default
    cp "$rpcbind_src" "$rpcbind_dest"
    chown root:root "$rpcbind_dest"
    chmod 644 "$rpcbind_dest"
    log_info "Installed custom rpcbind configuration (Daemon enabled)."

    log_success "RPCBind setup completed."
}

main "$@"