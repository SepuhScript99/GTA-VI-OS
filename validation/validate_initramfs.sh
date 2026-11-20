#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# Vice OS Initramfs Validator
# Validates the initramfs image in the built chroot for integrity and
# essential live-boot components.
# Run against a completed chroot directory or ISO image directory.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

CHROOTDIR="${1:-$WORKDIR/chroot}"
EXIT_CODE=0

main() {
    log_info "=== Validating Initramfs: $CHROOTDIR ==="

    if [ ! -d "$CHROOTDIR/boot" ] && [ ! -d "$CHROOTDIR" ]; then
        log_error "Boot directory not found: $CHROOTDIR/boot"
        exit 1
    fi

    local boot_dir
    if [ -d "$CHROOTDIR/boot" ]; then
        boot_dir="$CHROOTDIR/boot"
    else
        boot_dir="$CHROOTDIR"
    fi

    # 1. Find initramfs image
    local initrd_img
    initrd_img=$(find "$boot_dir" -name 'initrd.img-*' -type f | sort -V | tail -n 1 || true)

    if [ -z "$initrd_img" ]; then
        log_error "No initramfs image (initrd.img-*) found in $boot_dir"
        EXIT_CODE=1
    else
        local initrd_version
        initrd_version=$(basename "$initrd_img" | sed 's/initrd.img-//')
        local initrd_size
        initrd_size=$(du -h "$initrd_img" | awk '{print $1}')
        log_success "Initramfs found: $initrd_version (Size: $initrd_size)"

        # 2. Check initramfs is not empty or truncated
        local initrd_bytes
        initrd_bytes=$(stat -c%s "$initrd_img" 2>/dev/null || stat -f%z "$initrd_img" 2>/dev/null || echo "0")
        if [ "$initrd_bytes" -lt 1000000 ]; then
            log_warn "Initramfs is unusually small: $initrd_size (may be truncated)"
        else
            log_success "Initramfs size looks reasonable."
        fi

        # 3. Validate initramfs format
        local file_type
        file_type=$(file "$initrd_img")
        if echo "$file_type" | grep -q "gzip\|LZ4\|XZ\|cpio\|ASCII cpio"; then
            log_success "Initramfs format is valid: $file_type"
        else
            log_warn "Initramfs format may be invalid: $file_type"
        fi

        # 4. Check for live-boot components inside initramfs
        log_info "Checking initramfs for live-boot support..."
        if command -v lsinitramfs > /dev/null 2>&1; then
            if lsinitramfs "$initrd_img" 2>/dev/null | grep -q "live\|live-boot"; then
                log_success "live-boot scripts detected in initramfs."
            else
                log_warn "No live-boot scripts found in initramfs. Live ISO boot may fail."
            fi
        else
            log_info "lsinitramfs not available. Skipping live-boot content check."
        fi
    fi

    # 5. Check kernel version matches between initramfs and vmlinuz
    local kernel_img
    kernel_img=$(find "$boot_dir" -name 'vmlinuz-*' -type f | sort -V | tail -n 1 || true)

    if [ -n "$kernel_img" ] && [ -n "${initrd_version:-}" ]; then
        local kernel_version
        kernel_version=$(basename "$kernel_img" | sed 's/vmlinuz-//')
        if [ "$kernel_version" = "${initrd_version:-}" ]; then
            log_success "Kernel and initramfs versions match: $kernel_version"
        else
            log_error "Version mismatch: kernel=$kernel_version initramfs=${initrd_version:-unknown}"
            EXIT_CODE=1
        fi
    fi

    if [ "$EXIT_CODE" -eq 0 ]; then
        log_success "Initramfs validation passed."
    else
        log_error "Initramfs validation failed."
    fi

    exit $EXIT_CODE
}

main "$@"
