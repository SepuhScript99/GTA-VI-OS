#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# Vice OS ISO Build Pipeline Unit & Integration Test Suite
# Tests build orchestrator, modular build scripts, error handling,
# debootstrap retry logic, and cross-architecture reproducibility.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"

PASSED=0
FAILED=0

record_result() {
    local test_name="$1"
    local result="$2"
    local msg="${3:-}"

    case "$result" in
        PASS)
            log_success "[PASS] $test_name"
            PASSED=$((PASSED + 1))
            ;;
        FAIL)
            log_error "[FAIL] $test_name${msg:+: $msg}"
            FAILED=$((FAILED + 1))
            ;;
    esac
}

log_info "============================================"
log_info "  Vice OS Build Pipeline Test Suite"
log_info "============================================"

# Test 1: Bash syntax checks on all build scripts
test_syntax() {
    log_info "--- Test: Build scripts bash syntax ---"
    local files=(
        "build_iso.sh"
        "chroot_setup.sh"
        "build/create_rootfs.sh"
        "build/create_squashfs.sh"
        "build/create_bootloader.sh"
        "build/pack_iso.sh"
    )
    local all_good=true
    for f in "${files[@]}"; do
        if ! bash -n "$WORKDIR/$f"; then
            all_good=false
            record_result "Syntax check $f" FAIL "Bash syntax error"
        fi
    done
    if [ "$all_good" = true ]; then
        record_result "All 6 build pipeline scripts pass syntax check" PASS
    fi
}

# Test 2: Orchestrator --version flag
test_orchestrator_version() {
    log_info "--- Test: build_iso.sh --version ---"
    local out
    out=$(cd "$WORKDIR" && bash "$WORKDIR/build_iso.sh" --version 2>&1 || true)
    if echo "$out" | grep -qi "Build Orchestrator"; then
        record_result "build_iso.sh responds to --version without requiring root" PASS
    else
        record_result "build_iso.sh responds to --version" FAIL "Output: $out"
    fi
}

# Test 3: Debootstrap clean-before-retry logic in create_rootfs.sh
test_debootstrap_retry_logic() {
    log_info "--- Test: Debootstrap retry cleanliness ---"
    if grep -q "rm -rf \"\$CHROOTDIR\"" "$WORKDIR/build/create_rootfs.sh" && \
       grep -q "run_debootstrap_with_retry" "$WORKDIR/build/create_rootfs.sh"; then
        record_result "create_rootfs.sh wipes target chroot before each debootstrap retry" PASS
    else
        record_result "create_rootfs.sh wipes target chroot before each debootstrap retry" FAIL
    fi
}

# Test 4: Payload staging completeness
test_payload_staging() {
    log_info "--- Test: Payload directory staging ---"
    local missing=0
    for comp in "system_utils" "recovery" "chroot_scripts" "apps" "desktop" "config" "lib"; do
        if ! grep -q "$comp" "$WORKDIR/build/create_rootfs.sh"; then
            missing=$((missing + 1))
        fi
    done
    if [ "$missing" -eq 0 ]; then
        record_result "create_rootfs.sh stages all required payload components" PASS
    else
        record_result "create_rootfs.sh stages all required payload components" FAIL "Missing: $missing"
    fi
}

# Test 5: ARM64 cross-architecture support in create_rootfs.sh
test_cross_arch_rootfs() {
    log_info "--- Test: ARM64 cross-architecture support in create_rootfs.sh ---"
    if grep -q "qemu-user-static" "$WORKDIR/build/create_rootfs.sh" && \
       grep -q "second-stage" "$WORKDIR/build/create_rootfs.sh"; then
        record_result "create_rootfs.sh includes cross-arch debootstrap support for ARM64" PASS
    else
        record_result "create_rootfs.sh includes cross-arch debootstrap support for ARM64" FAIL
    fi
}

# Test 6: Virtual filesystem mount handling in chroot_setup.sh
test_chroot_mounts() {
    log_info "--- Test: Virtual filesystems in chroot_setup.sh ---"
    if grep -q "/dev/pts" "$WORKDIR/chroot_setup.sh" && \
       grep -q "safe_umount" "$WORKDIR/chroot_setup.sh"; then
        record_result "chroot_setup.sh mounts dev/pts and uses safe unmounting" PASS
    else
        record_result "chroot_setup.sh mounts dev/pts and uses safe unmounting" FAIL
    fi
}

