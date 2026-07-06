#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) SquashFS Creator
# Compresses the chroot directory into a live-boot compatible squashfs image.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Source Shared Library ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

# --- Arguments ---
CHROOTDIR="${1:?Error: CHROOTDIR argument required}"
IMAGEDIR="${2:?Error: IMAGEDIR argument required}"
SQUASHFS_TARGET="$IMAGEDIR/live/filesystem.squashfs"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ] && [ -f "$SQUASHFS_TARGET" ]; then
        log_warn "SquashFS creation failed. Removing partial artifact..."
        rm -f "$SQUASHFS_TARGET"
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Main ---
main() {
    check_dependencies "mksquashfs"

    log_info "Creating SquashFS image..."
    mkdir -p "$IMAGEDIR/live"

    # Remove existing squashfs to prevent using stale artifacts
    rm -f "$SQUASHFS_TARGET"

    # Attempt XZ compression (high ratio, slower)
    if ! mksquashfs "$CHROOTDIR" "$SQUASHFS_TARGET" -comp xz -e boot; then
        log_warn "XZ compression failed. Falling back to GZIP..."
        # Fallback to GZIP (lower ratio, faster)
        if ! mksquashfs "$CHROOTDIR" "$SQUASHFS_TARGET" -comp gzip -e boot; then
            log_error "SquashFS creation failed with both XZ and GZIP."
            exit 1
        fi
    fi

    local size
    size=$(du -sh "$SQUASHFS_TARGET" | awk '{print $1}')
    log_success "SquashFS created successfully at $SQUASHFS_TARGET (Size: $size)"
}

main "$@"