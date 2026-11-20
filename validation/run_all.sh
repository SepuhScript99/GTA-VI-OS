#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# Vice OS Validation Suite Runner
# Runs all validation scripts. Can be used standalone or as a CI step.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

CHROOTDIR="${1:-$WORKDIR/chroot}"
ISODIR="${2:-$WORKDIR/out}"

PASSED=0
FAILED=0
SKIPPED=0

run_validator() {
    local name="$1"
    local script="$2"
    shift 2

    if [ ! -f "$script" ]; then
        log_error "Validator not found: $script"
        FAILED=$((FAILED + 1))
        return
    fi

    log_info "--- Running: $name ---"
    if bash "$script" "$@" > /dev/null 2>&1; then
        log_success "[PASS] $name"
        PASSED=$((PASSED + 1))
    else
        log_error "[FAIL] $name (exit code: $?)"
        FAILED=$((FAILED + 1))
    fi
}

main() {
    log_info "============================================"
    log_info "  Vice OS Validation Suite"
    log_info "============================================"
    echo ""

    run_validator "Package List Validator" "$WORKDIR/validation/validate_packages.sh"

    if [ -d "$CHROOTDIR" ]; then
        run_validator "RootFS Validator" "$WORKDIR/validation/validate_rootfs.sh" "$CHROOTDIR"
        run_validator "Kernel Validator" "$WORKDIR/validation/validate_kernel.sh" "$CHROOTDIR"
        run_validator "Initramfs Validator" "$WORKDIR/validation/validate_initramfs.sh" "$CHROOTDIR"
    else
        log_warn "Chroot directory not found. Skipping chroot-dependent validators."
        SKIPPED=$((SKIPPED + 3))
    fi

    local iso_file=""
    if [ -d "$ISODIR" ]; then
        iso_file=$(find "$ISODIR" -name "*.iso" -type f 2>/dev/null | head -n 1 || true)
    fi
    if [ -n "$iso_file" ] && [ -f "$iso_file" ]; then
        run_validator "ISO Validator" "$WORKDIR/validation/validate_iso.sh" "$iso_file"
    else
        log_warn "No ISO found in $ISODIR. Skipping ISO validator."
        SKIPPED=$((SKIPPED + 1))
    fi

    echo ""
    log_info "============================================"
    log_info "  Results: $PASSED passed, $FAILED failed, $SKIPPED skipped"
    log_info "============================================"

    if [ "$FAILED" -gt 0 ]; then
        exit 1
    fi
}

main "$@"