#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) System Audit
# Performs security audits, configuration compliance checks, and generates reports.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

# --- Configuration ---
SYSTEMCTL_CMD="systemctl"
UFW_CMD="ufw"
SSHD_CONFIG="/etc/ssh/sshd_config"
SYSCTL_CMD="sysctl"
AUDITCTL_CMD="auditctl"

# --- Helper Functions ---

check_audit_deps() {
    check_dependencies "systemctl" "ufw" "sysctl"
}

# --- Security Audit Functions ---

audit_firewall() {
    log_info "Firewall Audit:"
    echo "==================================="

    if "$SYSTEMCTL_CMD" is-active --quiet ufw 2>/dev/null; then
        echo "  Status: [ACTIVE]"
        "$UFW_CMD" status verbose 2>/dev/null | sed 's/^/  /'
    else
        echo "  Status: [INACTIVE]"
        log_warn "Firewall is not active."
    fi

    echo "==================================="
}

audit_ssh() {
    log_info "SSH Audit:"
    echo "==================================="

    if [ ! -f "$SSHD_CONFIG" ]; then
        log_warn "SSH config not found. Skipping SSH audit."
        return 0
    fi

    local root_login pwd_auth

    root_login=$("$SYSTEMCTL_CMD" is-enabled sshd 2>/dev/null || echo "disabled")
    if [ "$root_login" == "disabled" ]; then
        echo "  SSH Service: [DISABLED]"
    else
        echo "  SSH Service: [ENABLED]"

        # Check config
        grep -q "^PermitRootLogin no" "$SSHD_CONFIG" && echo "  Root Login: [SECURE] (disabled)" || echo "  Root Login: [WARNING] (enabled)"
        grep -q "^PasswordAuthentication no" "$SSHD_CONFIG" && echo "  Password Auth: [SECURE] (disabled)" || echo "  Password Auth: [WARNING] (enabled)"
        grep -q "^X11Forwarding no" "$SSHD_CONFIG" && echo "  X11 Forward: [SECURE] (disabled)" || echo "  X11 Forward: [WARNING] (enabled)"
    fi

    echo "==================================="
}

audit_kernel_params() {
    log_info "Kernel Security Audit:"
    echo "==================================="

    local params=(
        "net.ipv4.tcp_syncookies"
        "net.ipv4.conf.all.rp_filter"
        "net.ipv4.conf.all.accept_redirects"
        "kernel.dmesg_restrict"
        "kernel.kptr_restrict"
        "fs.protected_symlinks"
    )

    for param in "${params[@]}"; do
        local value
        value=$("$SYSCTL_CMD" "$param" 2>/dev/null | awk -F= '{print $2}' | tr -d ' ')

        if [ -n "$value" ]; then
            printf "  %-40s %s\n" "$param:" "$value"
        else
            printf "  %-40s [UNSUPPORTED]\n" "$param:"
        fi
    done

    echo "==================================="
}

audit_user_accounts() {
    log_info "User Account Audit:"
    echo "==================================="

    # Users with UID 0 (root)
    local root_users
    root_users=$(awk -F: '$3 == 0 {print $1}' /etc/passwd)

    if [ "$root_users" == "root" ]; then
        echo "  Users with UID 0: root only."
    else
        log_warn "Multiple users with UID 0: $root_users"
    fi

    # Users with empty passwords
    local empty_pass
    empty_pass=$(awk -F: '($2 == "" || $2 == "*") {print $1}' /etc/shadow)

    if [ -z "$empty_pass" ]; then
        echo "  No users with empty passwords."
    else
        log_warn "Users with empty passwords: $empty_pass"
    fi

    # Users without passwords (login disabled)
    local no_pass
    no_pass=$(awk -F: '($2 == "!" || $2 == "!!") {print $1}' /etc/shadow)

    if [ -z "$no_pass" ]; then
        echo "  No users with disabled passwords."
    else
        echo "  Users with disabled passwords: $no_pass"
    fi

    echo "==================================="
}

audit_services() {
    log_info "Service Audit:"
    echo "==================================="

    # List running services
    echo "Running Services:"
    "$SYSTEMCTL_CMD" list-units --type=service --state=running --no-legend --no-pager 2>/dev/null | awk '{print "  " $1}'

    echo ""
    echo "Failed Services:"
    local failed
    failed=$("$SYSTEMCTL_CMD" --failed --no-legend --no-pager 2>/dev/null)

    if [ -z "$failed" ]; then
        echo "  (none)"
    else
        echo "$failed" | sed 's/^/  /'
    fi

    echo "==================================="
}

audit_file_permissions() {
    log_info "File Permission Audit:"
    echo "==================================="

    # Check sensitive files
    local files=("/etc/passwd" "/etc/shadow" "/etc/gshadow" "/etc/group")

    for file in "${files[@]}"; do
        if [ -f "$file" ]; then
            local perms
            perms=$(stat -c "%a %U:%G" "$file")
            printf "  %-20s %s\n" "$file" "$perms"
        fi
    done

    # Check SUID files
    echo ""
    echo "SUID Files:"
    find / -perm -4000 -type f 2>/dev/null | head -n 10 | sed 's/^/  /'

    echo "==================================="
}

# --- Full Audit Report ---

full_audit() {
    log_info "=== Full System Audit Report ==="
    echo ""

    audit_firewall
    audit_ssh
    audit_kernel_params
    audit_user_accounts
    audit_services
    audit_file_permissions

    log_info "=== Audit Complete ==="
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) System Audit

Usage: $0 <command>

Commands:
  firewall                  Audit firewall (UFW) configuration
  ssh                       Audit SSH configuration
  kernel                   Audit kernel security parameters
  users                    Audit user accounts and passwords
  services                 Audit running and failed services
  permissions              Audit file permissions and SUID files
  full                     Generate full audit report
  help                     Show this help message

Notes:
  - Some checks require root privileges (use sudo).
  - The audit is read-only and does not modify the system.

Examples:
  $0 firewall
  $0 ssh
  $0 full
HELP
}

# --- Main ---

main() {
    check_audit_deps

    local command="${1:-help}"
    shift || true

    case "$command" in
        firewall|audit-firewall)
            audit_firewall
            ;;
        ssh|audit-ssh)
            audit_ssh
            ;;
        kernel|audit-kernel)
            audit_kernel_params
            ;;
        users|audit-users)
            audit_user_accounts
            ;;
        services|audit-services)
            audit_services
            ;;
        permissions|audit-permissions)
            audit_file_permissions
            ;;
        full|all)
            full_audit
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