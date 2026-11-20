#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Password Reset Tool
# Resets a forgotten user password by mounting the root partition and chrooting.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"

LOCKFILE="/var/lock/vice-reset-password.lock"
LOCKED=0
MOUNTED=0

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?

    if [ "${MOUNTED:-0}" -eq 1 ]; then
        log_info "Cleaning up recovery mounts..."
        if mountpoint -q /mnt; then
            umount -R /mnt 2>/dev/null || umount -l -R /mnt 2>/dev/null || true
        fi
    fi

    # Release the lock only if acquired by this process
    if [ "${LOCKED:-0}" -eq 1 ]; then
        flock -u 9 2>/dev/null || true
        exec 9>&- 2>/dev/null || true
        rm -f "$LOCKFILE" 2>/dev/null || true
    fi

    if [ "${LOCKED:-0}" -eq 1 ]; then
        if [ $exit_code -eq 0 ]; then
            log_success "Password reset completed successfully."
        else
            log_error "Password reset failed with exit code $exit_code."
        fi
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Main ---
main() {
    # Handle flags
    if [[ "${1:-}" == "--version" ]]; then
        echo "Vice OS Password Reset Tool v1.1"
        echo "Usage: sudo $0 <root_partition> <username>"
        exit 0
    fi
    if [[ "${1:-}" == "--help" ]] || [[ "${1:-}" == "-h" ]]; then
        echo "Vice OS Password Reset Tool"
        echo ""
        echo "Resets user password on target root partition from a Live CD or rescue shell."
        echo ""
        echo "Usage: sudo $0 <root_partition> <username>"
        echo "Example: sudo $0 /dev/sda2 vice"
        exit 0
    fi

    check_root
    check_dependencies "mount" "umount" "chroot" "grep"

    mkdir -p /var/lock 2>/dev/null || true
    # Prevent concurrent execution
    exec 9>"$LOCKFILE"
    if ! flock -n 9; then
        log_error "Another password reset process is already running. Exiting."
        exit 1
    fi
    LOCKED=1

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

    if mountpoint -q /mnt; then
        log_error "/mnt is already mounted. Please unmount /mnt before running password reset."
        exit 1
    fi

    log_info "Mounting root partition ($root_part) to /mnt..."
    mount "$root_part" /mnt
    MOUNTED=1

    # Fast validation before mounting virtual filesystems
    if [ ! -f /mnt/etc/passwd ]; then
        log_error "Target partition $root_part does not contain a valid Linux root filesystem (/etc/passwd missing)."
        exit 1
    fi

    if ! grep -q "^${username}:" /mnt/etc/passwd; then
        log_error "User '$username' does not exist on the target system ($root_part)."
        exit 1
    fi

    log_info "Mounting virtual filesystems for chroot..."
    mount --rbind /dev /mnt/dev
    mount --make-rslave /mnt/dev
    mount --bind /proc /mnt/proc
    mount --rbind /sys /mnt/sys
    mount --make-rslave /mnt/sys

    if [ ! -x /mnt/usr/bin/passwd ] && [ ! -x /mnt/bin/passwd ]; then
        log_error "passwd utility not found in target system root filesystem."
        exit 1
    fi

    log_warn "Changing password for user '$username'..."
    # Run passwd interactively inside the chroot
    chroot /mnt passwd "$username"

    # Cleanup is handled by the trap
}

main "$@"
