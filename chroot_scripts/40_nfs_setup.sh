#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: NFS Common Setup
# Installs the custom /etc/default/nfs-common configuration for network storage.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

main() {
    log_info "Configuring NFS Common daemon defaults..."

    local nfs_src="/vice_payload/config/default/nfs-common"
    local nfs_dest="/etc/default/nfs-common"

    if [ ! -f "$nfs_src" ]; then
        log_error "NFS config file missing in payload: $nfs_src! Aborting."
        exit 1
    fi

    mkdir -p /etc/default
    cp "$nfs_src" "$nfs_dest"
    chown root:root "$nfs_dest"
    chmod 644 "$nfs_dest"
    log_info "Installed custom nfs-common configuration (Statd/Idmapd/Gssd enabled)."

    log_success "NFS Common setup completed."
}

main "$@"