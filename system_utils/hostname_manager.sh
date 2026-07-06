#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Hostname Manager
# Provides safe hostname viewing, setting, and /etc/hosts synchronization.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Source Shared Library ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

# --- Configuration ---
HOSTNAME_FILE="/etc/hostname"
HOSTS_FILE="/etc/hosts"
HOSTNAMECTL_CMD="hostnamectl"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Hostname operation failed with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Helper Functions ---

check_hostname_deps() {
    check_dependencies "hostname"
    
    # hostnamectl is optional but preferred
    if ! command -v "$HOSTNAMECTL_CMD" > /dev/null 2>&1; then
        log_warn "hostnamectl not found. Using legacy hostname command."
    fi
}

validate_hostname() {
    local hostname="$1"
    
    # Check length (1-63 characters per RFC 1178)
    if [ ${#hostname} -lt 1 ] || [ ${#hostname} -gt 63 ]; then
        log_error "Hostname must be between 1 and 63 characters."
        return 1
    fi
    
    # Check valid characters: letters, numbers, hyphens (per RFC 952/1123)
    # Must not start or end with a hyphen
    if ! [[ "$hostname" =~ ^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$ ]]; then
        log_error "Invalid hostname format."
        log_info "Rules:"
        log_info "  - Only letters (a-z, A-Z), numbers (0-9), and hyphens (-)"
        log_info "  - Must start and end with a letter or number"
        log_info "  - Length: 1-63 characters"
        return 1
    fi
    
    # Check for consecutive hyphens
    if [[ "$hostname" == *"--"* ]]; then
        log_error "Hostname cannot contain consecutive hyphens."
        return 1
    fi
    
    return 0
}

backup_config_file() {
    local file="$1"
    local timestamp
    timestamp=$(date +%Y%m%d%H%M%S)
    local backup="${file}.backup.${timestamp}"
    
    if [ -f "$file" ]; then
        cp "$file" "$backup"
        log_info "Backed up $file to $backup"
    fi
}

# --- View Functions ---

show_hostname() {
    log_info "Current Hostname Configuration:"
    echo "==================================="
    
    local short_name fqdn static_name pretty_name
    
    # Get short hostname
    short_name=$(hostname -s 2>/dev/null || cat "$HOSTNAME_FILE" 2>/dev/null || echo "unknown")
    echo "Short Name:   $short_name"
    
    # Get FQDN
    fqdn=$(hostname -f 2>/dev/null || echo "N/A")
    echo "FQDN:         $fqdn"
    
    # Try hostnamectl for detailed info
    if command -v "$HOSTNAMECTL_CMD" > /dev/null 2>&1; then
        static_name=$($HOSTNAMECTL_CMD --static 2>/dev/null || echo "N/A")
        pretty_name=$($HOSTNAMECTL_CMD --pretty 2>/dev/null || echo "N/A")
        
        echo "Static Name:  $static_name"
        
        if [ "$pretty_name" != "" ] && [ "$pretty_name" != "N/A" ]; then
            echo "Pretty Name:  $pretty_name"
        fi
        
        local chassis_type
        chassis_type=$($HOSTNAMECTL_CMD chassis 2>/dev/null || echo "N/A")
        echo "Chassis:      $chassis_type"
    fi
    
    echo "==================================="
}

show_hosts_file() {
    log_info "Contents of /etc/hosts:"
    echo "==================================="
    cat "$HOSTS_FILE"
    echo "==================================="
}

# --- Set Functions ---

set_hostname() {
    local new_hostname="$1"
    
    validate_hostname "$new_hostname" || return 1
    
    local old_hostname
    old_hostname=$(hostname 2>/dev/null || cat "$HOSTNAME_FILE" 2>/dev/null || echo "vice-os")
    
    if [ "$new_hostname" == "$old_hostname" ]; then
        log_warn "Hostname is already set to '$new_hostname'. No changes needed."
        return 0
    fi
    
    log_info "Changing hostname from '$old_hostname' to '$new_hostname'..."
    
    # Backup configuration files
    backup_config_file "$HOSTNAME_FILE"
    backup_config_file "$HOSTS_FILE"
    
    # Update /etc/hostname
    log_info "Updating $HOSTNAME_FILE..."
    echo "$new_hostname" > "$HOSTNAME_FILE"
    chmod 644 "$HOSTNAME_FILE"
    
    # Update the running system hostname
    log_info "Setting runtime hostname..."
    if command -v "$HOSTNAMECTL_CMD" > /dev/null 2>&1; then
        $HOSTNAMECTL_CMD set-hostname "$new_hostname"
    else
        hostname "$new_hostname"
    fi
    
    # Update /etc/hosts
    log_info "Updating $HOSTS_FILE..."
    update_hosts_file "$old_hostname" "$new_hostname"
    
    log_success "Hostname changed to '$new_hostname' successfully."
    log_warn "Some services may need to be restarted to pick up the new hostname."
    log_info "Tip: Run 'exec bash' to update your current shell prompt."
}

set_pretty_hostname() {
    local pretty_name="$1"
    
    if [ -z "$pretty_name" ]; then
        log_error "Pretty hostname required."
        return 1
    fi
    
    # Pretty hostname can contain spaces and special characters
    if [ ${#pretty_name} -gt 63 ]; then
        log_error "Pretty hostname must be 63 characters or less."
        return 1
    fi
    
    if ! command -v "$HOSTNAMECTL_CMD" > /dev/null 2>&1; then
        log_error "hostnamectl is required for pretty hostname but not found."
        return 1
    fi
    
    log_info "Setting pretty hostname to: $pretty_name"
    $HOSTNAMECTL_CMD set-hostname --pretty "$pretty_name"
    log_success "Pretty hostname set."
}

# --- /etc/hosts Management ---

update_hosts_file() {
    local old_hostname="$1"
    local new_hostname="$2"
    local tmp_file
    
    tmp_file=$(mktemp)
    
    # Read existing hosts file and replace old hostname with new
    while IFS= read -r line || [ -n "$line" ]; do
        # Skip comments and empty lines
        if [[ "$line" =~ ^[[:space:]]*# ]] || [[ -z "$line" ]]; then
            echo "$line" >> "$tmp_file"
            continue
        fi
        
        # Replace old hostname with new hostname in 127.0.1.1 line
        if [[ "$line" =~ ^127\.0\.1\.1[[:space:]] ]]; then
            # Replace old hostname, preserve any FQDN or aliases
            local new_line
            new_line=$(echo "$line" | sed "s/\b${old_hostname}\b/${new_hostname}/g")
            echo "$new_line" >> "$tmp_file"
        else
            echo "$line" >> "$tmp_file"
        fi
    done < "$HOSTS_FILE"
    
    # Check if 127.0.1.1 entry exists, if not add it
    if ! grep -q "^127\.0\.1\.1" "$tmp_file"; then
        echo "127.0.1.1   ${new_hostname}" >> "$tmp_file"
    fi
    
    # Move temp file to hosts file
    mv "$tmp_file" "$HOSTS_FILE"
    chmod 644 "$HOSTS_FILE"
}

# --- Validation Functions ---

check_hostname() {
    local hostname="${1:-}"
    
    if [ -z "$hostname" ]; then
        hostname=$(hostname 2>/dev/null || cat "$HOSTNAME_FILE" 2>/dev/null)
    fi
    
    log_info "Validating hostname: $hostname"
    
    if validate_hostname "$hostname"; then
        log_success "Hostname '$hostname' is valid."
        
        # Check /etc/hostname consistency
        local file_hostname
        file_hostname=$(cat "$HOSTNAME_FILE" 2>/dev/null || echo "")
        
        if [ "$hostname" == "$file_hostname" ]; then
            log_success "/etc/hostname is consistent."
        else
            log_warn "Mismatch: Runtime hostname ($hostname) != /etc/hostname ($file_hostname)"
        fi
        
        # Check /etc/hosts
        if grep -q "127\.0\.1\.1.*${hostname}" "$HOSTS_FILE" 2>/dev/null; then
            log_success "/etc/hosts contains hostname entry."
        else
            log_warn "/etc/hosts does not contain 127.0.1.1 entry for '$hostname'."
            log_info "This may cause 'unable to resolve host' warnings with sudo."
        fi
        
        return 0
    else
        return 1
    fi
}

# --- Reset Function ---

reset_hostname() {
    log_warn "Resetting hostname to default: 'vice-os'"
    set_hostname "vice-os"
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) Hostname Manager

Usage: $0 <command> [options]

Viewing:
  show                         Show current hostname configuration
  hosts                        Show contents of /etc/hosts

Setting:
  set <hostname>               Set system hostname (updates /etc/hostname, /etc/hosts, runtime)
  set-pretty <name>            Set pretty hostname (e.g., "Vice OS Desktop")

Validation:
  check [hostname]             Validate hostname format and file consistency
                                (checks current hostname if not specified)

Reset:
  reset                        Reset hostname to default 'vice-os'

Help:
  help                         Show this help message

Notes:
  - Hostname rules (RFC 1178/952/1123):
    * Only letters (a-z, A-Z), numbers (0-9), and hyphens (-)
    * Must start and end with a letter or number
    * Length: 1-63 characters
    * No consecutive hyphens
  - Configuration files are automatically backed up before modification.
  - Some services may need restarting after hostname change.

Examples:
  $0 show
  $0 set my-workstation
  $0 set-pretty "Vice OS Dev Machine"
  $0 check
  $0 reset
HELP
}

# --- Main ---

main() {
    check_hostname_deps
    
    local command="${1:-help}"
    shift || true
    
    case "$command" in
        show|status|info)
            show_hostname
            ;;
        hosts|etc-hosts)
            show_hosts_file
            ;;
        set|set-hostname)
            local new_hostname="${1:-}"
            if [ -z "$new_hostname" ]; then
                log_error "Hostname required."
                exit 1
            fi
            set_hostname "$new_hostname"
            ;;
        set-pretty|pretty)
            local pretty_name="${1:-}"
            if [ -z "$pretty_name" ]; then
                log_error "Pretty hostname required."
                exit 1
            fi
            set_pretty_hostname "$pretty_name"
            ;;
        check|validate)
            local hostname="${1:-}"
            check_hostname "$hostname"
            ;;
        reset|default)
            reset_hostname
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