#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# Vice OS Apps & Installer Test Suite
# Tests apps/vp-installer.sh, apps/vp-code.sh, apps/vp-docker.sh
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -f "$WORKDIR/lib/common.sh" ]; then
    source "$WORKDIR/lib/common.sh"
elif [ -f "/usr/local/lib/common.sh" ]; then
    source "/usr/local/lib/common.sh"
else
    echo "Error: common.sh library not found." >&2
    exit 1
fi

PASSED=0
FAILED=0

record_result() {
    local test_name="$1"
    local result="$2"
    local message="${3:-}"
    if [ "$result" = "PASS" ]; then
        log_success "[PASS] $test_name"
        PASSED=$((PASSED + 1))
    else
        log_error "[FAIL] $test_name${message:+: $message}"
        FAILED=$((FAILED + 1))
    fi
}

log_info "============================================"
log_info "  Vice OS Apps & Installer Test Suite"
log_info "============================================"

# Test 1: Bash syntax validation
for script in "apps/vp-installer.sh" "apps/vp-code.sh" "apps/vp-docker.sh"; do
    if [ -f "$WORKDIR/$script" ]; then
        if bash -n "$WORKDIR/$script"; then
            record_result "Syntax check: $script" PASS
        else
            record_result "Syntax check: $script" FAIL "Syntax error detected"
        fi
    else
        record_result "Syntax check: $script" FAIL "File does not exist"
    fi
done

# Test 2: CLI flag execution (--help and --version)
for script in "apps/vp-installer.sh" "apps/vp-code.sh" "apps/vp-docker.sh"; do
    if [ -f "$WORKDIR/$script" ]; then
        help_out=$("$WORKDIR/$script" --help 2>&1 || true)
        if echo "$help_out" | grep -qi "usage"; then
            record_result "$script --help returns usage" PASS
        else
            record_result "$script --help returns usage" FAIL
        fi

        ver_out=$("$WORKDIR/$script" --version 2>&1 || true)
        if echo "$ver_out" | grep -qi "v[0-9]"; then
            record_result "$script --version returns version" PASS
        else
            record_result "$script --version returns version" FAIL
        fi
    fi
done

# Test 3: Zero Data-Loss Safeguard Verification in vp-installer.sh
INSTALLER="$WORKDIR/apps/vp-installer.sh"
if grep -q "is_live_media" "$INSTALLER" && grep -q "LIVE BOOT MEDIA" "$INSTALLER"; then
    record_result "vp-installer: Live media detection & protection" PASS
else
    record_result "vp-installer: Live media detection & protection" FAIL
fi

if grep -q "safely_unmount_disk" "$INSTALLER" && grep -q "swapoff" "$INSTALLER"; then
    record_result "vp-installer: Safe partition unmounting & swap deactivation" PASS
else
    record_result "vp-installer: Safe partition unmounting & swap deactivation" FAIL
fi

if grep -q "check_disk_capacity" "$INSTALLER"; then
    record_result "vp-installer: Disk capacity validation" PASS
else
    record_result "vp-installer: Disk capacity validation" FAIL
fi

# Test 4: LUKS2 Encryption and Boot Partition Layout
if grep -q "Vice-Boot" "$INSTALLER" && grep -q "Vice-Root" "$INSTALLER" && grep -q "luksFormat --type luks2" "$INSTALLER"; then
    record_result "vp-installer: LUKS2 container with dedicated /boot partition" PASS
else
    record_result "vp-installer: LUKS2 container with dedicated /boot partition" FAIL
fi

# Test 5: Secure Credential Piping (Zero Shell Injection)
if grep -q 'printf .*%s\\n.*|.*chroot.*chpasswd' "$INSTALLER"; then
    record_result "vp-installer: Secure chpasswd stdin piping (no shell injection)" PASS
else
    record_result "vp-installer: Secure chpasswd stdin piping (no shell injection)" FAIL
fi

# Test 6: Sudoers Configuration & Visudo Validation
if grep -q 'Defaults secure_path=' "$INSTALLER" && grep -q 'visudo -cf' "$INSTALLER"; then
    record_result "vp-installer: Password-protected sudoers & visudo validation" PASS
else
    record_result "vp-installer: Password-protected sudoers & visudo validation" FAIL
fi

# Test 7: Post-Install Hardening Hooks
if grep -q "systemd-machine-id-setup" "$INSTALLER" && grep -q "ssh-keygen -A" "$INSTALLER"; then
    record_result "vp-installer: Machine-ID and SSH host keys regeneration" PASS
else
    record_result "vp-installer: Machine-ID and SSH host keys regeneration" FAIL
fi

if grep -q "run_post_install_hooks" "$INSTALLER"; then
    record_result "vp-installer: Extensible post-install hooks runner" PASS
else
    record_result "vp-installer: Extensible post-install hooks runner" FAIL
fi

# Test 8: Dynamic Repository Generation in vp-docker.sh
DOCKER_SH="$WORKDIR/apps/vp-docker.sh"
if grep -q 'dpkg --print-architecture' "$DOCKER_SH" && grep -q 'download.docker.com' "$DOCKER_SH"; then
    record_result "vp-docker: Dynamic architecture and apt repository generation" PASS
else
    record_result "vp-docker: Dynamic architecture and apt repository generation" FAIL
fi

# Test 9: Concurrency Lockfile Protection
for script in "apps/vp-installer.sh" "apps/vp-code.sh" "apps/vp-docker.sh"; do
    if grep -q 'flock -n 9' "$WORKDIR/$script"; then
        record_result "$script: Concurrency flock protection" PASS
    else
        record_result "$script: Concurrency flock protection" FAIL
    fi
done

log_info "============================================"
log_info "  Results: $PASSED passed, $FAILED failed"
log_info "============================================"

if [ "$FAILED" -gt 0 ]; then
    exit 1
fi
exit 0
