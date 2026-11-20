#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Log Analyzer
# Provides intelligent log analysis, error frequency tracking, and security
# event extraction from systemd journal and traditional log files.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

# --- Configuration ---
JOURNALCTL_CMD="journalctl"
AUTH_LOG="/var/log/auth.log"
SYSLOG="/var/log/syslog"
DMESG_CMD="dmesg"
GREP_CMD="grep"
AWK_CMD="awk"
SORT_CMD="sort"
UNIQ_CMD="uniq"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Log analysis failed with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Helper Functions ---

check_analyzer_deps() {
    check_dependencies "journalctl" "grep" "awk" "sort"
}

# --- Error Analysis Functions ---

analyze_errors() {
    local lines="${1:-50}"

    log_info "System Error Analysis (last $lines errors):"
    echo "==================================="

    # Extract errors from journal
    "$JOURNALCTL_CMD" -p err --no-pager -n "$lines" 2>/dev/null | while IFS= read -r line; do
        echo "  $line"
    done

    echo ""
    echo "Error Frequency (by service):"
    echo "-----------------------------------"

    # Count errors by unit
    "$JOURNALCTL_CMD" -p err --no-pager -n 500 2>/dev/null | \
        "$AWK_CMD" -F'[][]' '{print $5}' | \
        "$SORT_CMD" | \
        "$UNIQ_CMD" -c | \
        "$SORT_CMD" -rn | \
        head -n 10

    echo "==================================="
}

analyze_warnings() {
    local lines="${1:-30}"

    log_info "System Warning Analysis (last $lines warnings):"
    echo "==================================="

    "$JOURNALCTL_CMD" -p warning --no-pager -n "$lines" 2>/dev/null | while IFS= read -r line; do
        echo "  $line"
    done

    echo ""
    echo "Warning Frequency (by service):"
    echo "-----------------------------------"

    "$JOURNALCTL_CMD" -p warning --no-pager -n 500 2>/dev/null | \
        "$AWK_CMD" -F'[][]' '{print $5}' | \
        "$SORT_CMD" | \
        "$UNIQ_CMD" -c | \
        "$SORT_CMD" -rn | \
        head -n 10

    echo "==================================="
}

# --- Security Analysis Functions ---

analyze_security() {
    log_info "Security Event Analysis:"
    echo "==================================="

    # Failed SSH logins
    echo "1. Failed SSH Logins:"
    if [ -f "$AUTH_LOG" ]; then
        local failed
        failed=$("$GREP_CMD" "Failed password" "$AUTH_LOG" 2>/dev/null | wc -l)
        echo "   Total failed attempts: $failed"
        if [ "$failed" -gt 0 ]; then
            echo "   Recent attempts:"
            "$GREP_CMD" "Failed password" "$AUTH_LOG" 2>/dev/null | tail -n 5 | while read -r line; do
                echo "     $line"
            done
        fi
    else
        echo "   (auth.log not found)"
    fi
    echo ""

    # Successful SSH logins
    echo "2. Successful SSH Logins:"
    if [ -f "$AUTH_LOG" ]; then
        local success
        success=$("$GREP_CMD" "Accepted password\|Accepted publickey" "$AUTH_LOG" 2>/dev/null | wc -l)
        echo "   Total successful logins: $success"
        if [ "$success" -gt 0 ]; then
            echo "   Recent logins:"
            "$GREP_CMD" "Accepted password\|Accepted publickey" "$AUTH_LOG" 2>/dev/null | tail -n 5 | while read -r line; do
                echo "     $line"
            done
        fi
    else
        echo "   (auth.log not found)"
    fi
    echo ""

    # sudo usage
    echo "3. Sudo Usage:"
    if [ -f "$AUTH_LOG" ]; then
        local sudo_count
        sudo_count=$("$GREP_CMD" "sudo:" "$AUTH_LOG" 2>/dev/null | wc -l)
        echo "   Total sudo events: $sudo_count"
    else
        echo "   (auth.log not found)"
    fi
    echo ""

    # Fail2ban status
    echo "4. Fail2ban Status:"
    if command -v fail2ban-client > /dev/null 2>&1; then
        local banned
        banned=$(fail2ban-client status sshd 2>/dev/null | grep "Banned IP list" | cut -d: -f2 | sed 's/^[ \t]*//')
        if [ -n "$banned" ] && [ "$banned" != "None" ]; then
            echo "   Banned IPs: $banned"
        else
            echo "   No IPs banned."
        fi
    else
        echo "   (fail2ban not installed)"
    fi

    echo "==================================="
}

