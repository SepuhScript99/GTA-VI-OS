#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# Visual Studio Code Installer for Vice OS
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -f "$WORKDIR/lib/common.sh" ]; then
    source "$WORKDIR/lib/common.sh"
elif [ -f "/usr/local/lib/common.sh" ]; then
    source "/usr/local/lib/common.sh"
else
    echo "Error: common.sh library not found." >&2
    exit 1
fi
install_cleanup

LOCKFILE="/var/lock/vp-code.lock"
TMP_KEYRING=""
TMP_DEARMORED=""

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    rm -f "$TMP_KEYRING" "$TMP_DEARMORED" 2>/dev/null || true
    if [ -f "$LOCKFILE" ]; then
        rm -f "$LOCKFILE" 2>/dev/null || true
    fi
    if [ $exit_code -eq 0 ]; then
        log_success "VS Code installation completed successfully."
    else
        log_error "VS Code installation failed with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Main ---
main() {
    if [[ "${1:-}" == "--version" ]]; then
        echo "Vice OS Code Installer v1.1"
        exit 0
    fi
    if [[ "${1:-}" == "--help" ]] || [[ "${1:-}" == "-h" ]]; then
        echo "Visual Studio Code Installer for Vice OS"
        echo "Usage: sudo $0"
        echo "Downloads Microsoft GPG keys, configures apt repository, and installs VS Code."
        exit 0
    fi

    check_root

    # Prevent concurrent execution
    exec 9>"$LOCKFILE"
    if ! flock -n 9; then
        log_warn "Another VS Code installer process is already running. Exiting."
        exit 0
    fi

    log_info "Installing Visual Studio Code..."

    # Verify dependencies using shared library (installs them if missing)
    check_dependencies "curl" "gpg" "dpkg" "apt-transport-https"

    # Create temp files securely
    TMP_KEYRING=$(mktemp)
    TMP_DEARMORED=$(mktemp)

    # Define safe apt options for lock timeouts
    local APT_OPTS=(
        "-o" "Dpkg::Lock::Timeout=60"
    )

    # Download GPG key securely with retries
    log_info "Downloading Microsoft GPG key..."
    if ! curl -fsSL --retry 3 --retry-delay 5 https://packages.microsoft.com/keys/microsoft.asc -o "$TMP_KEYRING"; then
        log_error "Failed to download Microsoft GPG key. Check your internet connection."
        exit 1
    fi

    log_info "Dearmoring GPG key..."
    if ! gpg --dearmor < "$TMP_KEYRING" > "$TMP_DEARMORED"; then
        log_error "Failed to dearmor GPG key. The downloaded key might be corrupted."
        exit 1
    fi

    # Safely install the keyring to the destination
    log_info "Installing GPG key to apt keyrings..."
    install -d -m 0755 /usr/share/keyrings
    install -m 0644 "$TMP_DEARMORED" /usr/share/keyrings/packages.microsoft.gpg

    # Add the repository with dynamic architecture detection
    log_info "Adding VS Code repository..."
    local ARCH
    ARCH=$(dpkg --print-architecture)
    install -d -m 0755 /etc/apt/sources.list.d
    echo "deb [arch=$ARCH signed-by=/usr/share/keyrings/packages.microsoft.gpg] https://packages.microsoft.com/repos/code stable main" > /etc/apt/sources.list.d/vscode.list
    chown root:root /etc/apt/sources.list.d/vscode.list
    chmod 644 /etc/apt/sources.list.d/vscode.list

    # Install VS Code
    log_info "Updating apt cache..."
    if ! apt-get "${APT_OPTS[@]}" update -qq; then
        log_error "Failed to update apt cache. Please check your network connection."
        exit 1
    fi

    log_info "Installing VS Code package..."
    # Use --no-install-recommends to keep the OS lightweight
    if ! apt-get "${APT_OPTS[@]}" install -y --no-install-recommends code; then
        log_error "Failed to install VS Code package."
        exit 1
    fi
}

main "$@"
