#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Universal Hardware & Multi-VM Auto-Detect
# Installed to /usr/local/system_scripts/vice-hw-autodetect.sh
# Symlinked at /usr/local/bin/vice-hw-autodetect
# ============================================================================

VERSION="1.0.0"

case ":$PATH:" in
    *":/usr/sbin:"*) ;;
    *) PATH="$PATH:/usr/local/sbin:/usr/sbin:/sbin" ;;
esac
export PATH

LOG_FILE="${VICE_HW_LOG_FILE:-/var/log/vice-hw-autodetect.log}"
DISPATCHER_TUNE="${VICE_HW_DISPATCHER:-/etc/NetworkManager/dispatcher.d/80-vice-net-tune}"
LOCK_FILE="${VICE_HW_LOCK_FILE:-/run/lock/vice-hw-autodetect.lock}"
SYS_NET_DIR="${VICE_NET_SYS_DIR:-/sys/class/net}"

ACTIONS_LOG=()

log_info() {
    printf '[INFO] %s\n' "$1"
    ACTIONS_LOG+=("[INFO] $1")
}

log_warn() {
    printf '[WARN] %s\n' "$1" >&2
    ACTIONS_LOG+=("[WARN] $1")
}

log_error() {
    printf '[ERROR] %s\n' "$1" >&2
}

show_help() {
    cat <<'HELP'
GTA VI OS (Vice OS) Universal Hardware & Multi-VM Auto-Detect

Usage:
  vice-hw-autodetect --apply     Detect VM/bare-metal environment, unblock radios,
                                 bind missing drivers, auto-connect NICs, and
                                 manage hypervisor guest services
  vice-hw-autodetect --status    Show detected platform, NICs, tuning, and guest services
  vice-hw-autodetect --help      Show this help message and exit
  vice-hw-autodetect --version   Show version information and exit

Notes:
  - Runs automatically at boot via vice-hw-autodetect.service.
  - Preserves ISO #12/#13 audio settings (snd-intel8x0 ac97_clock=48000 / PipeWire).
HELP
}

show_version() {
    printf 'vice-hw-autodetect v%s (GTA VI OS Universal Hardware & VM Auto-Detect)\n' "$VERSION"
}

check_root() {
    if [ "${VICE_TESTING:-0}" = "1" ] || [ "${VICE_SKIP_ROOT_CHECK:-0}" = "1" ]; then
        return 0
    fi
    if [ "${EUID:-$(id -u)}" -ne 0 ]; then
        log_error "Root privileges are required for --apply (use sudo or pkexec)."
        exit 1
    fi
}

acquire_lock() {
    local lock_dir
    lock_dir=$(dirname "$LOCK_FILE")
    if ! mkdir -p "$lock_dir" 2>/dev/null; then
        return 0
    fi
    if command -v flock >/dev/null 2>&1; then
        exec 9>"$LOCK_FILE"
        if ! flock -w 10 9; then
            log_warn "Another vice-hw-autodetect instance is running; skipping."
            exit 0
        fi
    fi
}

read_dmi_field() {
    local field="$1"
    local dmi_path="/sys/class/dmi/id/${field}"
    if [ -r "$dmi_path" ]; then
        tr -d '\0\r\n' < "$dmi_path" 2>/dev/null || true
    fi
}

detect_virt_platform() {
    if [ -n "${VICE_HW_VIRT_OVERRIDE:-}" ]; then
        printf '%s' "$VICE_HW_VIRT_OVERRIDE"
        return 0
    fi

    local virt=""
    if command -v systemd-detect-virt >/dev/null 2>&1; then
        virt=$(systemd-detect-virt 2>/dev/null || true)
    fi

    case "$virt" in
        oracle|vmware|kvm|qemu|microsoft|xen|bochs|bhyve)
            printf '%s' "$virt"
            return 0
            ;;
    esac

    if [ -e /dev/vboxguest ]; then
        printf 'oracle'
        return 0
    fi

    local vendor product board combined
    vendor=$(read_dmi_field "sys_vendor")
    product=$(read_dmi_field "product_name")
    board=$(read_dmi_field "board_name")
    combined="${vendor} ${product} ${board}"

    case "$combined" in
        *VirtualBox*|*innotek*)
            printf 'oracle'
            return 0
            ;;
        *VMware*)
            printf 'vmware'
            return 0
            ;;
        *QEMU*|*KVM*|*Bochs*)
            printf 'kvm'
            return 0
            ;;
        *Microsoft*"Virtual Machine"*|*"Virtual Machine"*Microsoft*)
            printf 'microsoft'
            return 0
            ;;
    esac

    printf 'none'
}

