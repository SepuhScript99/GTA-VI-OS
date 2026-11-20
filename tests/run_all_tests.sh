#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# Vice OS Comprehensive Test Suite Runner
# Executes all unit and integration test suites:
#   - Python unit tests (tests/test_vice_utils.py, tests/test_desktop.py)
#   - Common shared library test suite (tests/test_common_sh.sh)
#   - System utilities test suite (tests/test_system_utils.sh)
#   - Apps & installer test suite (tests/test_apps.sh)
#   - Recovery suite (tests/test_recovery_suite.sh)
#   - Build pipeline test suite (tests/test_build_pipeline.sh)
#   - Validation integration test suite (tests/test_validation.sh)
#   - Chroot scripts & config test suite (tests/test_chroot_scripts.sh)
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

TOTAL_SUITES=0
PASSED_SUITES=0
FAILED_SUITES=0

run_suite() {
    local name="$1"
    local cmd="$2"

    TOTAL_SUITES=$((TOTAL_SUITES + 1))
    echo ""
    log_info "============================================================"
    log_info "  Starting Test Suite: $name"
    log_info "============================================================"

    if eval "$cmd"; then
        log_success "[SUITE PASS] $name"
        PASSED_SUITES=$((PASSED_SUITES + 1))
    else
        log_error "[SUITE FAIL] $name"
        FAILED_SUITES=$((FAILED_SUITES + 1))
    fi
}

main() {
    log_info "############################################################"
    log_info "       Vice OS Full Test Suite Orchestrator"
    log_info "############################################################"

    # 1. Python Unit Tests
    run_suite "Python Unit Tests (test_vice_utils, test_desktop)" \
        "python3 -m unittest discover -s \"$WORKDIR/tests\" -p 'test_*.py' -v || python -m unittest discover -s \"$WORKDIR/tests\" -p 'test_*.py' -v"

    # 2. Shared Library Tests
    if [ -f "$WORKDIR/tests/test_common_sh.sh" ]; then
        run_suite "Common Library Tests (test_common_sh.sh)" \
            "bash \"$WORKDIR/tests/test_common_sh.sh\""
    fi

    # 3. System Utilities Tests
    if [ -f "$WORKDIR/tests/test_system_utils.sh" ]; then
        run_suite "System Utilities Syntax & Structure (test_system_utils.sh)" \
            "bash \"$WORKDIR/tests/test_system_utils.sh\""
    fi

    # 4. Apps & Installer Tests
    if [ -f "$WORKDIR/tests/test_apps.sh" ]; then
        run_suite "Apps & Installer Suite (test_apps.sh)" \
            "bash \"$WORKDIR/tests/test_apps.sh\""
    fi

    # 5. Recovery Suite Tests
    if [ -f "$WORKDIR/tests/test_recovery_suite.sh" ]; then
        run_suite "System Recovery Suite (test_recovery_suite.sh)" \
            "bash \"$WORKDIR/tests/test_recovery_suite.sh\""
    fi

    # 6. Build Pipeline Tests
    if [ -f "$WORKDIR/tests/test_build_pipeline.sh" ]; then
        run_suite "Build Pipeline Suite (test_build_pipeline.sh)" \
            "bash \"$WORKDIR/tests/test_build_pipeline.sh\""
    fi

    # 7. Validation Integration Tests
    if [ -f "$WORKDIR/tests/test_validation.sh" ]; then
        run_suite "Validation Integration Suite (test_validation.sh)" \
            "bash \"$WORKDIR/tests/test_validation.sh\""
    fi

    # 8. Chroot Scripts & System Configuration Tests
    if [ -f "$WORKDIR/tests/test_chroot_scripts.sh" ]; then
        run_suite "Chroot Scripts & Configuration Suite (test_chroot_scripts.sh)" \
            "bash \"$WORKDIR/tests/test_chroot_scripts.sh\""
    fi

    echo ""
    log_info "############################################################"
    log_info "  Summary: $PASSED_SUITES / $TOTAL_SUITES suites passed ($FAILED_SUITES failed)"
    log_info "############################################################"

    if [ "$FAILED_SUITES" -gt 0 ]; then
        exit 1
    fi
}

main "$@"
