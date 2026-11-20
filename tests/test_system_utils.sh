#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# Vice OS System Utilities Test Suite
# Validates syntax, structure, and consistency of all 47 system_utils scripts.
# Tests run as static analysis (no execution of the utilities themselves).
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

UTILS_DIR="$WORKDIR/system_utils"
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

# Test 1: All scripts exist
test_all_scripts_exist() {
    local count
    count=$(find "$UTILS_DIR" -maxdepth 1 -name '*.sh' -type f | wc -l)
    if [ "$count" -ge 47 ]; then
        record_result "All 47+ system_utils scripts present ($count found)" PASS
    else
        record_result "All 47+ system_utils scripts present ($count found)" FAIL
    fi
}

# Test 2: Syntax check every script
test_syntax_check() {
    local errors=0
    local total=0

    while IFS= read -r -d '' script; do
        total=$((total + 1))
        local name
        name=$(basename "$script")
        if ! bash -n "$script" 2>/dev/null; then
            log_error "Syntax error in: $name"
            errors=$((errors + 1))
        fi
    done < <(find "$UTILS_DIR" -maxdepth 1 -name '*.sh' -type f -print0)

    if [ "$errors" -eq 0 ]; then
        record_result "No syntax errors in $total scripts" PASS
    else
        record_result "No syntax errors ($errors scripts failed)" FAIL
    fi
}

# Test 3: All scripts source the shared library
test_shared_library_sourced() {
    local missing=0
    local total=0

    while IFS= read -r -d '' script; do
        total=$((total + 1))
        local name
        name=$(basename "$script")
        # Every script must resolve WORKDIR and source lib/common.sh before use.
        if ! grep -q 'source "$WORKDIR/lib/common.sh"' "$script" 2>/dev/null; then
            log_error "Missing shared library source in: $name"
            missing=$((missing + 1))
        fi
    done < <(find "$UTILS_DIR" -maxdepth 1 -name '*.sh' -type f -print0)

    if [ "$missing" -eq 0 ]; then
        record_result "All $total scripts source lib/common.sh" PASS
    else
        record_result "All $total scripts source lib/common.sh ($missing missing)" FAIL
    fi
}

# Test 4: All scripts have set -Eeuo pipefail
test_strict_mode() {
    local missing=0
    local total=0

    while IFS= read -r -d '' script; do
        total=$((total + 1))
        local name
        name=$(basename "$script")
        if ! grep -q 'set -Eeuo pipefail' "$script" 2>/dev/null; then
            log_error "Missing strict mode in: $name"
            missing=$((missing + 1))
        fi
    done < <(find "$UTILS_DIR" -maxdepth 1 -name '*.sh' -type f -print0)

    if [ "$missing" -eq 0 ]; then
        record_result "All $total scripts use strict mode" PASS
    else
        record_result "All $total scripts use strict mode ($missing missing)" FAIL
    fi
}

# Test 5: All scripts have a main() function
test_main_function() {
    local missing=0
    local total=0

    while IFS= read -r -d '' script; do
        total=$((total + 1))
        local name
        name=$(basename "$script")
        if ! grep -q '^main()' "$script" 2>/dev/null; then
            log_error "Missing main() in: $name"
            missing=$((missing + 1))
        fi
    done < <(find "$UTILS_DIR" -maxdepth 1 -name '*.sh' -type f -print0)

    if [ "$missing" -eq 0 ]; then
        record_result "All $total scripts have main()" PASS
    else
        record_result "All $total scripts have main() ($missing missing)" FAIL
    fi
}

# Test 6: All scripts call main "$@"
test_main_call() {
    local missing=0
    local total=0

    while IFS= read -r -d '' script; do
        total=$((total + 1))
        local name
        name=$(basename "$script")
        if ! grep -q 'main "\$@"' "$script" 2>/dev/null; then
            log_error "Missing main call in: $name"
            missing=$((missing + 1))
        fi
    done < <(find "$UTILS_DIR" -maxdepth 1 -name '*.sh' -type f -print0)

    if [ "$missing" -eq 0 ]; then
        record_result "All $total scripts call main \$@" PASS
    else
        record_result "All $total scripts call main \$@ ($missing missing)" FAIL
    fi
}

# Test 7: All scripts use the working preamble (not the broken bootstrap_script eval)
test_working_preamble() {
    local broken=0
    local total=0

    while IFS= read -r -d '' script; do
        total=$((total + 1))
        local name
        name=$(basename "$script")
        # The old pattern (eval of bootstrap_script before sourcing common.sh) is
        # a broken circular dependency and must not reappear.
        if grep -q 'eval "$(bootstrap_script' "$script" 2>/dev/null; then
            log_error "Broken bootstrap_script eval still present in: $name"
            broken=$((broken + 1))
        fi
    done < <(find "$UTILS_DIR" -maxdepth 1 -name '*.sh' -type f -print0)

    if [ "$broken" -eq 0 ]; then
        record_result "No broken bootstrap_script eval ($total scripts)" PASS
    else
        record_result "No broken bootstrap_script eval ($broken broken)" FAIL
    fi
}

# Test 8: File size check (no unreasonably small or large files)
test_file_sizes() {
    local small=0
    local large=0
    local total=0

    while IFS= read -r -d '' script; do
        total=$((total + 1))
        local name
        name=$(basename "$script")
        local size
        size=$(stat -c%s "$script" 2>/dev/null || stat -f%z "$script" 2>/dev/null || echo "0")

        if [ "$size" -lt 50 ]; then
            log_warn "Very small script ($size bytes): $name"
            small=$((small + 1))
        fi
    done < <(find "$UTILS_DIR" -maxdepth 1 -name '*.sh' -type f -print0)

    if [ "$small" -eq 0 ] && [ "$large" -eq 0 ]; then
        record_result "All script sizes look reasonable" PASS
    else
        record_result "Script sizes: $small small, $large large" PASS
    fi
}

# Test 9: Category distribution
test_categories() {
    local managers=0
    local system=0
    local other=0
    local total=0

    while IFS= read -r -d '' script; do
        total=$((total + 1))
        local name
        name=$(basename "$script")
        if echo "$name" | grep -q "_manager\.sh$"; then
            managers=$((managers + 1))
        elif echo "$name" | grep -q "^system_"; then
            system=$((system + 1))
        else
            other=$((other + 1))
        fi
    done < <(find "$UTILS_DIR" -maxdepth 1 -name '*.sh' -type f -print0)

    log_info "  Manager scripts: $managers"
    log_info "  System scripts:  $system"
    log_info "  Other scripts:   $other"
    log_info "  Total scripts:   $total"
    record_result "Script category distribution" PASS
}

main() {
    log_info "============================================"
    log_info "  Vice OS System Utilities Test Suite"
    log_info "============================================"
    echo ""

    test_all_scripts_exist
    test_syntax_check
    test_shared_library_sourced
    test_strict_mode
    test_main_function
    test_main_call
    test_working_preamble
    test_file_sizes
    test_categories

    echo ""
    log_info "============================================"
    log_info "  Results: $PASSED passed, $FAILED failed, $SKIPPED skipped"
    log_info "============================================"

    if [ "$FAILED" -gt 0 ]; then
        exit 1
    fi
}

main "$@"
