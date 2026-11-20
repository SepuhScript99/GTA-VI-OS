#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# Vice OS Package List Validator
# Validates config/packages.list for correctness, duplicates, and availability.
# Can be run standalone or as part of the CI pipeline.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

PACKAGE_LIST="$WORKDIR/config/packages.list"
EXIT_CODE=0

main() {
    log_info "=== Validating Package List ==="

    if [ ! -f "$PACKAGE_LIST" ]; then
        log_error "Package list not found: $PACKAGE_LIST"
        exit 1
    fi

    # Extract non-comment, non-empty lines
    local packages=()
    while IFS= read -r line; do
        line="${line%%#*}"
        line="${line// /}"
        if [ -n "$line" ]; then
            packages+=("$line")
        fi
    done < "$PACKAGE_LIST"

    local total=${#packages[@]}
    log_info "Total packages to validate: $total"

    # 1. Check for duplicate entries
    local duplicates
    duplicates=$(printf '%s\n' "${packages[@]}" | sort | uniq -d)
    if [ -n "$duplicates" ]; then
        log_error "Duplicate packages found:"
        echo "$duplicates" | while IFS= read -r dup; do
            log_error "  Duplicate: $dup"
        done
        EXIT_CODE=1
    else
        log_success "No duplicate packages."
    fi

    # 2. Check for empty package names
    for pkg in "${packages[@]}"; do
        if [[ ! "$pkg" =~ ^[a-zA-Z0-9][a-zA-Z0-9+.\-]*$ ]]; then
            log_error "Invalid package name format: '$pkg'"
            EXIT_CODE=1
        fi
    done

    # 3. Check for missing dependencies (packages that are referenced by other configs)
    local missing_refs=0

    # Check if firefox-esr is installed when firefox.desktop is referenced
    if printf '%s\n' "${packages[@]}" | grep -q "^firefox-esr$"; then
        log_info "  firefox-esr present (matches mimeapps.list references)."
    fi

    # Check for thunar (file manager)
    if ! printf '%s\n' "${packages[@]}" | grep -q "^thunar$"; then
        log_error "Missing package: thunar (required by openbox_rc.xml and mimeapps.list)"
        missing_refs=$((missing_refs + 1))
        EXIT_CODE=1
    fi

    # Check for stalonetray (system tray)
    if ! printf '%s\n' "${packages[@]}" | grep -q "^stalonetray$"; then
        log_error "Missing package: stalonetray (required by autostart config)"
        missing_refs=$((missing_refs + 1))
        EXIT_CODE=1
    fi

    if [ "$missing_refs" -eq 0 ]; then
        log_success "All referenced packages are present."
    fi

    # 4. Report category counts
    log_info "Package list summary:"
    local core_count=0
    local desktop_count=0
    local audio_count=0
    local python_count=0
    local app_count=0
    local dev_count=0
    local current_section=""

    while IFS= read -r line; do
        if [[ "$line" =~ ^# ]]; then
            if [[ "$line" == *"Core System"* ]]; then current_section="core"
            elif [[ "$line" == *"Desktop Environment"* ]]; then current_section="desktop"
            elif [[ "$line" == *"Authentication"* ]]; then current_section="auth"
            elif [[ "$line" == *"Fonts"* ]]; then current_section="fonts"
            elif [[ "$line" == *"Audio"* ]]; then current_section="audio"
            elif [[ "$line" == *"Python & UI"* ]]; then current_section="python"
            elif [[ "$line" == *"Applications"* ]]; then current_section="apps"
            elif [[ "$line" == *"Developer"* ]]; then current_section="dev"
            fi
        elif [ -n "${line// /}" ] && [[ ! "$line" =~ ^# ]]; then
            case "$current_section" in
                core) core_count=$((core_count + 1)) ;;
                desktop) desktop_count=$((desktop_count + 1)) ;;
                audio) audio_count=$((audio_count + 1)) ;;
                python) python_count=$((python_count + 1)) ;;
                apps) app_count=$((app_count + 1)) ;;
                dev) dev_count=$((dev_count + 1)) ;;
            esac
        fi
    done < "$PACKAGE_LIST"

    log_info "  Core Utilities:      $core_count"
    log_info "  Desktop Environment: $desktop_count"
    log_info "  Audio:               $audio_count"
    log_info "  Python/Frameworks:   $python_count"
    log_info "  Applications:        $app_count"
    log_info "  Developer Tools:     $dev_count"
    log_info "  Total:               $total"

    if [ "$EXIT_CODE" -eq 0 ]; then
        log_success "Package list validation passed."
    else
        log_error "Package list validation failed."
    fi

    exit $EXIT_CODE
}

main "$@"
