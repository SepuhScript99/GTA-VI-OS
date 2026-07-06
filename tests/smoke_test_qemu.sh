#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) QEMU Smoke Test
# Boots the ISO in a headless QEMU VM to verify it reaches a login prompt.
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
TIMEOUT_SECONDS=90
TEST_DIR=$(mktemp -d)

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    log_info "Cleaning up smoke test environment..."
    # Kill QEMU if it's still running
    if [ -n "${QEMU_PID:-}" ] && kill -0 "$QEMU_PID" 2>/dev/null; then
        kill -9 "$QEMU_PID" 2>/dev/null || true
    fi
    rm -rf "$TEST_DIR"
    
    if [ $exit_code -eq 0 ]; then
        log_success "Smoke test completed successfully."
    else
        log_error "Smoke test failed with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Main ---
main() {
    check_dependencies "qemu-system-x86_64" "xorriso"

    log_info "=== Starting QEMU Smoke Test ==="

    if [ ! -f "$ISO_PATH" ]; then
        log_error "ISO file not found: $ISO_PATH"
        exit 1
    fi

    log_info "Extracting kernel and initrd from ISO for direct boot..."
    xorriso -osirrox on -indev "$ISO_PATH" -extract /vmlinuz "$TEST_DIR/vmlinuz" -extract /initrd.img "$TEST_DIR/initrd.img" >/dev/null 2>&1

    if [ ! -f "$TEST_DIR/vmlinuz" ] || [ ! -f "$TEST_DIR/initrd.img" ]; then
        log_error "Failed to extract kernel/initrd from ISO."
        exit 1
    fi

    local log_file="$TEST_DIR/qemu_console.log"
    log_info "Booting QEMU (Timeout: ${TIMEOUT_SECONDS}s)..."

    # Run QEMU in the background, redirecting serial console to log file
    # -append passes kernel command line args directly, bypassing GRUB for a faster, headless test
    qemu-system-x86_64 \
        -m 2048 \
        -kernel "$TEST_DIR/vmlinuz" \
        -initrd "$TEST_DIR/initrd.img" \
        -append "boot=live quiet loglevel=3 console=ttyS0 root=live:LABEL=VICE_OS" \
        -cdrom "$ISO_PATH" \
        -nographic \
        -serial file:"$log_file" \
        -display none \
        &
    
    QEMU_PID=$!

    # Wait for the login prompt or Openbox to appear in the log
    local elapsed=0
    while [ $elapsed -lt $TIMEOUT_SECONDS ]; do
        if [ -f "$log_file" ]; then
            # Look for standard agetty login prompt or our custom shell startup
            if grep -q "login:" "$log_file" || grep -q "VICE OS" "$log_file"; then
                log_success "Boot successful! Login prompt reached."
                exit 0
            fi
            # Check for kernel panic
            if grep -qi "Kernel panic" "$log_file"; then
                log_error "Kernel panic detected during boot!"
                cat "$log_file" >&2
                exit 1
            fi
        fi
        sleep 2
        elapsed=$((elapsed + 2))
    done

    log_error "Timeout reached. Boot did not complete in ${TIMEOUT_SECONDS} seconds."
    if [ -f "$log_file" ]; then
        log_warn "--- QEMU Console Output ---"
        cat "$log_file" >&2 || true
    fi
    exit 1
}

main "$@"