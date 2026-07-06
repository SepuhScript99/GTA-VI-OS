#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Password Reset Tool
# Resets a forgotten user password by mounting the root partition and chrooting.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Source Shared Library ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

LOCKFILE="/var/lock/vice-reset-password.lock"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    
    # Release the lock
    if [ -f "$LOCKFILE" ]; then
        rm -f "$LOCKFILE"
    fi
    
    log_info "Cleaning up recovery mounts..."
    # Use recursive unmount to safely catch all bind mounts and prevent "target is busy"
    if mountpoint -q /mnt; then
        umount -R /mnt 2>/dev/null || true
    fi
    
    if [ $exit_code -eq 0 ]; then
        log_success "Password reset completed successfully."
    else
        log_error "Password reset failed with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Main ---
main() {
    check_root
    check_dependencies "mount" "umount" "chroot" "passwd" "grep"

    # Prevent concurrent execution
    exec 9>"$LOCKFILE"
    if ! flock -n 9; then
        log_error "Another password reset process is already running. Exiting."
        exit 1
    fi

    log_info "=== Starting Password Reset Tool ==="

    if [ $# -lt 2 ]; then
        log_error "Usage: sudo $0 <root_partition> <username>"
        log_error "Example: sudo $0 /dev/sda2 vice"
        exit 1
    fi

    local root_part="$1"
    local username="$2"

    if [ ! -b "$root_part" ]; then
        log_error "Root partition $root_part is not a valid block device."
        exit 1
    fi

    log_info "Mounting root partition ($root_part) to /mnt..."
    mount "$root_part" /mnt

    # Fast user validation before mounting virtual filesystems
    # This reads the chroot's /etc/passwd directly, no chroot needed yet
    if ! grep -q "^${username}:" /mnt/etc/passwd; then
        log_error "User '$username' does not exist on the target system ($root_part)."
        exit 1
    fi

    log_info "Mounting virtual filesystems for chroot..."
    mount --bind /dev /mnt/dev
    mount --bind /proc /mnt/proc
    mount --bind /sys /mnt/sys

    log_warn "Changing password for user '$username'."
    # Run passwd interactively inside the chroot
    chroot /mnt passwd "$username"

    # Cleanup is handled by the trap
}

main "$@"