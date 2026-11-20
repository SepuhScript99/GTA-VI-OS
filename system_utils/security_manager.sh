#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Security Manager
# Provides centralized management for Firewall (UFW), Intrusion Prevention
# (Fail2ban), SSH auditing, and Login monitoring.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

# --- Configuration ---
UFW_CMD="ufw"
F2B_CMD="fail2ban-client"
SSHD_CONFIG="/etc/ssh/sshd_config"

# --- Helper Functions ---

check_security_deps() {
    check_dependencies "ufw" "systemctl" "journalctl"
}

# --- Firewall (UFW) Functions ---

fw_status() {
    log_info "Firewall Status (UFW):"
    echo "==================================="
    $UFW_CMD status verbose
    echo "==================================="
}

fw_enable() {
    log_info "Enabling Firewall..."
    $UFW_CMD --force enable
    log_success "Firewall enabled."
}

fw_disable() {
    log_warn "Disabling Firewall... (System is now unprotected)"
    $UFW_CMD --force disable
    log_success "Firewall disabled."
}

fw_allow_port() {
    local port="$1"
    local protocol="${2:-tcp}"

    if ! [[ "$port" =~ ^[0-9]+$ ]] || [ "$port" -lt 1 ] || [ "$port" -gt 65535 ]; then
        log_error "Invalid port number: $port"
        return 1
    fi

    case "$protocol" in
        tcp|udp|both)
            ;;
        *)
            log_error "Invalid protocol: $protocol (use tcp, udp, or both)"
            return 1
            ;;
    esac

    log_info "Allowing port $port/$protocol..."
    if [ "$protocol" == "both" ]; then
        $UFW_CMD allow "$port"
    else
        $UFW_CMD allow "$port/$protocol"
    fi
    log_success "Rule added."
}

fw_deny_port() {
    local port="$1"
    local protocol="${2:-tcp}"

    if ! [[ "$port" =~ ^[0-9]+$ ]] || [ "$port" -lt 1 ] || [ "$port" -gt 65535 ]; then
        log_error "Invalid port number: $port"
        return 1
    fi

    log_info "Denying port $port/$protocol..."
    $UFW_CMD deny "$port/$protocol"
    log_success "Rule added."
}

# --- Fail2ban Functions ---

f2b_status() {
    if ! command -v "$F2B_CMD" > /dev/null 2>&1; then
        log_error "Fail2ban is not installed."
        return 1
    fi

    log_info "Fail2ban Status:"
    echo "==================================="
    $F2B_CMD status
    echo "==================================="
}

f2b_start() {
    log_info "Starting Fail2ban..."
    systemctl start fail2ban
    systemctl enable fail2ban
    log_success "Fail2ban started and enabled."
}

f2b_stop() {
    log_info "Stopping Fail2ban..."
    systemctl stop fail2ban
    systemctl disable fail2ban
    log_success "Fail2ban stopped and disabled."
}

f2b_banned() {
    if ! command -v "$F2B_CMD" > /dev/null 2>&1; then
        log_error "Fail2ban is not installed."
        return 1
    fi

    log_info "Banned IPs (SSH):"
    echo "==================================="
    local banned_ips
    banned_ips=$($F2B_CMD status sshd 2>/dev/null | grep "Banned IP list" | cut -d: -f2 | sed 's/^[ \t]*//')

    if [ -z "$banned_ips" ] || [ "$banned_ips" == "None" ]; then
        log_info "No banned IPs found."
    else
        echo "$banned_ips" | tr ' ' '\n'
    fi
    echo "==================================="
}

