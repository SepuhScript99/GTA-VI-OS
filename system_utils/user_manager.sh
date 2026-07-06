#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) User Manager
# Provides user and group management utilities: creation, deletion,
# password changes, group assignments, and account locking.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Source Shared Library ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "User management operation failed with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Helper Functions ---

check_user_exists() {
    local username="$1"
    if ! id -u "$username" > /dev/null 2>&1; then
        return 1
    fi
    return 0
}

validate_username() {
    local username="$1"
    
    # Check length (1-32 chars)
    if [ ${#username} -lt 1 ] || [ ${#username} -gt 32 ]; then
        log_error "Username must be between 1 and 32 characters."
        return 1
    fi
    
    # Check valid characters (lowercase, numbers, hyphens, underscores)
    if ! [[ "$username" =~ ^[a-z_][a-z0-9_-]*$ ]]; then
        log_error "Username contains invalid characters."
        log_info "Valid characters: lowercase letters, numbers, hyphens, underscores."
        log_info "Must start with a letter or underscore."
        return 1
    fi
    
    # Check if user already exists
    if check_user_exists "$username"; then
        log_error "User '$username' already exists."
        return 1
    fi
    
    return 0
}

# --- User Creation Functions ---

create_user() {
    local username="$1"
    local full_name="${2:-}"
    local shell="${3:-/bin/bash}"
    local groups="${4:-}"
    
    validate_username "$username" || return 1
    
    log_info "Creating user: $username"
    
    local cmd_args=(
        "--create-home"
        "--shell" "$shell"
    )
    
    if [ -n "$full_name" ]; then
        cmd_args+=("--comment" "$full_name")
    fi
    
    if [ -n "$groups" ]; then
        cmd_args+=("--groups" "$groups")
    fi
    
    if ! useradd "${cmd_args[@]}" "$username"; then
        log_error "Failed to create user '$username'."
        return 1
    fi
    
    log_success "User '$username' created successfully."
    log_info "Set a password with: $0 set-password $username"
}

delete_user() {
    local username="$1"
    local keep_home="${2:-no}"
    
    if ! check_user_exists "$username"; then
        log_error "User '$username' does not exist."
        return 1
    fi
    
    # Prevent deleting the primary admin user
    if [ "$username" == "vice" ]; then
        log_error "Cannot delete the primary system user 'vice'."
        return 1
    fi
    
    log_info "Deleting user: $username"
    
    local cmd_args=()
    if [ "$keep_home" == "yes" ] || [ "$keep_home" == "keep" ]; then
        log_info "Keeping home directory."
    else
        cmd_args+=("--remove")
        log_info "Removing home directory."
    fi
    
    if ! userdel "${cmd_args[@]}" "$username"; then
        log_error "Failed to delete user '$username'."
        return 1
    fi
    
    log_success "User '$username' deleted successfully."
}

# --- Password Functions ---

set_password() {
    local username="$1"
    local password="${2:-}"
    
    if ! check_user_exists "$username"; then
        log_error "User '$username' does not exist."
        return 1
    fi
    
    log_info "Setting password for user: $username"
    
    if [ -n "$password" ]; then
        # Non-interactive password set
        if ! echo "${username}:${password}" | chpasswd; then
            log_error "Failed to set password."
            return 1
        fi
        log_success "Password set for '$username'."
    else
        # Interactive password set
        if ! passwd "$username"; then
            log_error "Failed to set password."
            return 1
        fi
        log_success "Password set for '$username'."
    fi
}

lock_user() {
    local username="$1"
    
    if ! check_user_exists "$username"; then
        log_error "User '$username' does not exist."
        return 1
    fi
    
    log_info "Locking account for user: $username"
    
    if ! usermod --lock "$username"; then
        log_error "Failed to lock user '$username'."
        return 1
    fi
    
    log_success "User '$username' locked."
}

unlock_user() {
    local username="$1"
    
    if ! check_user_exists "$username"; then
        log_error "User '$username' does not exist."
        return 1
    fi
    
    log_info "Unlocking account for user: $username"
    
    if ! usermod --unlock "$username"; then
        log_error "Failed to unlock user '$username'."
        return 1
    fi
    
    log_success "User '$username' unlocked."
}

# --- Group Management Functions ---

add_to_group() {
    local username="$1"
    local group="$2"
    
    if ! check_user_exists "$username"; then
        log_error "User '$username' does not exist."
        return 1
    fi
    
    if ! getent group "$group" > /dev/null 2>&1; then
        log_info "Group '$group' does not exist. Creating it..."
        if ! groupadd "$group"; then
            log_error "Failed to create group '$group'."
            return 1
        fi
    fi
    
    log_info "Adding user '$username' to group '$group'..."
    
    if ! usermod --append --groups "$group" "$username"; then
        log_error "Failed to add user to group."
        return 1
    fi
    
    log_success "User '$username' added to group '$group'."
    log_info "Note: The user may need to log out and log back in for changes to take effect."
}

remove_from_group() {
    local username="$1"
    local group="$2"
    
    if ! check_user_exists "$username"; then
        log_error "User '$username' does not exist."
        return 1
    fi
    
    if ! getent group "$group" > /dev/null 2>&1; then
        log_error "Group '$group' does not exist."
        return 1
    fi
    
    log_info "Removing user '$username' from group '$group'..."
    
    if ! gpasswd --delete "$username" "$group"; then
        log_error "Failed to remove user from group."
        return 1
    fi
    
    log_success "User '$username' removed from group '$group'."
}

# --- Information Functions ---

list_users() {
    log_info "System Users (UID >= 1000):"
    echo "==================================="
    awk -F: '($3 >= 1000) && ($1 != "nobody") {printf "  %-15s UID: %-6s Shell: %s\n", $1, $3, $7}' /etc/passwd
    echo "==================================="
}

show_user_info() {
    local username="$1"
    
    if ! check_user_exists "$username"; then
        log_error "User '$username' does not exist."
        return 1
    fi
    
    local uid gid home shell groups
    uid=$(id -u "$username")
    gid=$(id -g "$username")
    home=$(eval echo "~$username")
    shell=$(getent passwd "$username" | cut -d: -f7)
    groups=$(id -nG "$username" | tr ' ' ', ')
    
    echo "==================================="
    echo "     User Information: $username"
    echo "==================================="
    echo "UID:           $uid"
    echo "GID (Primary): $gid"
    echo "Home Dir:      $home"
    echo "Shell:         $shell"
    echo "Groups:        $groups"
    
    local lock_status
    if passwd -S "$username" | grep -q "P"; then
        lock_status="Active (Password set)"
    elif passwd -S "$username" | grep -q "L"; then
        lock_status="Locked"
    elif passwd -S "$username" | grep -q "NP"; then
        lock_status="No Password"
    else
        lock_status="Unknown"
    fi
    
    echo "Account Status:$lock_status"
    echo "==================================="
}

# --- Usage ---

show_help() {
    cat <<HELP
GTA VI OS (Vice OS) User Manager

Usage: $0 <command> [options]

User Management:
  create <username> [full_name] [shell] [groups]  Create a new user
  delete <username> [--keep-home]                  Delete a user
  set-password <username> [password]               Set user password (interactive if omitted)
  lock <username>                                  Lock user account
  unlock <username>                                Unlock user account

Group Management:
  add-to-group <username> <group>                  Add user to a group
  remove-from-group <username> <group>              Remove user from a group

Information:
  list                                             List all system users (UID >= 1000)
  info <username>                                  Show detailed user information

Help:
  help                                             Show this help message

Examples:
  $0 create john "John Doe" /bin/bash "sudo,audio"
  $0 set-password john
  $0 add-to-group john docker
  $0 info john
HELP
}

# --- Main ---

main() {
    check_root
    
    local command="${1:-help}"
    shift || true
    
    case "$command" in
        create|add)
            local username="${1:-}"
            if [ -z "$username" ]; then
                log_error "Username required."
                exit 1
            fi
            local full_name="${2:-}"
            local shell="${3:-/bin/bash}"
            local groups="${4:-}"
            create_user "$username" "$full_name" "$shell" "$groups"
            ;;
        delete|remove)
            local username="${1:-}"
            if [ -z "$username" ]; then
                log_error "Username required."
                exit 1
            fi
            local keep_home="${2:-no}"
            delete_user "$username" "$keep_home"
            ;;
        set-password|passwd)
            local username="${1:-}"
            if [ -z "$username" ]; then
                log_error "Username required."
                exit 1
            fi
            local password="${2:-}"
            set_password "$username" "$password"
            ;;
        lock)
            local username="${1:-}"
            if [ -z "$username" ]; then
                log_error "Username required."
                exit 1
            fi
            lock_user "$username"
            ;;
        unlock)
            local username="${1:-}"
            if [ -z "$username" ]; then
                log_error "Username required."
                exit 1
            fi
            unlock_user "$username"
            ;;
        add-to-group|addgroup)
            local username="${1:-}"
            local group="${2:-}"
            if [ -z "$username" ] || [ -z "$group" ]; then
                log_error "Username and group required."
                exit 1
            fi
            add_to_group "$username" "$group"
            ;;
        remove-from-group|delgroup)
            local username="${1:-}"
            local group="${2:-}"
            if [ -z "$username" ] || [ -z "$group" ]; then
                log_error "Username and group required."
                exit 1
            fi
            remove_from_group "$username" "$group"
            ;;
        list|users)
            list_users
            ;;
        info|show)
            local username="${1:-}"
            if [ -z "$username" ]; then
                log_error "Username required."
                exit 1
            fi
            show_user_info "$username"
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