platform_label() {
    case "$1" in
        oracle) printf 'VirtualBox (oracle)' ;;
        vmware) printf 'VMware (vmware)' ;;
        kvm|qemu) printf 'KVM/QEMU (%s)' "$1" ;;
        microsoft) printf 'Hyper-V (microsoft)' ;;
        none) printf 'Bare Metal / Physical Hardware (none)' ;;
        *) printf 'Virtualization (%s)' "$1" ;;
    esac
}

is_ignored_iface() {
    local dev="$1"
    local dev_type="${2:-}"
    case "$dev" in
        ""|lo|docker*|br-*|virbr*|veth*|tun*|tap*|wg*|vboxnet*|vmnet*)
            return 0
            ;;
    esac
    case "$dev_type" in
        loopback|bridge|tun|tap|veth|dummy|wireguard)
            return 0
            ;;
    esac
    return 1
}

probe_vm_guest_modules() {
    local platform="$1"
    if ! command -v modprobe >/dev/null 2>&1; then
        return 0
    fi

    # Probe hypervisor guest kernel modules cleanly if present; let native
    # systemd-udevd handle all PCI/USB hardware driver binding automatically.
    local vm_mods=()
    case "$platform" in
        oracle)
            vm_mods=("vboxguest" "vboxsf")
            ;;
        vmware)
            vm_mods=("vmw_vmci" "vmxnet3")
            ;;
        kvm|qemu)
            vm_mods=("virtio_net" "virtio_console")
            ;;
        microsoft)
            vm_mods=("hv_netvsc" "hv_utils")
            ;;
    esac

    local mod
    for mod in "${vm_mods[@]}"; do
        modprobe -q "$mod" >/dev/null 2>&1 || true
    done
}

unblock_and_settle() {
    local platform="$1"

    if command -v rfkill >/dev/null 2>&1; then
        rfkill unblock all >/dev/null 2>&1 || true
    fi

    if command -v udevadm >/dev/null 2>&1; then
        udevadm settle --timeout=5 >/dev/null 2>&1 || true
    fi

    probe_vm_guest_modules "$platform"

    if command -v udevadm >/dev/null 2>&1; then
        udevadm settle --timeout=3 >/dev/null 2>&1 || true
    fi

    if command -v rfkill >/dev/null 2>&1; then
        rfkill unblock all >/dev/null 2>&1 || true
    fi

    log_info "Native udev hardware settled and wireless radios unblocked."
}

unit_is_installed() {
    local unit="$1"
    if ! command -v systemctl >/dev/null 2>&1; then
        return 1
    fi
    systemctl cat "$unit" >/dev/null 2>&1
}

activate_guest_unit() {
    local unit="$1"
    if ! unit_is_installed "$unit"; then
        return 0
    fi
    systemctl unmask --runtime "$unit" >/dev/null 2>&1 || true
    systemctl unmask "$unit" >/dev/null 2>&1 || true
    systemctl reset-failed "$unit" >/dev/null 2>&1 || true
    systemctl start --no-block "$unit" >/dev/null 2>&1 || systemctl start "$unit" >/dev/null 2>&1 || true
    log_info "Activated matching guest unit: $unit"
}

mask_irrelevant_unit() {
    local unit="$1"
    if ! unit_is_installed "$unit"; then
        return 0
    fi
    systemctl stop "$unit" >/dev/null 2>&1 || true
    systemctl reset-failed "$unit" >/dev/null 2>&1 || true
    systemctl mask --runtime "$unit" >/dev/null 2>&1 || systemctl mask "$unit" >/dev/null 2>&1 || true
}

