#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# Docker Engine Installer for Vice OS
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Source Shared Library ---
if [ ! -f "$WORKDIR/lib/common.sh" ]; then
    echo "Error: lib/common.sh not found. Cannot continue." >&2
    exit 1
fi
source "$WORKDIR/lib/common.sh"

# Initialize temp variables BEFORE trap to avoid unbound variable errors in cleanup
TMP_KEYRING=""
TMP_DEARMORED=""

# --- Cleanup Function ---
cleanup() {
    local exit_code=$?
    rm -f "$TMP_KEYRING" "$TMP_DEARMORED" 2>/dev/null || true
    if [ $exit_code -eq 0 ]; then
        log_success "Docker installation completed successfully."
    else
        log_error "Docker installation failed with exit code $exit_code."
    fi
    exit $exit_code
}

trap cleanup EXIT SIGINT SIGTERM

# --- Main ---
main() {
    check_root
    log_info "Installing Docker Engine..."

    # Verify dependencies using shared library (including iptables for Docker networking)
    check_dependencies "curl" "gpg" "dpkg" "apt-transport-https" "ca-certificates" "iptables"

    # Create temp files securely
    TMP_KEYRING=$(mktemp)
    TMP_DEARMORED=$(mktemp)

    # Define safe apt options for lock timeouts
    local APT_OPTS=(
        "-o" "Dpkg::Lock::Timeout=60"
    )

    # Download GPG key securely with retries
    log_info "Downloading Docker GPG key..."
    if ! curl -fsSL --retry 3 --retry-delay 5 https://download.docker.com/linux/debian/gpg -o "$TMP_KEYRING"; then
        log_error "Failed to download Docker GPG key. Check your internet connection."
        exit 1
    fi

    log_info "Deadoring GPG key..."
    if ! gpg --dearmor < "$TMP_KEYRING" > "$TMP_DEARMORED"; then
        log_error "Failed to dearmor GPG key. The downloaded key might be corrupted."
        exit 1
    fi
    
    # Safely install the keyring to the destination
    log_info "Installing GPG key to apt keyrings..."
    install -d -m 0755 /etc/apt/keyrings
    install -m 0644 "$TMP_DEARMORED" /etc/apt/keyrings/docker.gpg

    # Add the repository using declarative configuration file
    log_info "Adding Docker repository..."
    local repo_src="$WORKDIR/config/apt/sources.list.d/docker.list"
    if [ -f "$repo_src" ]; then
        install -d -m 0755 /etc/apt/sources.list.d
        cp "$repo_src" /etc/apt/sources.list.d/docker.list
        chown root:root /etc/apt/sources.list.d/docker.list
        chmod 644 /etc/apt/sources.list.d/docker.list
    else
        log_error "Repository config missing: $repo_src"
        exit 1
    fi

    # Update apt cache
    log_info "Updating apt cache..."
    if ! apt-get "${APT_OPTS[@]}" update -qq; then
        log_error "Failed to update apt cache. Please check your network connection."
        exit 1
    fi

    # Configure Docker daemon for production safety (log rotation) BEFORE installing/starting
    log_info "Configuring Docker daemon log rotation..."
    mkdir -p /etc/docker
    cat <<JSON > /etc/docker/daemon.json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
JSON

    # Install Docker Engine
    log_info "Installing Docker packages..."
    # Use --no-install-recommends to keep the OS lightweight
    if ! apt-get "${APT_OPTS[@]}" install -y --no-install-recommends docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin; then
        log_error "Failed to install Docker packages."
        exit 1
    fi

    # Add vice user to docker group
    if id -u vice >/dev/null 2>&1; then
        log_info "Adding user 'vice' to docker group..."
        usermod -aG docker vice
    else
        log_warn "User 'vice' does not exist. Skipping docker group assignment."
    fi

    # Enable and start the service (applies daemon.json on first start)
    log_info "Enabling and starting Docker service..."
    systemctl enable --now docker

    # Verify service status
    if systemctl is-active --quiet docker; then
        log_success "Docker installed and started successfully."
    else
        log_error "Docker installed, but the service failed to start. Check 'systemctl status docker'."
    fi
    
    log_warn "If you added a user to the docker group, please log out and log back in for changes to take effect."
}

main "$@"