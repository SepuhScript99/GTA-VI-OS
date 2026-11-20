#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Bootloader Creator
# Generates hybrid BIOS (bios.img) and UEFI (efiboot.img) GRUB boot images.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

# --- Arguments ---
IMAGEDIR="${1:?Error: IMAGEDIR argument required}"
SCRATCHDIR="${2:?Error: SCRATCHDIR argument required}"
ARCH="${3:-${DEBIAN_ARCH:-amd64}}"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_warn "Bootloader creation failed. Removing partial artifacts..."
        rm -f "$SCRATCHDIR/bootx64.efi" "$SCRATCHDIR/bootaa64.efi" "$SCRATCHDIR/efiboot.img"
        rm -f "$SCRATCHDIR/core.img" "$SCRATCHDIR/bios.img"
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Main ---
main() {
    check_dependencies "grub-mkstandalone" "mcopy" "mmd" "mkfs.vfat" "dd"

    local grub_cfg="$IMAGEDIR/boot/grub/grub.cfg"

    log_info "Validating GRUB configuration..."
    if [ ! -f "$grub_cfg" ]; then
        log_error "GRUB config not found at $grub_cfg. Did the previous phase fail?"
        exit 1
    fi

    log_info "Target architecture: ${ARCH}"

    # Determine EFI parameters based on architecture
    local efi_format=""
    local efi_binary=""
    local efi_boot_name=""
    local efi_pkg_hint=""
    if [ "${ARCH}" = "arm64" ]; then
        efi_format="arm64-efi"
        efi_binary="bootaa64.efi"
        efi_boot_name="BOOTAA64.EFI"
        efi_pkg_hint="grub-efi-arm64-bin"
    else
        efi_format="x86_64-efi"
        efi_binary="bootx64.efi"
        efi_boot_name="BOOTX64.EFI"
        efi_pkg_hint="grub-efi-amd64-bin"
    fi

    # Verify EFI binaries directory exists
    local efi_mod_dir="/usr/lib/grub/${efi_format}"
    if [ ! -d "$efi_mod_dir" ]; then
        log_error "GRUB EFI directory not found: $efi_mod_dir. Please install $efi_pkg_hint."
        exit 1
    fi

    # --- Generate EFI GRUB image ---
    log_info "Generating EFI boot image (${efi_format})..."
    if ! grub-mkstandalone --format="${efi_format}" \
        --output="$SCRATCHDIR/${efi_binary}" \
        --locales="" --fonts="" \
        "boot/grub/grub.cfg=$grub_cfg"; then
        log_error "Failed to generate EFI GRUB standalone image (${efi_format})."
        exit 1
    fi

    # Create FAT image for EFI (use fixed volume ID for reproducibility)
    log_info "Creating EFI System Partition image (efiboot.img)..."
    dd if=/dev/zero of="$SCRATCHDIR/efiboot.img" bs=1M count=20 status=none
    if ! mkfs.vfat -i 47544136 "$SCRATCHDIR/efiboot.img" >/dev/null 2>&1; then
        log_error "Failed to format efiboot.img as FAT."
        exit 1
    fi

    mmd -i "$SCRATCHDIR/efiboot.img" efi efi/boot
    if ! mcopy -m -i "$SCRATCHDIR/efiboot.img" "$SCRATCHDIR/${efi_binary}" "::efi/boot/${efi_boot_name}"; then
        log_error "Failed to copy ${efi_boot_name} into efiboot.img."
        exit 1
    fi

    # --- Generate BIOS GRUB image (x86_64 only) ---
    if [ "${ARCH}" != "arm64" ]; then
        log_info "Generating BIOS boot image..."
        local cdboot_img="/usr/lib/grub/i386-pc/cdboot.img"
        if [ ! -f "$cdboot_img" ]; then
            log_error "$cdboot_img not found. Is grub-pc-bin installed?"
            exit 1
        fi

        local bios_modules="linux normal iso9660 biosdisk search search_fs_file search_label search_fs_uuid part_gpt part_msdos loopback squash4 font gfxterm all_video test cat echo memdisk tar fat ext2"
        local core_modules="biosdisk iso9660 memdisk tar search search_fs_file search_label part_gpt part_msdos normal"
        if ! grub-mkstandalone --format=i386-pc \
            --output="$SCRATCHDIR/core.img" \
            --install-modules="$bios_modules" \
            --modules="$core_modules" \
            --locales="" --fonts="" \
            "boot/grub/grub.cfg=$grub_cfg"; then
            log_error "Failed to generate BIOS GRUB standalone image."
            exit 1
        fi

        cat "$cdboot_img" "$SCRATCHDIR/core.img" > "$SCRATCHDIR/bios.img"
        log_info "BIOS boot image created (i386-pc)."
    else
        log_info "Skipping BIOS boot image (ARM64 — UEFI only)."

        # --- Stage Raspberry Pi boot files (ARM64) ---
        if [ -d "$WORKDIR/config/rpi" ]; then
            log_info "Staging Raspberry Pi boot configuration..."
            if [ -f "$WORKDIR/config/rpi/config.txt" ]; then
                mcopy -m -i "$SCRATCHDIR/efiboot.img" "$WORKDIR/config/rpi/config.txt" "::config.txt" 2>/dev/null || true
                cp "$WORKDIR/config/rpi/config.txt" "$IMAGEDIR/config.txt" 2>/dev/null || true
            fi
            if [ -f "$WORKDIR/config/rpi/cmdline.txt" ]; then
                mcopy -m -i "$SCRATCHDIR/efiboot.img" "$WORKDIR/config/rpi/cmdline.txt" "::cmdline.txt" 2>/dev/null || true
                cp "$WORKDIR/config/rpi/cmdline.txt" "$IMAGEDIR/cmdline.txt" 2>/dev/null || true
            fi
            if [ -f "$WORKDIR/config/rpi/boot.cmd" ]; then
                mcopy -m -i "$SCRATCHDIR/efiboot.img" "$WORKDIR/config/rpi/boot.cmd" "::boot.cmd" 2>/dev/null || true
                cp "$WORKDIR/config/rpi/boot.cmd" "$IMAGEDIR/boot.cmd" 2>/dev/null || true
            fi
        fi
    fi

    log_success "Bootloader images created successfully."
}

main "$@"