manage_guest_services() {
    local platform="$1"

    if ! command -v systemctl >/dev/null 2>&1 || [ ! -d /run/systemd/system ]; then
        log_info "systemd runtime not active; skipping hypervisor service orchestration."
        return 0
    fi

    local active_units=()
    local masked_units=()

    case "$platform" in
        oracle)
            active_units+=("virtualbox-guest-utils.service" "vboxadd-service.service")
            masked_units+=(
                "open-vm-tools.service" "vgauth.service"
                "qemu-guest-agent.service" "spice-vdagentd.service" "spice-vdagentd.socket"
                "hv-kvp-daemon.service" "hv-vss-daemon.service" "hv-fcopy-daemon.service"
            )
            ;;
        vmware)
            active_units+=("open-vm-tools.service" "vgauth.service")
            masked_units+=(
                "virtualbox-guest-utils.service" "vboxadd-service.service"
                "qemu-guest-agent.service" "spice-vdagentd.service" "spice-vdagentd.socket"
                "hv-kvp-daemon.service" "hv-vss-daemon.service" "hv-fcopy-daemon.service"
            )
            ;;
        kvm|qemu)
            if [ -e /dev/virtio-ports/org.qemu.guest_agent.0 ]; then
                active_units+=("qemu-guest-agent.service")
            else
                masked_units+=("qemu-guest-agent.service")
            fi
            if [ -e /dev/virtio-ports/com.redhat.spice.0 ]; then
                active_units+=("spice-vdagentd.socket" "spice-vdagentd.service")
            else
                masked_units+=("spice-vdagentd.service" "spice-vdagentd.socket")
            fi
            masked_units+=(
                "virtualbox-guest-utils.service" "vboxadd-service.service"
                "open-vm-tools.service" "vgauth.service"
                "hv-kvp-daemon.service" "hv-vss-daemon.service" "hv-fcopy-daemon.service"
            )
            ;;
        microsoft)
            active_units+=("hv-kvp-daemon.service" "hv-vss-daemon.service" "hv-fcopy-daemon.service")
            masked_units+=(
                "virtualbox-guest-utils.service" "vboxadd-service.service"
                "open-vm-tools.service" "vgauth.service"
                "qemu-guest-agent.service" "spice-vdagentd.service" "spice-vdagentd.socket"
            )
            ;;
        *)
            masked_units+=(
                "virtualbox-guest-utils.service" "vboxadd-service.service"
                "open-vm-tools.service" "vgauth.service"
                "qemu-guest-agent.service" "spice-vdagentd.service" "spice-vdagentd.socket"
                "hv-kvp-daemon.service" "hv-vss-daemon.service" "hv-fcopy-daemon.service"
            )
            ;;
    esac

    local unit
    for unit in "${masked_units[@]}"; do
        mask_irrelevant_unit "$unit"
    done
    for unit in "${active_units[@]}"; do
        activate_guest_unit "$unit"
    done
    log_info "Reconciled hypervisor guest services for platform=$platform."
}

get_nm_device_state() {
    local dev="$1"
    nmcli -t -f GENERAL.STATE dev show "$dev" 2>/dev/null | head -n 1 | cut -d: -f2- || true
}

is_nm_state_connected_or_connecting() {
    case "$1" in
        *disconnected*|*unavailable*|*unmanaged*)
            return 1
            ;;
        100\ *|[4-9][0-9]\ *|*connected*|*connecting*)
            return 0
            ;;
    esac
    return 1
}

