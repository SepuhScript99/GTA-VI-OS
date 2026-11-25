#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Chroot Script: Package Installation
# Installs core system packages, kernel, and applications from packages.list.
# ============================================================================

# Source the shared library from the payload directory
if [ ! -f /vice_payload/lib/common.sh ]; then
    echo "Error: /vice_payload/lib/common.sh not found." >&2
    exit 1
fi
source /vice_payload/lib/common.sh

# Prevent interactive prompts during package installation
export DEBIAN_FRONTEND=noninteractive

# Pre-seed timezone and non-interactive package defaults before packages install
echo "tzdata tzdata/Areas select Etc" | debconf-set-selections
echo "tzdata tzdata/Zones/Etc select UTC" | debconf-set-selections
echo "macchanger macchanger/automatically_run boolean false" | debconf-set-selections
echo "wireshark-common wireshark-common/install-setuid boolean false" | debconf-set-selections

# Define safe apt options for retries and lock timeouts
APT_OPTS=(
    "-o" "Acquire::Retries=3"
    "-o" "Dpkg::Lock::Timeout=300"
    "-o" "Dpkg::Options::=--force-confold"
    "-o" "Dpkg::Options::=--force-confdef"
)

has_install_candidate() {
    local pkg="$1"
    local candidate
    candidate=$(apt-cache policy "$pkg" 2>/dev/null | awk '/Candidate:/ {if (!c) c=$2} END {print c}')
    [ -n "$candidate" ] && [ "$candidate" != "(none)" ]
}

refresh_external_repo_list() {
    local list_path="$1"
    local label="$2"
    if ! apt-get "${APT_OPTS[@]}" update \
        -o Dir::Etc::sourcelist="$list_path" \
        -o Dir::Etc::sourceparts="-" \
        -o APT::Get::List-Cleanup="0"; then
        log_warn "External repo unreachable (${label}); removing ${list_path} and continuing with Debian fallback."
        rm -f "$list_path"
        return 1
    fi
    return 0
}

configure_dev_repos() {
    local build_arch="$1"
    local deb_arch
    deb_arch=$(dpkg --print-architecture 2>/dev/null || echo "$build_arch")

    log_info "Configuring official developer repositories (VS Code, .NET 8.0, Node.js 22 LTS)..."
    echo "code code/add-microsoft-repo boolean true" | debconf-set-selections

    apt-get "${APT_OPTS[@]}" install -y --no-install-recommends \
        ca-certificates curl gnupg apt-transport-https

    install -d -m 0755 /usr/share/keyrings /etc/apt/sources.list.d

    local tmp_ms_key tmp_ns_key tmp_gnupg
    tmp_ms_key=$(mktemp)
    tmp_ns_key=$(mktemp)
    tmp_gnupg=$(mktemp -d)
    chmod 700 "$tmp_gnupg"

    if curl -fsSL --retry 3 --retry-delay 5 https://packages.microsoft.com/keys/microsoft.asc -o "$tmp_ms_key" \
        && gpg --homedir "$tmp_gnupg" --batch --yes --dearmor < "$tmp_ms_key" > /usr/share/keyrings/packages.microsoft.gpg; then
        chmod 644 /usr/share/keyrings/packages.microsoft.gpg
        printf 'deb [arch=%s signed-by=/usr/share/keyrings/packages.microsoft.gpg] https://packages.microsoft.com/repos/code stable main\n' \
            "$deb_arch" > /etc/apt/sources.list.d/vscode.list
        printf 'deb [arch=%s signed-by=/usr/share/keyrings/packages.microsoft.gpg] https://packages.microsoft.com/debian/12/prod bookworm main\n' \
            "$deb_arch" > /etc/apt/sources.list.d/microsoft-prod.list
        chmod 644 /etc/apt/sources.list.d/vscode.list /etc/apt/sources.list.d/microsoft-prod.list
        refresh_external_repo_list "/etc/apt/sources.list.d/vscode.list" "Microsoft VS Code" || true
        refresh_external_repo_list "/etc/apt/sources.list.d/microsoft-prod.list" "Microsoft Debian 12 Prod (.NET 8.0)" || true
    else
        rm -f /usr/share/keyrings/packages.microsoft.gpg
        log_warn "Failed to fetch Microsoft GPG key; skipping VS Code and Microsoft .NET apt repos."
    fi

    if curl -fsSL --retry 3 --retry-delay 5 https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key -o "$tmp_ns_key" \
        && gpg --homedir "$tmp_gnupg" --batch --yes --dearmor < "$tmp_ns_key" > /usr/share/keyrings/nodesource.gpg; then
        chmod 644 /usr/share/keyrings/nodesource.gpg
        printf 'deb [signed-by=/usr/share/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main\n' \
            > /etc/apt/sources.list.d/nodesource.list
        chmod 644 /etc/apt/sources.list.d/nodesource.list
        refresh_external_repo_list "/etc/apt/sources.list.d/nodesource.list" "NodeSource Node.js 22 LTS" || true
    else
        rm -f /usr/share/keyrings/nodesource.gpg
        log_warn "Failed to fetch NodeSource GPG key; falling back to Debian Bookworm Node.js."
    fi

    rm -rf "$tmp_ms_key" "$tmp_ns_key" "$tmp_gnupg"
}

