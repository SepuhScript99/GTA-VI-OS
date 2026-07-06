#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Security Hardener
# Proactively hardens the system by tightening sysctl, disabling services,
# and securing SSH configurations.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Source Shared Library ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

# --- Configuration ---
SYSCTL_CMD="sysctl"
SYSTEMCTL_CMD="systemctl"
SSHD_CONFIG="/etc/ssh/sshd_config"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Security hardening failed with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Helper Functions ---

check_hardener_deps() {
    check_dependencies "sysctl" "systemctl" "sed"
}

# --- Kernel Hardening Functions ---

harden_kernel() {
    log_info "Applying kernel hardening parameters..."
    
    local params=(
        "net.ipv4.tcp_syncookies=1"
        "net.ipv4.conf.all.rp_filter=1"
        "net.ipv4.conf.all.accept_redirects=0"
        "net.ipv4.conf.all.send_redirects=0"
        "net.ipv4.ip_forward=0"
        "net.ipv6.conf.all.accept_redirects=0"
        "kernel.dmesg_restrict=1"
        "kernel.kptr_restrict=2"
        "kernel.yama.ptrace_scope=1"
        "fs.suid_dumpable=0"
        "fs.protected_symlinks=1"
        "fs.protected_hardlinks=1"
    )
    
    for param in "${params[@]}"; do
        local key="${param%%=*}"
        local value="${param##*=}"
        
        if "$SYSCTL_CMD" -w "$key=$value" > /dev/null 2>&1; then
            log_info "  [OK] $key=$value"
        else
            log_warn "  [SKIP] $key (unsupported)"
        fi
    done
    
    log_success "Kernel parameters hardened."
}

# --- Service Hardening Functions ---

disable_unused_services() {
    log_info "Disabling unnecessary services..."
    
    local services=(
        "avahi-daemon"
        "cups"
        "cups-browsed"
        "rpcbind"
        "nfs-server"
        "bluetooth"
    )
    
    for svc in "${services[@]}"; do
        if "$SYSTEMCTL_CMD" is-enabled --quiet "$svc" 2>/dev/null; then
            "$SYSTEMCTL_CMD" disable --now "$svc" 2>/dev/null && log_info "  [DISABLED] $svc"
        fi
    done
    
    log_success "Unused services disabled."
}

# --- SSH Hardening Functions ---

harden_ssh() {
    if [ ! -f "$SSHD_CONFIG" ]; then
        log_warn "SSH config not found. Skipping SSH hardening."
        return 0
    fi
    
    log_info "Hardening SSH configuration..."
    
    local backup_ts
    backup_ts=$(date +%Y%m%d%H%M%S)
    cp "$SSHD_CONFIG" "${SSHD_CONFIG}.backup.${backup_ts}"
    
    # Disable root login
    if "$SYSTEMCTL_CMD" is-enabled --quiet sshd 2>/dev/null || "$SYSTEMCTL_CMD" is-enabled --quiet ssh 2>/dev/null; then
        sed -i 's/^#*PermitRootLogin.*/PermitRootLogin no/' "$SSHD_CONFIG"
        sed -i 's/^#*PermitRootLogin.*/PermitRootLogin no/' "$SSHD_CONFIG"
        log_info "  [OK] PermitRootLogin no"
    fi
    
    # Disable password authentication
    sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' "$SSHD_CONFIG"
    log_info "  [OK] PasswordAuthentication no"
    
    # Disable X11 forwarding
    sed -i 's/^#*X11Forwarding.*/X11Forwarding no/' "$SSHD_CONFIG"
    log_info "  [OK] X11Forwarding no"
    
    # Restart SSH service
    if "$SYSTEMCTL_CMD" is-active --quiet sshd 2>/dev/null; then
        "$SYSTEMCTL_CMD" restart sshd 2>/dev/null || true
    elif "$SYSTEMCTL_CMD" is-active --quiet ssh 2>/dev/null; then
        "$SYSTEMCTL_CMD" restart ssh 2>/dev/null || true
    fi
    
    log_success "SSH hardened."
}

# --- File Permission Hardening ---

harden_permissions() {
    log_info "Hardening file permissions..."
    
    # Restrict /etc/shadow and /etc/gshadow
    chmod 640 /etc/shadow 2>/dev/null && log_info "  [OK] /etc/shadow"
    chmod 640 /etc/gshadow 2>/dev/null && log_info "  [OK] /etc/gshadow"
    
    # Restrict cron directories
    chmod 700 /etc/cron.d 2>/dev/null && log_info "  [OK] /etc/cron.d"
    chmod 700 /etc/cron.daily 2>/dev/null && log_info "  [OK] /etc/cron.daily"
    chmod 700 /etc/cron.hourly 2>/dev/null && log_info "  [OK] /etc/cron.hourly"
    
    log_success "File permissions hardened."
}

# --- Full Hardening ---

full_harden() {
    log_info "=== Starting Full Security Hardening ==="
    
    harden_kernel
    echo ""
    disable_unused_services
    echo ""
    harden_ssh
    echo ""
    harden_permissions
    
    log_info "=== Hardening Complete ==="
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Security Hardener

Usage: $0 <command>

Commands:
  kernel                     Apply kernel hardening sysctl parameters
  services                  Disable unnecessary services (avahi, cups, etc.)
  ssh                       Harden SSH configuration
  permissions               Tighten file permissions
  full                      Run all hardening steps
  help                      Show this help message

Notes:
  - Requires root privileges (use sudo).
  - SSH hardening creates a backup before modifying.
  - Kernel parameters are applied immediately but not persistent.
  - Use 'sysctl -p' to make kernel changes persistent.

Examples:
  $0 kernel
  $0 ssh
  $0 full
HELP
}

# --- Main ---

main() {
    check_hardener_deps
    
    local command="${1:-help}"
    shift || true
    
    case "$command" in
        kernel|harden-kernel)
            harden_kernel
            ;;
        services|disable-services)
            disable_unused_services
            ;;
        ssh|harden-ssh)
            harden_ssh
            ;;
        permissions|harden-permissions)
            harden_permissions
            ;;
        full|all)
            full_harden
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