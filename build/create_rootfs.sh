#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) RootFS Creator
# Executes debootstrap to create the base Debian filesystem and stages the
# vice_payload directory for chroot configuration.
# ============================================================================

WORKDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$WORKDIR/lib/common.sh"
install_cleanup

# --- Arguments ---
CHROOTDIR="${1:?Error: CHROOTDIR argument required}"

# --- Main ---
main() {
    check_dependencies "debootstrap"

    local arch="${DEBIAN_ARCH:-amd64}"
    local suite="${DEBIAN_SUITE:-bookworm}"

    log_info "=== Starting RootFS Creation (${arch}) ==="

    # Step 1: Debootstrap minimal Debian (Bookworm) - with Retry + Fallback
    if [ ! -d "$CHROOTDIR/etc" ]; then
        log_info "Bootstrapping Debian ${suite} (${arch}) into $CHROOTDIR..."

        local debootstrap_args=("--arch=${arch}" "${suite}" "$CHROOTDIR")
        local primary_mirror="${DEBIAN_MIRROR:-http://deb.debian.org/debian/}"
        local fallback_mirror="http://ftp.us.debian.org/debian/"

        # Detect cross-architecture builds (e.g. ARM64 on x86_64 host)
        local host_arch
        host_arch=$(dpkg --print-architecture 2>/dev/null || uname -m)
        case "$host_arch" in
            x86_64|amd64) host_arch="amd64" ;;
            aarch64|arm64) host_arch="arm64" ;;
        esac

        local is_cross=false
        if [ "$arch" != "$host_arch" ]; then
            is_cross=true
            log_info "Cross-architecture build detected (host: $host_arch, target: $arch)."
            check_dependencies "qemu-user-static"
        fi

        # Helper to execute debootstrap with clean state on every retry
        run_debootstrap_with_retry() {
            local mirror="$1"
            local max_attempts="${2:-3}"
            local delay="${3:-10}"
            local attempt=1

            while [ "$attempt" -le "$max_attempts" ]; do
                log_info "Debootstrap attempt $attempt/$max_attempts using mirror: $mirror"
                # Clean chroot before running debootstrap to prevent 'target not empty' errors
                rm -rf "$CHROOTDIR"
                mkdir -p "$CHROOTDIR"

                if [ "$is_cross" = true ]; then
                    # Foreign stage 1 (download & unpack)
                    if debootstrap --foreign "${debootstrap_args[@]}" "$mirror"; then
                        local qemu_bin="/usr/bin/qemu-${arch}-static"
                        if [ "$arch" = "arm64" ]; then
                            qemu_bin="/usr/bin/qemu-aarch64-static"
                        fi
                        if [ -f "$qemu_bin" ]; then
                            mkdir -p "$CHROOTDIR/usr/bin"
                            cp "$qemu_bin" "$CHROOTDIR/usr/bin/"
                            chmod +x "$CHROOTDIR/usr/bin/$(basename "$qemu_bin")"
                        fi
                        # Stage 2 configuration inside chroot
                        if chroot "$CHROOTDIR" /debootstrap/debootstrap --second-stage; then
                            return 0
                        fi
                    fi
                else
                    if debootstrap "${debootstrap_args[@]}" "$mirror"; then
                        return 0
                    fi
                fi

                log_warn "Debootstrap attempt $attempt/$max_attempts failed."
                if [ "$attempt" -lt "$max_attempts" ]; then
                    log_info "Retrying in ${delay}s..."
                    sleep "$delay"
                    delay=$((delay * 2))
                fi
                ((attempt++))
            done
            return 1
        }

        if run_debootstrap_with_retry "$primary_mirror" 3 10; then
            log_success "Debootstrap completed using primary mirror."
        else
            log_warn "Primary mirror failed after retries. Trying fallback mirror..."
            if run_debootstrap_with_retry "$fallback_mirror" 3 10; then
                log_success "Debootstrap completed using fallback mirror."
            else
                log_error "Debootstrap failed on both mirrors after retries."
                exit 1
            fi
        fi
    else
        log_warn "Chroot directory already exists. Skipping debootstrap."
    fi

    # Step 2: Stage the vice_payload directory inside the chroot
    log_info "Staging project files into chroot payload..."

    # Clean up any existing payload to prevent stale files on resume
    rm -rf "$CHROOTDIR/vice_payload"
    mkdir -p "$CHROOTDIR/vice_payload"

    local dirs_to_copy=("config" "assets" "desktop" "apps" "system_scripts" "system_utils" "recovery" "lib" "chroot_scripts")
    for dir in "${dirs_to_copy[@]}"; do
        if [ -d "$WORKDIR/$dir" ]; then
            cp -r "$WORKDIR/$dir" "$CHROOTDIR/vice_payload/"
        else
            log_warn "Directory missing from workspace: $dir"
        fi
    done

    # Ensure all scripts in the payload are executable using find
    log_info "Setting executable permissions for payload scripts..."
    find "$CHROOTDIR/vice_payload" -type f \( -name "*.sh" -o -name "*.py" \) -exec chmod +x {} \;

    # Step 3: Write build metadata for chroot scripts
    log_info "Writing build metadata (arch=${arch})..."
    mkdir -p "$CHROOTDIR/etc"
    cat <<BUILD > "$CHROOTDIR/etc/vice-build.conf"
# Vice OS Build Configuration
# Written by create_rootfs.sh - DO NOT EDIT
DEBIAN_ARCH=${arch}
BUILD

    log_success "RootFS creation and payload staging completed."
}

main "$@"