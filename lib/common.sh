#!/bin/bash
# ============================================================================
# GTA VI OS (Vice OS) Common Bash Library
# Version: 1.0 Stable
#
# Provides shared logging, error handling, and validation utilities.
# This file should be sourced by other scripts, not executed directly.
# ============================================================================

# Prevent direct execution
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "This library is meant to be sourced, not executed directly."
    exit 1
fi

# Enforce strict mode globally for any script that sources this library
set -Eeuo pipefail
export DEBIAN_FRONTEND=noninteractive

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# --- Internal Logging Handler ---
__log() {
    local level="$1"
    local color="$2"
    local message="$3"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    local formatted_msg="${color}[${level}]${NC} ${message}"
    local log_entry="${timestamp} - [${level}] - ${message}"

    # Print to console
    echo -e "$formatted_msg"

    # Safely append to log file if the variable is set
    if [[ -n "${LOG_FILE:-}" ]]; then
        local log_dir
        log_dir=$(dirname "$LOG_FILE")
        # Ensure log directory exists, ignore errors if we can't create it
        if [[ ! -d "$log_dir" ]]; then
            mkdir -p "$log_dir" 2>/dev/null || true
        fi
        # Append log, ignore errors if file isn't writable
        echo "$log_entry" >> "$LOG_FILE" 2>/dev/null || true
    fi
}

# --- Public Logging Functions ---
log_info() {
    __log "INFO" "$BLUE" "$1"
}

log_success() {
    __log "SUCCESS" "$GREEN" "$1"
}

log_warn() {
    __log "WARN" "$YELLOW" "$1"
}

log_error() {
    __log "ERROR" "$RED" "$1" >&2
}

# --- Error Handler ---
# Callback for 'trap'. Captures line number and exit code.
common_error_handler() {
    local exit_code=$?
    local line_no=$1
    log_error "Command failed at line $line_no with exit code $exit_code."
}

# --- Validation Functions ---

check_root() {
    if [[ "${VICE_TESTING:-0}" == "1" || "${VICE_SKIP_ROOT_CHECK:-0}" == "1" ]]; then
        return 0
    fi
    if [[ "$EUID" -ne 0 ]]; then
        log_error "Please run this script as root (sudo)."
        exit 1
    fi
}

check_host() {
    if ! grep -Ei 'debian|ubuntu' /etc/os-release > /dev/null 2>&1; then
        log_warn "This script is designed for Debian/Ubuntu hosts. Proceeding anyway..."
    fi
}

# Args: $1 = domain to test (e.g., deb.debian.org)
check_internet() {
    local domain="${1:-deb.debian.org}"
    log_info "Checking internet connection to ${domain}..."

    # Use getent (part of libc-bin, always installed) to check DNS resolution.
    # This avoids a hard dependency on curl/ping for the check itself.
    if ! getent hosts "$domain" > /dev/null 2>&1; then
        log_error "No internet connection or DNS resolution failed for ${domain}."
        exit 1
    fi
}

# Args: $1 = path to check, $2 = required space in GB
check_disk_space() {
    local path="${1:-$PWD}"
    local required_gb="${2:-10}"

    local available_gb
    # Use --output=avail for robust parsing, -BG for gigabyte blocks
    available_gb=$(df --output=avail -BG "$path" | tail -n 1 | tr -dc '0-9')

    if [[ "$available_gb" -lt "$required_gb" ]]; then
        log_error "Insufficient disk space. Required: ${required_gb}GB, Available: ${available_gb}GB"
        exit 1
    fi
}

# Args: $1...$N = dependencies
check_dependencies() {
    if [[ "${VICE_TESTING:-0}" == "1" || "${VICE_SKIP_DEP_CHECK:-0}" == "1" ]]; then
        return 0
    fi
    local deps=("$@")
    local missing=()

    for dep in "${deps[@]}"; do
        if ! command -v "$dep" > /dev/null 2>&1; then
            missing+=("$dep")
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        log_warn "Missing dependencies: ${missing[*]}"
        if command -v apt-get > /dev/null 2>&1; then
            log_info "Installing missing dependencies via apt-get..."
            # Update cache first to prevent 404s on stale hosts
            apt-get update
            # Use --no-install-recommends to keep the system lightweight
            apt-get install -y --no-install-recommends "${missing[@]}"
        else
            log_error "apt-get not found. Please install the missing dependencies manually."
            exit 1
        fi
    fi
}

# Args: $1...$N = commands to check
# Usage: check_command "wget" "curl" || exit 1
check_command() {
    local cmds=("$@")
    local missing=()

    for cmd in "${cmds[@]}"; do
        if ! command -v "$cmd" > /dev/null 2>&1; then
            missing+=("$cmd")
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Required commands not found: ${missing[*]}"
        return 1
    fi
    return 0
}

# --- Initialization Helpers ---

# Resolves the project root directory based on the calling script's location.
# Sources lib/common.sh from the resolved path.
# Usage: eval "$(init_script "$(dirname "${BASH_SOURCE[0]}")")"
# Returns: WORKDIR as an exported variable
init_script() {
    local script_dir="$1"
    local workdir
    workdir="$(cd "$script_dir/.." && pwd)"
    if [ ! -f "$workdir/lib/common.sh" ]; then
        echo "Error: lib/common.sh not found at $workdir/lib/common.sh" >&2
        exit 1
    fi
    echo "WORKDIR=\"$workdir\""
}

# Installs a default cleanup trap that logs failure and exits.
# Can be overridden by defining a cleanup() function before calling.
install_cleanup() {
    if ! declare -F cleanup > /dev/null 2>&1; then
        eval "$(cat <<'CLEANUP'
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Operation failed with exit code $exit_code."
    fi
    exit $exit_code
}
CLEANUP
)"
    fi
    trap cleanup EXIT SIGINT SIGTERM
}

# Convenience: calls init_script and install_cleanup in one step.
# Usage: eval "$(bootstrap_script "$(dirname "${BASH_SOURCE[0]}")")"
bootstrap_script() {
    init_script "$1"
    echo "source \"\$WORKDIR/lib/common.sh\""
    echo 'install_cleanup'
}

# --- Utility Functions ---

# Returns a compact UTC timestamp string (e.g., 2026-07-23_14-30-00)
get_timestamp() {
    date '+%Y-%m-%d_%H-%M-%S'
}

# Args: $1 = max_attempts, $2 = initial_delay (seconds), remaining args = command
# Retries a command with exponential backoff on failure.
# Example: retry_command 3 5 apt-get install -y firefox
retry_command() {
    local max_attempts="${1:-3}"
    local delay="${2:-5}"
    shift 2 || true

    local attempt=1
    local cmd=("$@")

    while [[ $attempt -le $max_attempts ]]; do
        if "${cmd[@]}"; then
            return 0
        fi

        if [[ $attempt -lt $max_attempts ]]; then
            log_warn "Command failed (attempt $attempt/$max_attempts). Retrying in ${delay}s..."
            sleep "$delay"
            delay=$((delay * 2))
        else
            log_error "Command failed after $max_attempts attempts: ${cmd[*]}"
            return 1
        fi
        ((attempt++))
    done
}