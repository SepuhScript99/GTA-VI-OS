#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# Vice OS Kernel Validator
# Validates kernel image, modules, and configuration in the built chroot.
# Run against a completed chroot directory.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

CHROOTDIR="${1:-$WORKDIR/chroot}"
EXIT_CODE=0

main() {
    log_info "=== Validating Kernel: $CHROOTDIR ==="

    if [ ! -d "$CHROOTDIR" ]; then
        log_error "Chroot directory does not exist: $CHROOTDIR"
        exit 1
    fi

    local boot_dir="$CHROOTDIR/boot"

    if [ ! -d "$boot_dir" ]; then
        log_error "/boot directory not found in chroot."
        exit 1
    fi

    # 1. Find kernel image
    local kernel_img
    kernel_img=$(find "$boot_dir" -name 'vmlinuz-*' -type f | sort -V | tail -n 1 || true)

    if [ -z "$kernel_img" ]; then
        log_error "No kernel image (vmlinuz-*) found in $boot_dir"
        EXIT_CODE=1
    else
        local kernel_version
        kernel_version=$(basename "$kernel_img" | sed 's/vmlinuz-//')
        local kernel_size
        kernel_size=$(du -h "$kernel_img" | awk '{print $1}')
        log_success "Kernel found: $kernel_version (Size: $kernel_size)"

        # Check kernel file is valid (ELF binary)
        if file "$kernel_img" | grep -q "Linux kernel\|ELF\|x86-64"; then
            log_success "Kernel image format is valid."
        else
            log_warn "Kernel image format may be invalid: $(file "$kernel_img")"
        fi
    fi

    # 2. Check kernel modules directory
    if [ -n "${kernel_version:-}" ]; then
        local modules_dir="$CHROOTDIR/lib/modules/$kernel_version"
        if [ -d "$modules_dir" ]; then
            local module_count
            module_count=$(find "$modules_dir" -name '*.ko' -type f 2>/dev/null | wc -l)
            log_success "Kernel modules: $module_count modules loaded for $kernel_version."
        else
            log_error "Kernel modules directory not found: $modules_dir"
            EXIT_CODE=1
        fi
    fi

    # 3. Check essential kernel modules
    log_info "Checking essential kernel modules..."
    local essential_modules=("ext4" "squashfs" "overlay" "loop" "virtio" "virtio_blk")
    local missing_modules=0

    if [ -n "${kernel_version:-}" ]; then
        local modules_dir="$CHROOTDIR/lib/modules/$kernel_version"
        if [ -d "$modules_dir" ]; then
            for mod in "${essential_modules[@]}"; do
                if ! find "$modules_dir" -name "${mod}.ko*" -type f 2>/dev/null | grep -q .; then
                    log_warn "Essential module not found: $mod"
                    missing_modules=$((missing_modules + 1))
                fi
            done
        fi
        if [ "$missing_modules" -eq 0 ]; then
            log_success "All essential kernel modules present."
        fi
    fi

    # 4. Check kernel config
    local config_file="$boot_dir/config-${kernel_version:-}"
    if [ -f "$config_file" ]; then
        log_success "Kernel configuration found: config-$kernel_version"
        # Check for important config options
        local important_opts=("CONFIG_SQUASHFS=y" "CONFIG_OVERLAY_FS=y" "CONFIG_EXT4_FS=y")
        for opt in "${important_opts[@]}"; do
            if grep -q "^$opt" "$config_file" 2>/dev/null; then
                log_info "  $opt: enabled"
            fi
        done
    else
        log_warn "Kernel config not found: $config_file"
    fi

    # 5. Check System.map
    local map_file="$boot_dir/System.map-${kernel_version:-}"
    if [ -f "$map_file" ]; then
        local map_size
        map_size=$(du -h "$map_file" | awk '{print $1}')
        log_info "System.map present (Size: $map_size)"
    fi

    if [ "$EXIT_CODE" -eq 0 ]; then
        log_success "Kernel validation passed."
    else
        log_error "Kernel validation failed."
    fi

    exit $EXIT_CODE
}

main "$@"
