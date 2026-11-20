#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# Vice OS Common Bash Library Test Suite
# Tests the shared functions in lib/common.sh:
#   - bootstrap_script, init_script, install_cleanup
#   - retry_command, get_timestamp
#   - log_info, log_warn, log_error, log_success
#   - check_root, check_dependencies, check_command
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Source the library to test (not through bootstrap_script since we're testing it)
source "$WORKDIR/lib/common.sh"

PASSED=0
FAILED=0
SKIPPED=0

record_result() {
    local test_name="$1"
    local result="$2"
    local message="${3:-}"
    case "$result" in
        PASS)
            log_success "[PASS] $test_name"
            PASSED=$((PASSED + 1))
            ;;
        FAIL)
            log_error "[FAIL] $test_name${message:+: $message}"
            FAILED=$((FAILED + 1))
            ;;
        SKIP)
            log_info "[SKIP] $test_name${message:+: $message}"
            SKIPPED=$((SKIPPED + 1))
            ;;
    esac
}

# --- Test: get_timestamp ---

test_timestamp_format() {
    local ts
    ts=$(get_timestamp)
    # Expected format: YYYY-MM-DD_HH-MM-SS (e.g., 2026-07-24_14-30-00)
    if [[ "$ts" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{2}-[0-9]{2}-[0-9]{2}$ ]]; then
        record_result "get_timestamp format" PASS
    else
        record_result "get_timestamp format" FAIL "got: $ts"
    fi
}

test_timestamp_reproducible() {
    local ts1 ts2
    ts1=$(get_timestamp)
    sleep 1
    ts2=$(get_timestamp)
    if [ "$ts1" != "$ts2" ]; then
        record_result "get_timestamp changes each second" PASS
    else
        record_result "get_timestamp changes each second" FAIL "timestamps identical"
    fi
}

# --- Test: retry_command ---

test_retry_success() {
    if retry_command 3 1 true; then
        record_result "retry_command succeeds on success" PASS
    else
        record_result "retry_command succeeds on success" FAIL
    fi
}

test_retry_failure() {
    if retry_command 2 1 false 2>/dev/null; then
        record_result "retry_command fails on persistent failure" FAIL "should have failed"
    else
        record_result "retry_command fails on persistent failure" PASS
    fi
}

test_retry_eventually_succeeds() {
    local count=0
    local func
    func() { count=$((count + 1)); [ "$count" -ge 2 ]; }
    if retry_command 3 1 func; then
        record_result "retry_command retries then succeeds" PASS
    else
        record_result "retry_command retries then succeeds" FAIL
    fi
}

# --- Test: bootstrap_script ---

test_bootstrap_returns_workdir() {
    # Use the real tests/ directory so init_script resolves to the repo root
    # where lib/common.sh actually exists (init_script exits 1 if common.sh
    # is not found at the resolved path).
    local result
    result=$(init_script "$WORKDIR/tests")
    if echo "$result" | grep -qF "WORKDIR=\"$WORKDIR\""; then
        record_result "init_script resolves WORKDIR" PASS
    else
        record_result "init_script resolves WORKDIR" FAIL "got: $result"
    fi
}

test_bootstrap_rejects_direct_execution() {
    # Running common.sh directly should exit with error
    if bash "$WORKDIR/lib/common.sh" 2>/dev/null; then
        record_result "common.sh rejects direct execution" FAIL "should have failed"
    else
        record_result "common.sh rejects direct execution" PASS
    fi
}

# --- Test: check_command ---

test_check_command_exists() {
    if check_command "bash" 2>/dev/null; then
        record_result "check_command finds existing command" PASS
    else
        record_result "check_command finds existing command" FAIL
    fi
}

test_check_command_missing() {
    if check_command "nonexistent_command_xyz" 2>/dev/null; then
        record_result "check_command rejects missing command" FAIL "should have failed"
    else
        record_result "check_command rejects missing command" PASS
    fi
}

# --- Test: Logging functions (don't crash) ---

test_logging_no_crash() {
    log_info "Test info message" > /dev/null 2>&1
    log_success "Test success message" > /dev/null 2>&1
    log_warn "Test warn message" > /dev/null 2>&1
    log_error "Test error message" > /dev/null 2>&1
    record_result "Logging functions produce no errors" PASS
}

test_logging_with_logfile() {
    local tmpfile
    tmpfile=$(mktemp)
    LOG_FILE="$tmpfile" log_info "Write test" > /dev/null 2>&1
    if grep -q "Write test" "$tmpfile" 2>/dev/null; then
        record_result "Logging writes to LOG_FILE" PASS
    else
        record_result "Logging writes to LOG_FILE" FAIL
    fi
    rm -f "$tmpfile"
}

# --- Run all tests ---

main() {
    log_info "============================================"
    log_info "  Vice OS Common Library Test Suite"
    log_info "============================================"
    echo ""

    test_timestamp_format
    test_timestamp_reproducible
    test_retry_success
    test_retry_failure
    test_retry_eventually_succeeds
    test_bootstrap_returns_workdir
    test_bootstrap_rejects_direct_execution
    test_check_command_exists
    test_check_command_missing
    test_logging_no_crash
    test_logging_with_logfile

    echo ""
    log_info "============================================"
    log_info "  Results: $PASSED passed, $FAILED failed, $SKIPPED skipped"
    log_info "============================================"

    if [ "$FAILED" -gt 0 ]; then
        exit 1
    fi
}

main "$@"