f2b_unban() {
    local ip="$1"

    if ! [[ "$ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        log_error "Invalid IP address format."
        return 1
    fi

    log_info "Unbanning IP: $ip"
    $F2B_CMD unban "$ip" 2>/dev/null || $F2B_CMD set sshd unbanip "$ip" 2>/dev/null
    log_success "IP $ip unbanned."
}

# --- SSH Audit Functions ---

audit_ssh() {
    log_info "SSH Configuration Audit:"
    echo "==================================="

    if [ ! -f "$SSHD_CONFIG" ]; then
        log_warn "SSH config file not found at $SSHD_CONFIG"
        return 1
    fi

    local root_login pwd_auth port

    # Check Root Login
    root_login=$(grep -i "^PermitRootLogin" "$SSHD_CONFIG" | awk '{print $2}')
    if [ "$root_login" == "no" ] || [ "$root_login" == "prohibit-password" ]; then
        echo "Root Login:       [SECURE] ($root_login)"
    else
        echo "Root Login:       [WARNING] (Root login is permitted)"
    fi

    # Check Password Authentication
    pwd_auth=$(grep -i "^PasswordAuthentication" "$SSHD_CONFIG" | awk '{print $2}')
    if [ "$pwd_auth" == "no" ]; then
        echo "Password Auth:    [SECURE] (Disabled - Key-based only)"
    else
        echo "Password Auth:    [WARNING] (Enabled - Vulnerable to brute force)"
    fi

    # Check Port
    port=$(grep -i "^Port" "$SSHD_CONFIG" | awk '{print $2}')
    if [ -z "$port" ]; then
        port="22 (default)"
    fi
    echo "SSH Port:         $port"

    echo "==================================="
}

# --- Login Monitoring Functions ---

failed_logins() {
    local count="${1:-10}"

    log_info "Last $count failed login attempts:"
    echo "==================================="

    # Try journalctl first (modern systemd)
    if journalctl _COMM=sshd -u ssh -g "Failed password" --no-pager -n "$count" 2>/dev/null | grep -q "Failed"; then
        journalctl _COMM=sshd -u ssh -g "Failed password" --no-pager -n "$count" | awk '{print $1, $2, $3, $9, $11}'
    else
        # Fallback to auth.log
        if [ -f /var/log/auth.log ]; then
            grep "Failed password" /var/log/auth.log | tail -n "$count" | awk '{print $1, $2, $3, $9, $11}'
        else
            log_warn "No failed login logs found."
        fi
    fi

    echo "==================================="
}

successful_logins() {
    local count="${1:-10}"

    log_info "Last $count successful logins:"
    echo "==================================="

    # Use 'last' command which reads /var/log/wtmp
    last -n "$count" -a | head -n "$count"

    echo "==================================="
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Security Manager

Usage: $0 <command> [options]

Firewall (UFW):
  fw-status                   Show firewall status
  fw-enable                   Enable firewall
  fw-disable                  Disable firewall
  fw-allow <port> [proto]    Allow port (proto: tcp/udp/both, default: tcp)
  fw-deny <port> [proto]     Deny port

Fail2ban:
  f2b-status                  Show fail2ban status
  f2b-start                   Start and enable fail2ban
  f2b-stop                    Stop and disable fail2ban
  f2b-banned                  List banned IPs
  f2b-unban <ip>              Unban a specific IP

Auditing:
  audit-ssh                   Audit SSH configuration
  failed-logins [count]       Show failed login attempts (default: 10)
  successful-logins [count]   Show successful logins (default: 10)

Help:
  help                        Show this help message

Examples:
  $0 fw-status
  $0 fw-allow 8080 tcp
  $0 f2b-banned
  $0 audit-ssh
  $0 failed-logins 20
HELP
}

# --- Main ---

main() {
    local command="${1:-help}"
    if [ "$command" = "help" ] || [ "$command" = "--help" ] || [ "$command" = "-h" ]; then
        show_help
        exit 0
    fi
    shift || true

    check_security_deps

    case "$command" in
        fw-status|ufw-status)
            fw_status
            ;;
        fw-enable|ufw-enable)
            fw_enable
            ;;
        fw-disable|ufw-disable)
            fw_disable
            ;;
        fw-allow|allow|allow-port)
            local port="${1:-}"
            if [ -z "$port" ]; then
                log_error "Port required."
                exit 1
            fi
            local protocol="${2:-tcp}"
            fw_allow_port "$port" "$protocol"
            ;;
        fw-deny|deny|deny-port)
            local port="${1:-}"
            if [ -z "$port" ]; then
                log_error "Port required."
                exit 1
            fi
            local protocol="${2:-tcp}"
            fw_deny_port "$port" "$protocol"
            ;;
        f2b-status|fail2ban-status)
            f2b_status
            ;;
        f2b-start|fail2ban-start)
            f2b_start
            ;;
        f2b-stop|fail2ban-stop)
            f2b_stop
            ;;
        f2b-banned|banned)
            f2b_banned
            ;;
        f2b-unban|unban)
            local ip="${1:-}"
            if [ -z "$ip" ]; then
                log_error "IP address required."
                exit 1
            fi
            f2b_unban "$ip"
            ;;
        audit-ssh|ssh-audit)
            audit_ssh
            ;;
        failed-logins|failed)
            local count="${1:-10}"
            failed_logins "$count"
            ;;
        successful-logins|logins)
            local count="${1:-10}"
            successful_logins "$count"
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