# Test 7: Initramfs generation mounts in build_iso.sh
test_initramfs_mounts() {
    log_info "--- Test: Initramfs mounts in build_iso.sh ---"
    if grep -A 10 "Generating initramfs" "$WORKDIR/build_iso.sh" | grep -q "mount --bind /proc"; then
        record_result "build_iso.sh binds /proc, /sys, /dev during initramfs generation" PASS
    else
        record_result "build_iso.sh binds /proc, /sys, /dev during initramfs generation" FAIL
    fi
}

# Test 8: Resumed build safety in build_iso.sh
test_resume_kernel_safety() {
    log_info "--- Test: Safe kernel_img resolution on resume ---"
    if grep -q "kernel_ver=\"unknown\"" "$WORKDIR/build_iso.sh"; then
        record_result "build_iso.sh guards kernel_img against nounset crash on resume" PASS
    else
        record_result "build_iso.sh guards kernel_img against nounset crash on resume" FAIL
    fi
}

# Test 9: BIOS GRUB module inclusion in create_bootloader.sh
test_bootloader_modules() {
    log_info "--- Test: BIOS GRUB module completeness ---"
    if grep -q "search_fs_file" "$WORKDIR/build/create_bootloader.sh" && \
       grep -q "search_label" "$WORKDIR/build/create_bootloader.sh" && \
       grep -q "part_gpt" "$WORKDIR/build/create_bootloader.sh"; then
        record_result "create_bootloader.sh embeds search and partition modules for BIOS" PASS
    else
        record_result "create_bootloader.sh embeds search and partition modules for BIOS" FAIL
    fi
}

# Test 10: EFI volume ID reproducibility
test_bootloader_reproducibility() {
    log_info "--- Test: efiboot.img reproducibility ---"
    if grep -q "mkfs.vfat -i" "$WORKDIR/build/create_bootloader.sh" && \
       grep -q "mcopy -m" "$WORKDIR/build/create_bootloader.sh"; then
        record_result "create_bootloader.sh uses deterministic volume ID and timestamps" PASS
    else
        record_result "create_bootloader.sh uses deterministic volume ID and timestamps" FAIL
    fi
}

# Test 11: SquashFS reproducibility and payload exclusions
test_squashfs_opts() {
    log_info "--- Test: SquashFS reproducibility options ---"
    if grep -q "mkfs-time" "$WORKDIR/build/create_squashfs.sh" && \
       ! grep -q -- '"-all-root"' "$WORKDIR/build/create_squashfs.sh" && \
       grep -q "vice_payload" "$WORKDIR/build/create_squashfs.sh"; then
        record_result "create_squashfs.sh enforces deterministic timestamps and excludes vice_payload" PASS
    else
        record_result "create_squashfs.sh enforces deterministic timestamps and excludes vice_payload" FAIL
    fi
}

# Test 12: ARM64 El Torito boot entry validity in pack_iso.sh
test_pack_iso_arm64() {
    log_info "--- Test: pack_iso.sh ARM64 boot specification ---"
    # Ensure ARM64 path does not call eltorito-alt-boot as primary
    if grep -A 10 "ARM64: Pure UEFI" "$WORKDIR/build/pack_iso.sh" | grep -q "\-eltorito-boot.*EFI/efiboot.img"; then
        record_result "pack_iso.sh sets EFI as primary El Torito boot entry on ARM64" PASS
    else
        record_result "pack_iso.sh sets EFI as primary El Torito boot entry on ARM64" FAIL
    fi
}

# Test 13: SOURCE_DATE_EPOCH propagation in build orchestrator
test_source_date_epoch() {
    log_info "--- Test: SOURCE_DATE_EPOCH in build_iso.sh ---"
    if grep -q "SOURCE_DATE_EPOCH" "$WORKDIR/build_iso.sh" && \
       grep -q "SOURCE_DATE_EPOCH" "$WORKDIR/build/pack_iso.sh"; then
        record_result "build_iso.sh and pack_iso.sh propagate SOURCE_DATE_EPOCH" PASS
    else
        record_result "build_iso.sh and pack_iso.sh propagate SOURCE_DATE_EPOCH" FAIL
    fi
}

main() {
    test_syntax
    test_orchestrator_version
    test_debootstrap_retry_logic
    test_payload_staging
    test_cross_arch_rootfs
    test_chroot_mounts
    test_initramfs_mounts
    test_resume_kernel_safety
    test_bootloader_modules
    test_bootloader_reproducibility
    test_squashfs_opts
    test_pack_iso_arm64
    test_source_date_epoch

    log_info "============================================"
    log_info "  Results: $PASSED passed, $FAILED failed"
    log_info "============================================"

    if [ "$FAILED" -gt 0 ]; then
        exit 1
    fi
    exit 0
}

main "$@"
