#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) RootFS Creator
# Executes debootstrap to create the base Debian filesystem and stages the
# vice_payload directory for chroot configuration.
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

# --- Main ---
main() {
    check_dependencies "debootstrap"

    log_info "=== Starting RootFS Creation ==="

    # Step 1: Debootstrap minimal Debian (Bookworm) - with Fallback
    if [ ! -d "$CHROOTDIR/etc" ]; then
        log_info "Bootstrapping Debian Bookworm into $CHROOTDIR..."
        rm -rf "$CHROOTDIR"
        mkdir -p "$CHROOTDIR"
        
        if ! debootstrap --arch=amd64 bookworm "$CHROOTDIR" http://deb.debian.org/debian/; then
            log_warn "Primary Debian mirror failed. Falling back to US mirror..."
            if ! debootstrap --arch=amd64 bookworm "$CHROOTDIR" http://ftp.us.debian.org/debian/; then
                log_error "Debootstrap failed on both primary and fallback mirrors."
                exit 1
            fi
        fi
    else
        log_warn "Chroot directory already exists. Skipping debootstrap."
    fi

    # Step 2: Stage the vice_payload directory inside the chroot
    log_info "Staging project files into chroot payload..."
    
    # Clean up any existing payload to prevent stale files on resume
    rm -rf "$CHROOTDIR/vice_payload"
    mkdir -p "$CHROOTDIR/vice_payload"
    
    local dirs_to_copy=("config" "assets" "desktop" "apps" "system_scripts" "lib" "chroot_scripts")
    for dir in "${dirs_to_copy[@]}"; do
        if [ -d "$WORKDIR/$dir" ]; then
            cp -r "$WORKDIR/$dir" "$CHROOTDIR/vice_payload/"
        else
            log_warn "Directory missing from workspace: $dir"
        fi
    done

    # Ensure all scripts in the payload are executable using find
    log_info "Setting executable permissions for payload scripts..."
    find "$CHROOTDIR/vice_payload" -type f \( -name "*.sh" -o -name "*.py" \) -exec chmod +x {} \;

    log_success "RootFS creation and payload staging completed."
}

main "$@"