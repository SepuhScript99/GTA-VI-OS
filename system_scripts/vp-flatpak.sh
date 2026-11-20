#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# Vice OS Flatpak Integration Script
# Installs Flatpak, adds Flathub, and optionally installs common Flatpak apps.
# Can be run standalone or triggered by the welcome wizard.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

LOCKFILE="/var/lock/vp-flatpak.lock"
FLATHUB_REPO="https://flathub.org/repo/flathub.flatpakrepo"
FLATHUB_GPG="https://flathub.org/repo/flathub.gpg"

cleanup() {
    local exit_code=$?
    exec 9>&- 2>/dev/null || true
    rm -f "$LOCKFILE" 2>/dev/null || true
    exit $exit_code
}
trap cleanup EXIT SIGINT SIGTERM

show_help() {
    cat <<HELP
Vice OS Flatpak Integration Utility

Usage: $0 [options] [app-id ...]

Options:
  help, --help, -h   Show this help message

Arguments:
  app-id             Flatpak application ID(s) to install (e.g. org.mozilla.firefox)

Examples:
  $0
  $0 org.mozilla.firefox
  $0 com.spotify.Client org.videolan.VLC
HELP
}

main() {
    if [ "${1:-}" = "help" ] || [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
        show_help
        exit 0
    fi

    check_root

    exec 9>"$LOCKFILE"
    if ! flock -n 9; then
        log_warn "Another Flatpak process is already running. Exiting."
        exit 0
    fi

    log_info "=== Setting up Flatpak support ==="

    # 1. Install Flatpak
    log_info "Installing Flatpak..."
    if command -v flatpak > /dev/null 2>&1; then
        log_info "Flatpak already installed."
    else
        local APT_OPTS=(
            "-o" "Acquire::Retries=3"
            "-o" "Acquire::http::Timeout=30"
            "-o" "Acquire::https::Timeout=30"
            "-o" "Dpkg::Lock::Timeout=120"
        )
        if ! apt-get "${APT_OPTS[@]}" install -y --no-install-recommends flatpak; then
            log_error "Failed to install Flatpak."
            exit 1
        fi
        log_success "Flatpak installed."
    fi

    # 2. Add Flathub repository
    log_info "Adding Flathub repository..."
    if flatpak remotes --system 2>/dev/null | grep -q "flathub"; then
        log_info "Flathub repository already configured."
    else
        if flatpak remote-add --if-not-exists --system flathub "$FLATHUB_REPO" 2>/dev/null; then
            log_success "Flathub repository added."
        else
            log_warn "Could not add Flathub via flatpakrepo. Trying direct GPG method..."
            flatpak remote-add --if-not-exists --system flathub "https://dl.flathub.org/repo/" --from="https://flathub.org/repo/flathub.flatpakrepo" 2>/dev/null || log_warn "Flathub addition failed. User can add manually."
        fi
    fi

    # 3. Check if any common apps should be installed
    local install_apps=()
    if [ $# -gt 0 ]; then
        install_apps=("$@")
        log_info "Installing requested Flatpak apps: ${install_apps[*]}"
for app in "${install_apps[@]}"; do
            if ! [[ "$app" =~ ^[a-zA-Z0-9_.-]+$ ]] || [[ "$app" =~ ^- ]]; then
                log_warn "Invalid Flatpak app ID: $app. Skipping."
                continue
            fi
            log_info "Installing: $app"
            if flatpak install --system --noninteractive flathub "$app" 2>/dev/null; then
                log_success "Installed: $app"
            else
                log_warn "Failed to install: $app"
            fi
        done
    fi

    log_success "=== Flatpak setup complete ==="
    log_info "Applications can be installed with: flatpak install <app-id>"
    log_info "Browse available apps at: https://flathub.org"
}

main "$@"
