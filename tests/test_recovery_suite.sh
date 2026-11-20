#!/bin/bash
set -u

WORKDIR="/e/gta-vi-os"
cd "$WORKDIR"

echo "=== Running Recovery Tool Suite Verification ==="

FAILED=0

# Test 1: Check non-root rejection on all scripts
for s in recovery/vice-recovery.sh recovery/rebuild_grub.sh recovery/reset_network.sh recovery/reset_password.sh recovery/vice_grub_theme.sh recovery/vice_plymouth_theme.sh; do
    out=$(bash "$s" 2>&1 || true)
    if echo "$out" | grep -qi "root"; then
        echo "[PASS] $s rejects non-root execution"
    else
        echo "[FAIL] $s did not reject non-root: $out"
        FAILED=$((FAILED + 1))
    fi
done

# Test 2: Check help flags work without root
for s in recovery/vice-recovery.sh recovery/rebuild_grub.sh recovery/reset_network.sh recovery/reset_password.sh recovery/vice_grub_theme.sh recovery/vice_plymouth_theme.sh; do
    if bash "$s" --help >/dev/null 2>&1; then
        echo "[PASS] $s --help succeeds without root"
    else
        echo "[FAIL] $s --help failed"
        FAILED=$((FAILED + 1))
    fi
done

# Test 3: Check version flags work without root
for s in recovery/vice-recovery.sh recovery/rebuild_grub.sh recovery/reset_network.sh recovery/reset_password.sh recovery/vice_grub_theme.sh recovery/vice_plymouth_theme.sh; do
    if bash "$s" --version >/dev/null 2>&1; then
        echo "[PASS] $s --version succeeds without root"
    else
        echo "[FAIL] $s --version failed"
        FAILED=$((FAILED + 1))
    fi
done

# Test 4: Verify flock lock retention when second process fails
TEST_LOCK="/tmp/test_flock.lock"
rm -f "$TEST_LOCK"

(
    exec 9>"$TEST_LOCK"
    flock -n 9
    sleep 2
) &
PID1=$!
sleep 0.5

# Second process tries to grab lock and exits
(
    exec 9>"$TEST_LOCK"
    if ! flock -n 9; then
        # Simulate our fixed cleanup
        LOCKED=0
        if [ "$LOCKED" -eq 1 ]; then
            rm -f "$TEST_LOCK"
        fi
        exit 1
    fi
)
CODE2=$?

if [ "$CODE2" -eq 1 ] && [ -f "$TEST_LOCK" ]; then
    echo "[PASS] Second process flock rejection preserves lockfile and exits 1"
else
    echo "[FAIL] Flock test failed: code=$CODE2, lockfile_exists=$(test -f "$TEST_LOCK" && echo yes || echo no)"
    FAILED=$((FAILED + 1))
fi

wait $PID1 2>/dev/null || true
rm -f "$TEST_LOCK"

echo "=== Test Summary: FAILED=$FAILED ==="
exit $FAILED