ensure_wired_autoconnect() {
    local dev="$1"
    local initial_state="${2:-}"
    local state
    state=$(get_nm_device_state "$dev")
    if [ -z "$state" ]; then
        state="$initial_state"
    fi

    if is_nm_state_connected_or_connecting "$state"; then
        return 0
    fi

    if [[ "$state" == *unavailable* ]] || [[ "$state" == 20\ * ]]; then
        if command -v ip >/dev/null 2>&1; then
            ip link set "$dev" up >/dev/null 2>&1 || true
            sleep 0.5
            state=$(get_nm_device_state "$dev")
        fi
        if [[ "$state" == *unavailable* ]] || [[ "$state" == 20\ * ]]; then
            log_info "Interface $dev has no carrier (cable unplugged); leaving ready for hotplug."
            return 0
        fi
    fi

    # Attempt existing/auto-created NetworkManager profile first
    nmcli -w 6 dev connect "$dev" >/dev/null 2>&1 || true
    state=$(get_nm_device_state "$dev")
    if is_nm_state_connected_or_connecting "$state"; then
        log_info "Auto-connected $dev via NetworkManager."
        return 0
    fi

    # Create or activate an explicit plug-and-play DHCP profile if needed
    local con_name="vice-auto-${dev}"
    if ! nmcli -t -f NAME connection show 2>/dev/null | grep -Fxq "$con_name"; then
        nmcli connection add \
            type ethernet \
            ifname "$dev" \
            con-name "$con_name" \
            autoconnect yes \
            connection.autoconnect-priority 10 \
            ipv4.method auto \
            ipv6.method auto >/dev/null 2>&1 || true
    fi

    if nmcli -w 8 connection up "$con_name" ifname "$dev" >/dev/null 2>&1; then
        log_info "Created and connected auto-DHCP profile '$con_name' on $dev."
    elif nmcli -w 6 dev connect "$dev" >/dev/null 2>&1; then
        log_info "Connected $dev via fallback nmcli dev connect."
    else
        log_warn "DHCP auto-connect deferred on $dev (no lease or offline)."
    fi
}

configure_network_plug_and_play() {
    if ! command -v nmcli >/dev/null 2>&1; then
        log_warn "nmcli not installed; skipping NetworkManager plug-and-play setup."
        return 0
    fi

    local nm_running=""
    nm_running=$(nmcli -t -f RUNNING general 2>/dev/null || true)
    if ! printf '%s' "$nm_running" | grep -qi "running"; then
        log_warn "NetworkManager is not running yet; skipping nmcli device setup."
        return 0
    fi

    nmcli networking on >/dev/null 2>&1 || true

    local dev_lines=""
    dev_lines=$(nmcli -t -f DEVICE,TYPE,STATE dev 2>/dev/null || true)
    if [ -z "$dev_lines" ]; then
        log_info "No NetworkManager devices discovered."
        return 0
    fi

    local dev dev_type dev_state
    while IFS=: read -r dev dev_type dev_state; do
        [ -n "$dev" ] || continue
        if is_ignored_iface "$dev" "$dev_type"; then
            continue
        fi

        case "$dev_type" in
            ethernet)
                nmcli dev set "$dev" managed yes >/dev/null 2>&1 || true
                ensure_wired_autoconnect "$dev" "$dev_state"
                ;;
            gsm|cdma|wwan)
                nmcli dev set "$dev" managed yes >/dev/null 2>&1 || true
                if [ "$dev_state" = "disconnected" ]; then
                    nmcli -w 6 dev connect "$dev" >/dev/null 2>&1 || true
                fi
                ;;
            wifi)
                nmcli dev set "$dev" managed yes >/dev/null 2>&1 || true
                if [ "$dev_state" = "disconnected" ]; then
                    nmcli dev wifi rescan ifname "$dev" >/dev/null 2>&1 || true
                fi
                ;;
        esac
    done <<< "$dev_lines"

    apply_nic_tuning
}

