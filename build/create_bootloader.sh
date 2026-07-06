#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Bootloader Creator
# Generates hybrid BIOS (bios.img) and UEFI (efiboot.img) GRUB boot images.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Source Shared Library ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

# --- Arguments ---
IMAGEDIR="${1:?Error: IMAGEDIR argument required}"
SCRATCHDIR="${2:?Error: SCRATCHDIR argument required}"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_warn "Bootloader creation failed. Removing partial artifacts..."
        rm -f "$SCRATCHDIR/bootx64.efi" "$SCRATCHDIR/efiboot.img"
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

    # --- Generate EFI GRUB image ---
    log_info "Generating EFI boot image..."
    if ! grub-mkstandalone --format=x86_64-efi \
        --output="$SCRATCHDIR/bootx64.efi" \
        --locales="" --fonts="" \
        "boot/grub/grub.cfg=$grub_cfg"; then
        log_error "Failed to generate EFI GRUB standalone image."
        exit 1
    fi

    # Create FAT image for EFI
    log_info "Creating EFI System Partition image (efiboot.img)..."
    dd if=/dev/zero of="$SCRATCHDIR/efiboot.img" bs=1M count=20 status=none
    if ! mkfs.vfat "$SCRATCHDIR/efiboot.img" >/dev/null 2>&1; then
        log_error "Failed to format efiboot.img as FAT."
        exit 1
    fi
    
    mmd -i "$SCRATCHDIR/efiboot.img" efi efi/boot
    if ! mcopy -i "$SCRATCHDIR/efiboot.img" "$SCRATCHDIR/bootx64.efi" ::efi/boot/BOOTX64.EFI; then
        log_error "Failed to copy BOOTX64.EFI into efiboot.img."
        exit 1
    fi

    # --- Generate BIOS GRUB image ---
    log_info "Generating BIOS boot image..."
    local cdboot_img="/usr/lib/grub/i386-pc/cdboot.img"
    if [ ! -f "$cdboot_img" ]; then
        log_error "$cdboot_img not found. Is grub-pc-bin installed?"
        exit 1
    fi

    if ! grub-mkstandalone --format=i386-pc \
        --output="$SCRATCHDIR/core.img" \
        --install-modules="linux normal iso9660 biosdisk search loopback squash4" \
        --modules="linux normal iso9660 biosdisk search loopback squash4" \
        --locales="" --fonts="" \
        "boot/grub/grub.cfg=$grub_cfg"; then
        log_error "Failed to generate BIOS GRUB standalone image."
        exit 1
    fi

    # Concatenate cdboot.img and core.img to create bios.img
    cat "$cdboot_img" "$SCRATCHDIR/core.img" > "$SCRATCHDIR/bios.img"

    log_success "Bootloader images created successfully."
}

main "$@"