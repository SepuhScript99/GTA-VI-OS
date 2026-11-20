#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) ISO Validator
# Validates the structural integrity and bootability of the generated ISO.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Source Shared Library ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

# --- Arguments ---
ISO_PATH="${1:?Error: Path to ISO argument required}"

# --- Main ---
main() {
    check_dependencies "xorriso" "sha256sum" "du"

    log_info "=== Starting ISO Validation ==="

    # 1. Check if ISO exists
    if [ ! -f "$ISO_PATH" ]; then
        log_error "ISO file not found: $ISO_PATH"
        exit 1
    fi

    # 2. Check file size (minimum 500MB for a functional Live ISO)
    local size_bytes
    size_bytes=$(stat -c%s "$ISO_PATH")
    local min_size=$((500 * 1024 * 1024))
    if [ "$size_bytes" -le 0 ]; then
        log_error "ISO file is zero bytes."
        exit 1
    fi
    if [ "$size_bytes" -lt "$min_size" ]; then
        log_error "ISO is too small ($(du -sh "$ISO_PATH" | awk '{print $1}')). Expected at least 500MB."
        exit 1
    fi
    local size_human
    size_human=$(du -sh "$ISO_PATH" | awk '{print $1}')
    log_info "ISO Size: $size_human"

    # 3. Verify SHA256 Checksum (if SHA256SUMS exists)
    local sum_file="$(dirname "$ISO_PATH")/SHA256SUMS"
    if [ -f "$sum_file" ]; then
        log_info "Verifying SHA256 checksum..."
        if ! (cd "$(dirname "$ISO_PATH")" && sha256sum -c SHA256SUMS); then
            log_error "SHA256 checksum verification failed!"
            exit 1
        fi
        log_success "Checksum verified."
    else
        log_warn "SHA256SUMS file not found. Skipping checksum verification."
    fi

    # 4. Inspect ISO structure using xorriso
    log_info "Inspecting ISO structure..."
    local xorriso_report
    xorriso_report=$(xorriso -indev "$ISO_PATH" -report_system_area plain -- 2>&1)

    # Check for El Torito BIOS boot image
    if echo "$xorriso_report" | grep -q "El Torito boot catalog"; then
        log_success "BIOS (El Torito) boot catalog found."
    else
        log_error "BIOS (El Torito) boot catalog MISSING."
        exit 1
    fi

    # Check for EFI boot image
    if echo "$xorriso_report" | grep -qiE "EFI boot|UEFI|efiboot\.img"; then
        log_success "EFI boot image found."
    else
        log_error "EFI boot image MISSING."
        exit 1
    fi

    # Check for Hybrid MBR
    if echo "$xorriso_report" | grep -q "System area summary: MBR"; then
        log_success "Hybrid MBR found (USB bootable)."
    else
        log_warn "Hybrid MBR not found. ISO might not boot from USB in legacy mode."
    fi

    # 5. Verify critical payload files exist inside the ISO
    log_info "Checking critical payload files inside ISO..."
    local critical_files=("/vmlinuz" "/initrd.img" "/VICE_OS" "/live/filesystem.squashfs" "/boot/grub/grub.cfg")

    for file in "${critical_files[@]}"; do
        if xorriso -indev "$ISO_PATH" -find "$file" -maxdepth 0 2>/dev/null | grep -q "$file"; then
            log_success "Found: $file"
        else
            log_error "Missing critical file in ISO: $file"
            exit 1
        fi
    done

    # 6. Validate SquashFS filesystem integrity
    log_info "Validating SquashFS filesystem integrity..."
    local squashfs_size_bytes
    squashfs_size_bytes=$(xorriso -indev "$ISO_PATH" -find /live/filesystem.squashfs -ls 2>/dev/null | awk '/filesystem.squashfs/{print $5}')
    if [ -z "$squashfs_size_bytes" ] || [ "$squashfs_size_bytes" -le 1000000 ]; then
        log_error "SquashFS is too small or missing (${squashfs_size_bytes:-0} bytes)."
        exit 1
    fi
    log_success "SquashFS size: $(awk "BEGIN {printf \"%.1fM\", $squashfs_size_bytes / 1048576}")"

    # 7. Validate kernel and initramfs sizes
    log_info "Validating kernel and initramfs sizes..."
    local kernel_size_bytes
    kernel_size_bytes=$(xorriso -indev "$ISO_PATH" -find /vmlinuz -ls 2>/dev/null | awk '/vmlinuz/{print $5}')
    local initrd_size_bytes
    initrd_size_bytes=$(xorriso -indev "$ISO_PATH" -find /initrd.img -ls 2>/dev/null | awk '/initrd.img/{print $5}')

    if [ -z "$kernel_size_bytes" ] || [ "$kernel_size_bytes" -lt 5000000 ]; then
        log_error "Kernel image is too small or missing (${kernel_size_bytes:-0} bytes)."
        exit 1
    fi
    log_success "Kernel size: $(awk "BEGIN {printf \"%.1fM\", $kernel_size_bytes / 1048576}")"

    if [ -z "$initrd_size_bytes" ] || [ "$initrd_size_bytes" -lt 1000000 ]; then
        log_error "Initramfs image is too small or missing (${initrd_size_bytes:-0} bytes)."
        exit 1
    fi
    log_success "Initramfs size: $(awk "BEGIN {printf \"%.1fM\", $initrd_size_bytes / 1048576}")"

    # 8. Check for single kernel version (no stale kernels)
    log_info "Checking for stale kernel files..."
    local vmlinuz_count
    vmlinuz_count=$(xorriso -indev "$ISO_PATH" -find /vmlinuz* -ls 2>/dev/null | grep -c "vmlinuz" || true)
    local initrd_count
    initrd_count=$(xorriso -indev "$ISO_PATH" -find /initrd* -ls 2>/dev/null | grep -c "initrd" || true)
    if [ "$vmlinuz_count" -gt 1 ]; then
        log_warn "Multiple vmlinuz images found ($vmlinuz_count). Only the latest is used."
    fi
    if [ "$initrd_count" -gt 1 ]; then
        log_warn "Multiple initrd images found ($initrd_count). Only the latest is used."
    fi

    log_success "=== ISO Validation Complete: Artifact is structurally sound ==="
}

main "$@"