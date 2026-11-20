#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) SquashFS Creator
# Compresses the chroot directory into a live-boot compatible squashfs image.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

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

    # Reproducibility and exclude options
    local epoch="${SOURCE_DATE_EPOCH:-$(date +%s)}"
    local common_opts=("-all-root" "-mkfs-time" "$epoch")

    # Exclude temporary payload and caches if present; retain /boot by default for offline installer support
    local exclude_args=("-e" "vice_payload")
    if [ "${EXCLUDE_BOOT:-false}" = "true" ]; then
        log_info "EXCLUDE_BOOT=true: Excluding /boot from SquashFS."
        exclude_args+=("boot")
    fi

    # Attempt Zstd compression (fastest decompression, good ratio)
    # Zstd is supported by Linux kernel since 5.19 (Bookworm has 6.1).
    if mksquashfs "$CHROOTDIR" "$SQUASHFS_TARGET" -comp zstd -Xcompression-level 15 "${common_opts[@]}" "${exclude_args[@]}"; then
        log_success "SquashFS created with Zstd compression."
    elif mksquashfs "$CHROOTDIR" "$SQUASHFS_TARGET" -comp xz "${common_opts[@]}" "${exclude_args[@]}"; then
        log_warn "Zstd not available. Falling back to XZ compression."
        log_success "SquashFS created with XZ compression."
    else
        log_warn "XZ compression failed. Falling back to GZIP..."
        if ! mksquashfs "$CHROOTDIR" "$SQUASHFS_TARGET" -comp gzip "${common_opts[@]}" "${exclude_args[@]}"; then
            log_error "SquashFS creation failed with Zstd, XZ, and GZIP."
            exit 1
        fi
        log_success "SquashFS created with GZIP compression."
    fi

    local size
    size=$(du -sh "$SQUASHFS_TARGET" | awk '{print $1}')
    log_success "SquashFS created successfully at $SQUASHFS_TARGET (Size: $size)"
}

main "$@"