apply_nic_tuning() {
    if [ ! -x "$DISPATCHER_TUNE" ]; then
        return 0
    fi
    if [ ! -d "$SYS_NET_DIR" ]; then
        return 0
    fi

    local net_path dev state carrier
    for net_path in "$SYS_NET_DIR"/*; do
        [ -e "$net_path" ] || continue
        dev=$(basename "$net_path")
        if is_ignored_iface "$dev"; then
            continue
        fi
        state=""
        if [ -r "$net_path/operstate" ]; then
            state=$(tr -d '[:space:]' < "$net_path/operstate" 2>/dev/null || true)
        fi
        carrier="0"
        if [ -r "$net_path/carrier" ]; then
            carrier=$(tr -d '[:space:]' < "$net_path/carrier" 2>/dev/null || printf '0')
        fi
        if [ "$state" = "up" ] || { [ "$state" = "unknown" ] && [ "$carrier" = "1" ]; }; then
            "$DISPATCHER_TUNE" "$dev" up >/dev/null 2>&1 || true
            log_info "Applied 80-vice-net-tune on active NIC $dev."
        fi
    done
}

collect_nic_summary() {
    if command -v nmcli >/dev/null 2>&1; then
        local nm_out=""
        nm_out=$(nmcli -t -f DEVICE,TYPE,STATE,CONNECTION dev 2>/dev/null || true)
        if [ -n "$nm_out" ]; then
            local dev dtype dstate dcon drv speed
            while IFS=: read -r dev dtype dstate dcon; do
                [ -n "$dev" ] || continue
                if is_ignored_iface "$dev" "$dtype"; then
                    continue
                fi
                drv="unknown"
                if [ -L "${SYS_NET_DIR}/${dev}/device/driver" ]; then
                    drv=$(basename "$(readlink -f "${SYS_NET_DIR}/${dev}/device/driver" 2>/dev/null || printf 'unknown')")
                fi
                speed="-"
                if [ -r "${SYS_NET_DIR}/${dev}/speed" ]; then
                    speed=$(tr -d '[:space:]' < "${SYS_NET_DIR}/${dev}/speed" 2>/dev/null || printf '-')
                    if [ "$speed" != "-" ] && [ "$speed" != "-1" ]; then
                        speed="${speed}Mb/s"
                    else
                        speed="-"
                    fi
                fi
                printf '  - %s (type=%s, state=%s, driver=%s, speed=%s, conn=%s)\n' \
                    "$dev" "$dtype" "$dstate" "$drv" "$speed" "${dcon:-none}"
            done <<< "$nm_out"
            return 0
        fi
    fi

    if [ -d "$SYS_NET_DIR" ]; then
        local p dev op
        for p in "$SYS_NET_DIR"/*; do
            [ -e "$p" ] || continue
            dev=$(basename "$p")
            if is_ignored_iface "$dev"; then
                continue
            fi
            op="unknown"
            if [ -r "$p/operstate" ]; then
                op=$(tr -d '[:space:]' < "$p/operstate" 2>/dev/null || printf 'unknown')
            fi
            printf '  - %s (operstate=%s)\n' "$dev" "$op"
        done
    fi
}

collect_guest_service_summary() {
    local units=(
        "virtualbox-guest-utils.service"
        "vboxadd-service.service"
        "open-vm-tools.service"
        "vgauth.service"
        "qemu-guest-agent.service"
        "spice-vdagentd.service"
    )
    if ! command -v systemctl >/dev/null 2>&1 || [ ! -d /run/systemd/system ]; then
        printf '  - systemd runtime unavailable\n'
        return 0
    fi
    local unit active enabled
    for unit in "${units[@]}"; do
        if ! unit_is_installed "$unit"; then
            continue
        fi
        active=$(systemctl is-active "$unit" 2>/dev/null || true)
        enabled=$(systemctl is-enabled "$unit" 2>/dev/null || true)
        printf '  - %s: active=%s unit_state=%s\n' "$unit" "${active:-unknown}" "${enabled:-unknown}"
    done
}

write_diagnostics_log() {
    local platform="$1"
    local log_dir
    log_dir=$(dirname "$LOG_FILE")
    if ! mkdir -p "$log_dir" 2>/dev/null; then
        return 0
    fi

    local vendor product kernel_ver now_utc rfkill_out
    vendor=$(read_dmi_field "sys_vendor")
    product=$(read_dmi_field "product_name")
    kernel_ver=$(uname -r 2>/dev/null || printf 'unknown')
    now_utc=$(date -u '+%Y-%m-%d %H:%M:%S UTC' 2>/dev/null || printf 'unknown')
    rfkill_out="unavailable"
    if command -v rfkill >/dev/null 2>&1; then
        rfkill_out=$(rfkill list 2>/dev/null | tr '\n' ' ' | sed 's/[[:space:]]\+/ /g' || printf 'none')
    fi

    {
        printf '=== Vice OS Hardware & VM Auto-Detect Diagnostics ===\n'
        printf 'Timestamp: %s\n' "$now_utc"
        printf 'Platform: %s\n' "$(platform_label "$platform")"
        printf 'DMI Vendor: %s\n' "${vendor:-unknown}"
        printf 'DMI Product: %s\n' "${product:-unknown}"
        printf 'Kernel: %s\n' "$kernel_ver"
        printf 'Dispatcher: %s (%s)\n' "$DISPATCHER_TUNE" "$( [ -x "$DISPATCHER_TUNE" ] && printf 'executable' || printf 'missing' )"
        printf 'RFKill: %s\n' "${rfkill_out:-none}"
        printf 'Interfaces:\n'
        collect_nic_summary || true
        printf 'Guest Services:\n'
        collect_guest_service_summary || true
        printf 'Actions:\n'
        local entry
        for entry in "${ACTIONS_LOG[@]}"; do
            printf '  %s\n' "$entry"
        done
    } > "$LOG_FILE" 2>/dev/null || true
    chmod 644 "$LOG_FILE" 2>/dev/null || true
}

run_apply() {
    local platform
    platform=$(detect_virt_platform)
    log_info "Detected hardware platform: $(platform_label "$platform")"

    unblock_and_settle "$platform"
    manage_guest_services "$platform"
    configure_network_plug_and_play
    write_diagnostics_log "$platform"
}

run_status() {
    local platform vendor product kernel_ver nm_state failed_count
    platform=$(detect_virt_platform)
    vendor=$(read_dmi_field "sys_vendor")
    product=$(read_dmi_field "product_name")
    kernel_ver=$(uname -r 2>/dev/null || printf 'unknown')

    nm_state="not-installed"
    if command -v nmcli >/dev/null 2>&1; then
        if nmcli -t -f RUNNING general 2>/dev/null | grep -qi "running"; then
            nm_state="running"
        else
            nm_state="stopped"
        fi
    fi

    failed_count="n/a"
    if command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; then
        failed_count=$(systemctl --failed --no-legend 2>/dev/null | wc -l | tr -d '[:space:]' || printf '0')
    fi

    printf 'Platform: %s\n' "$(platform_label "$platform")"
    printf 'DMI: %s / %s\n' "${vendor:-unknown}" "${product:-unknown}"
    printf 'Kernel: %s\n' "$kernel_ver"
    printf 'NetworkManager: %s\n' "$nm_state"
    printf 'FailedUnits: %s\n' "$failed_count"
    printf 'DispatcherTune: %s\n' "$( [ -x "$DISPATCHER_TUNE" ] && printf 'installed (%s)' "$DISPATCHER_TUNE" || printf 'not-installed' )"
    printf 'LogFile: %s (%s)\n' "$LOG_FILE" "$( [ -f "$LOG_FILE" ] && printf 'present' || printf 'not-written' )"
    printf 'Interfaces:\n'
    collect_nic_summary || true
    printf 'GuestServices:\n'
    collect_guest_service_summary || true
}

main() {
    if [ "$#" -eq 0 ]; then
        show_help
        exit 0
    fi

    local action=""
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --apply)
                action="apply"
                ;;
            --status)
                action="status"
                ;;
            --help|-h|help)
                show_help
                exit 0
                ;;
            --version|-v|-V)
                show_version
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help >&2
                exit 1
                ;;
        esac
        shift
    done

    case "$action" in
        apply)
            check_root
            acquire_lock
            run_apply
            ;;
        status)
            run_status
            ;;
        *)
            log_error "No action specified (use --apply or --status)."
            exit 1
            ;;
    esac
}

main "$@"
