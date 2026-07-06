#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) ISO Packer
# Assembles the final hybrid BIOS/UEFI bootable ISO using xorriso.
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
OUTDIR="${3:?Error: OUTDIR argument required}"
ISO_NAME="${4:?Error: ISO_NAME argument required}"
ISO_LABEL="${5:?Error: ISO_LABEL argument required}"

ISO_OUTPUT="$OUTDIR/$ISO_NAME"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ] && [ -f "$ISO_OUTPUT" ]; then
        log_warn "ISO packing failed. Removing partial ISO artifact..."
        rm -f "$ISO_OUTPUT"
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Main ---
main() {
    check_dependencies "xorriso"

    log_info "Validating boot artifacts..."
    # Validate that all required files exist before calling xorriso
    local required_files=(
        "$IMAGEDIR/vmlinuz"
        "$IMAGEDIR/initrd.img"
        "$IMAGEDIR/VICE_OS"
        "$IMAGEDIR/live/filesystem.squashfs"
        "$IMAGEDIR/boot/grub/grub.cfg"
        "$SCRATCHDIR/bios.img"
        "$SCRATCHDIR/efiboot.img"
    )

    for file in "${required_files[@]}"; do
        if [ ! -f "$file" ]; then
            log_error "Required artifact not found: $file"
            exit 1
        fi
    done

    log_info "Packing final ISO with xorriso..."
    mkdir -p "$OUTDIR"

    # Remove existing ISO to prevent confusion if xorriso fails silently
    rm -f "$ISO_OUTPUT"

    if ! xorriso -as mkisofs -r -J -joliet-long -iso-level 3 \
        -full-iso9660-filenames -volid "$ISO_LABEL" \
        --grub2-boot-info --grub2-mbr /usr/lib/grub/i386-pc/boot_hybrid.img \
        -eltorito-boot boot/grub/bios.img -no-emul-boot -boot-load-size 4 -boot-info-table \
        --eltorito-catalog boot/grub/boot.cat \
        -eltorito-alt-boot -e EFI/efiboot.img -no-emul-boot \
        --append_partition 2 0xef "$SCRATCHDIR/efiboot.img" \
        -output "$ISO_OUTPUT" \
        -graft-points \
        "$IMAGEDIR"= \
        /boot/grub/bios.img="$SCRATCHDIR/bios.img" \
        /EFI/efiboot.img="$SCRATCHDIR/efiboot.img"; then
        
        log_error "xorriso failed to create the ISO image."
        exit 1
    fi

    if [ ! -s "$ISO_OUTPUT" ]; then
        log_error "xorriso completed but ISO file is missing or zero bytes."
        exit 1
    fi

    local size
    size=$(du -sh "$ISO_OUTPUT" | awk '{print $1}')
    log_success "ISO packed successfully at $ISO_OUTPUT (Size: $size)"
}

main "$@"