# --- Boot Analysis Functions ---

analyze_boot() {
    log_info "Boot Time Analysis:"
    echo "==================================="

    # Get boot duration
    local boot_time
    boot_time=$("$JOURNALCTL_CMD" -b 0 | "$GREP_CMD" "systemd-analyze" | "$AWK_CMD" '{print $NF}' | head -n 1)

    if [ -n "$boot_time" ]; then
        echo "Last Boot Duration: $boot_time"
    else
        echo "Boot Duration: N/A"
    fi

    echo ""
    echo "Boot Errors (current boot):"
    echo "-----------------------------------"

    local boot_errors
    boot_errors=$("$JOURNALCTL_CMD" -b 0 -p err --no-pager 2>/dev/null | wc -l)
    echo "Total boot errors: $boot_errors"

    if [ "$boot_errors" -gt 0 ]; then
        echo ""
        echo "Recent boot errors:"
        "$JOURNALCTL_CMD" -b 0 -p err --no-pager 2>/dev/null | tail -n 10 | while IFS= read -r line; do
            echo "  $line"
        done
    fi

    echo ""
    echo "Slowest Services:"
    echo "-----------------------------------"

    # Get slowest services from boot
    if command -v systemd-analyze > /dev/null 2>&1; then
        systemd-analyze blame 2>/dev/null | head -n 10 | while read -r line; do
            echo "  $line"
        done
    else
        echo "  (systemd-analyze not available)"
    fi

    echo "==================================="
}

# --- Pattern Search Functions ---

search_pattern() {
    local pattern="$1"
    local lines="${2:-20}"

    if [ -z "$pattern" ]; then
        log_error "Search pattern required."
        return 1
    fi

    log_info "Searching logs for pattern: '$pattern' (last $lines matches)"
    echo "==================================="

    "$JOURNALCTL_CMD" --no-pager -n 1000 2>/dev/null | "$GREP_CMD" -i "$pattern" | tail -n "$lines"

    echo "==================================="
}

# --- Summary Report ---

full_report() {
    log_info "=== Full Log Analysis Report ==="
    echo ""

    echo "1. Error Summary:"
    analyze_errors 20
    echo ""

    echo "2. Security Summary:"
    analyze_security
    echo ""

    echo "3. Boot Summary:"
    analyze_boot
    echo ""

    log_info "=== Report Complete ==="
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Log Analyzer

Usage: $0 <command> [options]

Error Analysis:
  errors [lines]              Show recent system errors and frequency by service
  warnings [lines]           Show recent warnings and frequency by service

Security Analysis:
  security                   Analyze SSH logins, sudo usage, and Fail2ban status

Boot Analysis:
  boot                       Analyze boot time, errors, and slow services

Pattern Search:
  search <pattern> [lines]   Search logs for a specific pattern (case-insensitive)

Full Report:
  report                     Generate a comprehensive analysis report

Help:
  help                       Show this help message

Examples:
  $0 errors 30
  $0 security
  $0 boot
  $0 search "kernel panic" 10
  $0 report
HELP
}

# --- Main ---

main() {
    check_analyzer_deps

    local command="${1:-help}"
    shift || true

    case "$command" in
        errors|error)
            local lines="${1:-50}"
            analyze_errors "$lines"
            ;;
        warnings|warning)
            local lines="${1:-30}"
            analyze_warnings "$lines"
            ;;
        security|security-analysis)
            analyze_security
            ;;
        boot|boot-analysis)
            analyze_boot
            ;;
        search|find|grep)
            local pattern="${1:-}"
            if [ -z "$pattern" ]; then
                log_error "Search pattern required."
                exit 1
            fi
            local lines="${2:-20}"
            search_pattern "$pattern" "$lines"
            ;;
        report|full-report)
            full_report
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            log_error "Unknown command: $command"
            log_info "Run '$0 help' for usage information."
            exit 1
            ;;
    esac
}

main "$@"