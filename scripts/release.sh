#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# Vice OS Release Automation Script
# Validates pre-release checklist, builds ISO, and creates GitHub release.
# Usage: bash scripts/release.sh <version> [--dry-run]
# Example: bash scripts/release.sh v1.0.0
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

DRY_RUN=false
VERSION=""
EXIT_CODE=0

check_fail() {
    local step="$1"
    local message="$2"
    log_error "[FAIL] $step: $message"
    EXIT_CODE=1
}

pass_fail() {
    local step="$1"
    if [ $? -eq 0 ]; then
        log_success "[PASS] $step"
    else
        check_fail "$step" "Check failed"
    fi
}

main() {
    if [ $# -lt 1 ] || [ "${1:-}" == "--help" ] || [ "${1:-}" == "-h" ]; then
        echo "Vice OS Release Automation Script"
        echo ""
        echo "Usage: bash $0 <version> [--dry-run]"
        echo ""
        echo "Arguments:"
        echo "  <version>   Release version (e.g., v1.0.0)"
        echo "  --dry-run   Run pre-release checks without creating a release"
        echo ""
        echo "Examples:"
        echo "  bash $0 v1.0.0"
        echo "  bash $0 v1.0.0 --dry-run"
        exit 0
    fi

    VERSION="$1"
    shift || true

    if [ "${1:-}" == "--dry-run" ]; then
        DRY_RUN=true
        log_info "=== DRY RUN — No changes will be made ==="
    fi

    log_info "=== Vice OS Release: $VERSION ==="
    echo ""

    # ── Pre-Release Checklist ──
    log_info "--- Pre-Release Checklist ---"

    # 1. Git working tree clean
    log_info "Checking git working tree..."
    if command -v git > /dev/null 2>&1; then
        if [ -z "$(git status --porcelain 2>/dev/null)" ]; then
            log_success "[PASS] Git working tree is clean."
        else
            check_fail "Git working tree" "Uncommitted changes found. Commit or stash them first."
        fi
    else
        log_warn "git not available. Skipping working tree check."
    fi

    # 2. Version files match
    log_info "Checking version consistency..."
    local os_release_version
    local lsb_release_version
    os_release_version=$(grep "^VERSION_ID=" "$WORKDIR/config/os-release" 2>/dev/null | cut -d= -f2 | tr -d '"' || echo "")
    lsb_release_version=$(grep "^DISTRIB_RELEASE=" "$WORKDIR/config/lsb-release" 2>/dev/null | cut -d= -f2 || echo "")
    if [ "$os_release_version" = "${VERSION#v}" ]; then
        log_success "[PASS] os-release version matches: $os_release_version"
    else
        check_fail "os-release" "Version mismatch: VERSION_ID=$os_release_version, expected ${VERSION#v}"
    fi
    if [ "$lsb_release_version" = "${VERSION#v}" ]; then
        log_success "[PASS] lsb-release version matches: $lsb_release_version"
    else
        check_fail "lsb-release" "Version mismatch: DISTRIB_RELEASE=$lsb_release_version, expected ${VERSION#v}"
    fi

    # 3. Changelog has unreleased entry for this version
    log_info "Checking changelog..."
    if grep -q "^## \[${VERSION#v}\]" "$WORKDIR/docs/CHANGELOG.md" 2>/dev/null; then
        log_success "[PASS] Changelog has entry for ${VERSION#v}."
    else
        check_fail "Changelog" "No entry found for [${VERSION#v}] in CHANGELOG.md."
    fi

    # 4. Unit tests pass
    log_info "Running unit tests..."
    if python3 -m unittest discover -s "$WORKDIR/tests" -v 2>&1; then
        log_success "[PASS] All unit tests pass."
    else
        check_fail "Unit tests" "One or more unit tests failed."
    fi

    # 5. Validation tests pass
    log_info "Running validation integration tests..."
    if bash "$WORKDIR/tests/test_validation.sh" 2>&1; then
        log_success "[PASS] All integration tests pass."
    else
        check_fail "Integration tests" "One or more integration tests failed."
    fi

    # 6. Build dependencies available
    log_info "Checking build dependencies..."
    local deps=("debootstrap" "grub-mkstandalone" "xorriso" "mksquashfs" "mcopy" "mkfs.vfat")
    local missing=0
    for dep in "${deps[@]}"; do
        if ! command -v "$dep" > /dev/null 2>&1; then
            log_warn "Missing build dependency: $dep"
            missing=$((missing + 1))
        fi
    done
    if [ "$missing" -eq 0 ]; then
        log_success "[PASS] All build dependencies present."
    else
        check_fail "Build dependencies" "$missing missing dependencies."
    fi

    echo ""
    if [ "$EXIT_CODE" -ne 0 ]; then
        log_error "Pre-release checklist has $EXIT_CODE failure(s)."
        log_error "Fix the issues above before creating a release."
        exit $EXIT_CODE
    fi

    if $DRY_RUN; then
        log_success "Dry run complete. All pre-release checks pass."
        exit 0
    fi

    # ── Release Steps ──
    log_info "--- Creating Release: $VERSION ---"

    # Build ISO (clean build)
    log_info "Building ISO (clean build)..."
    if ! bash "$WORKDIR/build_iso.sh" --clean; then
        log_error "ISO build failed."
        exit 1
    fi
    log_success "ISO build complete."

    # Validate ISO
    log_info "Validating ISO..."
    if ! bash "$WORKDIR/tests/validate_iso.sh" "$WORKDIR/out/gta-vi-os-amd64.iso"; then
        log_error "ISO validation failed."
        exit 1
    fi
    log_success "ISO validation passed."

    # Create git tag
    if command -v git > /dev/null 2>&1; then
        log_info "Creating git tag: $VERSION..."
        if git tag -a "$VERSION" -m "Release $VERSION Stable"; then
            log_success "Git tag created: $VERSION"
            log_info "Push with: git push origin $VERSION"
        else
            log_error "Failed to create git tag."
            exit 1
        fi
    fi

    log_success "=== Release $VERSION ready ==="
    echo ""
    log_info "Next steps:"
    log_info "  1. Push tag: git push origin $VERSION"
    log_info "  2. Create GitHub Release with artifact: $WORKDIR/out/gta-vi-os-amd64.iso"
    log_info "  3. Upload SHA256SUMS and build_info.txt from $WORKDIR/out/"
}

main "$@"