install_debian_nodejs_fallback() {
    local fb_node=()
    local pkg
    for pkg in nodejs npm node-typescript; do
        if has_install_candidate "$pkg"; then
            fb_node+=("$pkg")
        fi
    done
    if [ "${#fb_node[@]}" -gt 0 ]; then
        apt-get "${APT_OPTS[@]}" install -y --no-install-recommends "${fb_node[@]}" || true
    fi
}

install_dev_suite() {
    log_info "Installing official VS Code, .NET 8.0 LTS SDK, and Node.js 22 LTS + TypeScript..."

    if has_install_candidate code; then
        if ! apt-get "${APT_OPTS[@]}" install -y --no-install-recommends code; then
            log_warn "VS Code installation failed; continuing without blocking ISO build."
        fi
    else
        log_warn "VS Code package candidate unavailable; skipping."
    fi

    if has_install_candidate dotnet-sdk-8.0; then
        if ! apt-get "${APT_OPTS[@]}" install -y --no-install-recommends dotnet-sdk-8.0; then
            log_warn "dotnet-sdk-8.0 installation failed; falling back to mono-devel if available."
            if has_install_candidate mono-devel; then
                apt-get "${APT_OPTS[@]}" install -y --no-install-recommends mono-devel || true
            fi
        fi
    else
        log_warn "dotnet-sdk-8.0 unavailable; falling back to mono-devel if available."
        if has_install_candidate mono-devel; then
            apt-get "${APT_OPTS[@]}" install -y --no-install-recommends mono-devel || true
        fi
    fi

    # NodeSource nodejs 22.x Provides: npm and Conflicts: npm (never install Debian npm alongside it).
    # Read apt-cache policy into a variable to avoid SIGPIPE under set -o pipefail.
    local node_policy=""
    node_policy=$(apt-cache policy nodejs 2>/dev/null || true)
    if [[ "$node_policy" == *"nodesource"* ]]; then
        if apt-get "${APT_OPTS[@]}" install -y --no-install-recommends nodejs; then
            if command -v npm >/dev/null 2>&1; then
                log_info "Installing global TypeScript compiler via npm..."
                local npm_cache_dir
                npm_cache_dir=$(mktemp -d)
                npm_config_cache="$npm_cache_dir" npm install -g typescript --no-audit --no-fund || true
                rm -rf "$npm_cache_dir" /root/.npm 2>/dev/null || true
            else
                log_warn "npm unavailable after NodeSource nodejs install; skipping global TypeScript."
            fi
        else
            log_warn "NodeSource Node.js 22 LTS install failed; checking Debian fallback."
            rm -f /etc/apt/sources.list.d/nodesource.list /var/lib/apt/lists/*nodesource* 2>/dev/null || true
            install_debian_nodejs_fallback
        fi
    else
        log_warn "NodeSource Node.js 22 LTS repo unavailable; installing Debian Bookworm nodejs + npm + node-typescript fallback."
        install_debian_nodejs_fallback
    fi

    apt-get clean
}

install_kernel_and_firmware() {
    local build_arch="$1"
    local kernel_pkg="$2"
    local headers_pkg="$3"

    log_info "Installing kernel and firmware (${build_arch}; preferring pinned bookworm-backports LTS)..."

    # Ensure 90-vice-backports-kernel pinning is active even if 01 runs standalone
    if [ -d /vice_payload/config/apt/preferences.d ]; then
        mkdir -p /etc/apt/preferences.d
        local pref_file
        for pref_file in /vice_payload/config/apt/preferences.d/*; do
            if [ -f "$pref_file" ]; then
                cp "$pref_file" "/etc/apt/preferences.d/$(basename "$pref_file")"
                chown root:root "/etc/apt/preferences.d/$(basename "$pref_file")"
                chmod 644 "/etc/apt/preferences.d/$(basename "$pref_file")"
            fi
        done
    fi

    local kernel_pkgs=("${kernel_pkg}" "${headers_pkg}" "initramfs-tools" "firmware-linux" "firmware-misc-nonfree")
    local selected_pkgs=()
    local pkg candidate
    for pkg in "${kernel_pkgs[@]}"; do
        if has_install_candidate "$pkg"; then
            candidate=$(apt-cache policy "$pkg" 2>/dev/null | awk '/Candidate:/ {if (!c) c=$2} END {print c}')
            log_info "  ${pkg} candidate: ${candidate:-unknown}"
            selected_pkgs+=("$pkg")
        else
            log_warn "Kernel/firmware package unavailable, skipping: $pkg"
        fi
    done

    if [ "${#selected_pkgs[@]}" -gt 0 ]; then
        if ! apt-get "${APT_OPTS[@]}" install -y --no-install-recommends "${selected_pkgs[@]}"; then
            log_warn "Backports kernel/firmware install hit a resolution error; falling back cleanly to standard bookworm..."
            apt-get "${APT_OPTS[@]}" install -y --no-install-recommends -t bookworm "${selected_pkgs[@]}"
        fi
    fi
}

main() {
    # Read build configuration
    local build_arch="amd64"
    if [ -f /etc/vice-build.conf ]; then
        source /etc/vice-build.conf
        build_arch="${DEBIAN_ARCH:-amd64}"
    fi
    log_info "Build architecture: ${build_arch}"

    local kernel_pkg="linux-image-amd64"
    local headers_pkg="linux-headers-amd64"
    if [ "${build_arch}" = "arm64" ]; then
        kernel_pkg="linux-image-arm64"
        headers_pkg="linux-headers-arm64"
    fi

    log_info "Installing live-boot BEFORE kernel..."
    # live-boot must be present before the kernel package triggers initramfs generation
    apt-get "${APT_OPTS[@]}" install -y --no-install-recommends live-boot live-config

    install_kernel_and_firmware "${build_arch}" "${kernel_pkg}" "${headers_pkg}"

    log_info "Installing bootloader and installer prerequisites (${build_arch})..."
    local core_infra_candidates=("grub2-common" "dosfstools" "parted" "cryptsetup" "rsync" "whiptail")
    if [ "${build_arch}" = "arm64" ]; then
        core_infra_candidates+=("grub-efi-arm64-bin")
    else
        core_infra_candidates+=("grub-pc-bin" "grub-efi-amd64-bin")
    fi

    local core_infra_pkgs=()
    for pkg in "${core_infra_candidates[@]}"; do
        if has_install_candidate "$pkg"; then
            core_infra_pkgs+=("$pkg")
        else
            log_warn "Prerequisite package unavailable in current Debian suite, skipping: $pkg"
        fi
    done
    if [ "${#core_infra_pkgs[@]}" -gt 0 ]; then
        apt-get "${APT_OPTS[@]}" install -y --no-install-recommends "${core_infra_pkgs[@]}"
    fi

    log_info "Installing packages from list..."
    if [ ! -f /vice_payload/config/packages.list ]; then
        log_error "packages.list not found in payload!"
        exit 1
    fi

    # Collect candidate packages (append ARM64 list and filter x86-only packages on ARM64)
    local pkg_list="/vice_payload/config/packages.list"
    local list_files=("$pkg_list")
    if [ "${build_arch}" = "arm64" ] && [ -f /vice_payload/config/packages.arm64.list ]; then
        log_info "Appending ARM64-specific packages and filtering x86-only packages..."
        list_files+=("/vice_payload/config/packages.arm64.list")
    fi

    local available_pkgs=()
    local pkg_line=""
    while IFS= read -r pkg_line || [ -n "$pkg_line" ]; do
        pkg_line="${pkg_line%%#*}"
        pkg_line="${pkg_line//[[:space:]]/}"
        [ -z "$pkg_line" ] && continue

        if [ "${build_arch}" = "arm64" ]; then
            case "$pkg_line" in
                virtualbox-guest-utils|virtualbox-guest-x11|xserver-xorg-video-vmware|xserver-xorg-video-vboxvideo|intel-microcode|amd64-microcode)
                    continue
                    ;;
            esac
        fi

        if has_install_candidate "$pkg_line"; then
            available_pkgs+=("$pkg_line")
        else
            log_warn "Package unavailable in current Debian suite, skipping: $pkg_line"
        fi
    done < <(cat "${list_files[@]}")

    if [ "${#available_pkgs[@]}" -gt 0 ]; then
        apt-get "${APT_OPTS[@]}" install -y --no-install-recommends "${available_pkgs[@]}"
    fi
    apt-get clean

    configure_dev_repos "${build_arch}"
    install_dev_suite

    log_info "Generating locales..."
    # Ensure locales package is installed before trying to generate
    apt-get "${APT_OPTS[@]}" install -y --no-install-recommends locales
    if grep -q "# en_US.UTF-8 UTF-8" /etc/locale.gen; then
        sed -i 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen
    elif ! grep -q "^en_US.UTF-8 UTF-8" /etc/locale.gen; then
        echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen
    fi
    locale-gen

    log_info "Installing default locale configuration..."
    if [ -f /vice_payload/config/default/locale ]; then
        mkdir -p /etc/default
        cp /vice_payload/config/default/locale /etc/default/locale
        chown root:root /etc/default/locale
        chmod 644 /etc/default/locale
        # Update the active environment
        update-locale LANG=en_US.UTF-8
    else
        log_warn "config/default/locale not found in payload!"
    fi

    log_info "Installing default keyboard configuration..."
    if [ -f /vice_payload/config/default/keyboard ]; then
        mkdir -p /etc/default
        cp /vice_payload/config/default/keyboard /etc/default/keyboard
        chown root:root /etc/default/keyboard
        chmod 644 /etc/default/keyboard
        # Ensure console-setup is installed and apply the config
        apt-get "${APT_OPTS[@]}" install -y --no-install-recommends console-setup keyboard-configuration
        setupcon --save 2>/dev/null || true
    else
        log_warn "config/default/keyboard not found in payload!"
    fi

    log_info "Setting timezone to UTC (universal default)..."
    # tzdata was pre-seeded, but we ensure it's installed and configured cleanly
    apt-get "${APT_OPTS[@]}" install -y --no-install-recommends tzdata
    rm -f /etc/localtime
    ln -s /usr/share/zoneinfo/Etc/UTC /etc/localtime
    dpkg-reconfigure -f noninteractive tzdata

    log_success "Package installation completed."
}

main "$@"
