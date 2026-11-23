#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) System Fetch Utility
# Installed to /usr/local/system_scripts/vicefetch.sh
# Symlinked at /usr/local/bin/vicefetch
# ============================================================================

VERSION="1.0.0"

case ":$PATH:" in
    *":/usr/sbin:"*) ;;
    *) PATH="$PATH:/usr/local/sbin:/usr/sbin:/sbin" ;;
esac
export PATH

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

USE_COLOR=1
COLOR_MODE="auto"
HOLD_ON_EXIT=0

# --- Color Palette Variables (populated by init_colors) ---
RST=""
BOLD=""
C_CORAL=""
C_PEACH=""
C_GOLD=""
C_AQUA=""
C_MINT=""
C_VIOLET=""
C_MAGENTA=""
C_WHITE=""
C_MUTED=""
C_SLATE=""

ART_GRAD=()
SWATCH_ROW1=()
SWATCH_ROW2=()

print_help() {
    cat <<'EOF'
GTA VI OS (Vice OS) System Fetch — GTA VI x Debian

Usage:
  vicefetch [OPTIONS]

Options:
  --plain, --no-color   Disable ANSI color output
  --256                 Force 256-color ANSI fallback palette
  --truecolor           Force 24-bit Truecolor ANSI palette
  --hold                Keep window open and wait for Enter before exiting
  -v, --version         Show version information and exit
  -h, --help            Show this help message and exit
EOF
}

print_version() {
    printf 'vicefetch v%s (GTA VI x Debian — Vice OS)\n' "$VERSION"
}

detect_color_mode() {
    if [ "$USE_COLOR" -eq 0 ] || [ -n "${NO_COLOR:-}" ]; then
        COLOR_MODE="plain"
        return 0
    fi
    if [ "$COLOR_MODE" != "auto" ]; then
        return 0
    fi
    local ct="${COLORTERM:-}"
    ct="${ct,,}"
    if [ "$ct" = "truecolor" ] || [ "$ct" = "24bit" ]; then
        COLOR_MODE="truecolor"
    else
        COLOR_MODE="256"
    fi
}

init_colors() {
    detect_color_mode

    if [ "$COLOR_MODE" = "plain" ]; then
        RST=""
        BOLD=""
        C_CORAL=""
        C_PEACH=""
        C_GOLD=""
        C_AQUA=""
        C_MINT=""
        C_VIOLET=""
        C_MAGENTA=""
        C_WHITE=""
        C_MUTED=""
        C_SLATE=""
        ART_GRAD=("" "" "" "" "" "" "" "" "" "")
        SWATCH_ROW1=("" "" "" "" "" "" "" "")
        SWATCH_ROW2=("" "" "" "" "" "" "" "")
        return 0
    fi

    RST=$'\033[0m'
    BOLD=$'\033[1m'

    if [ "$COLOR_MODE" = "truecolor" ]; then
        C_VIOLET=$'\033[1;38;2;155;93;229m'
        C_MAGENTA=$'\033[1;38;2;255;77;141m'
        C_CORAL=$'\033[1;38;2;255;110;127m'
        C_PEACH=$'\033[1;38;2;255;158;100m'
        C_GOLD=$'\033[1;38;2;255;209;102m'
        C_AQUA=$'\033[1;38;2;54;214;195m'
        C_MINT=$'\033[1;38;2;62;213;152m'
        C_WHITE=$'\033[1;38;2;245;246;250m'
        C_MUTED=$'\033[38;2;166;174;191m'
        C_SLATE=$'\033[38;2;110;119;140m'

        # 10-step Leonida Sunset vertical gradient:
        # #9B5DE5 -> #FF4D8D -> #FF6E7F -> #FF9E64 -> #FFD166
        ART_GRAD=(
            $'\033[1;38;2;155;93;229m'
            $'\033[1;38;2;181;88;207m'
            $'\033[1;38;2;212;82;178m'
            $'\033[1;38;2;255;77;141m'
            $'\033[1;38;2;255;91;134m'
            $'\033[1;38;2;255;110;127m'
            $'\033[1;38;2;255;134;113m'
            $'\033[1;38;2;255;158;100m'
            $'\033[1;38;2;255;183;101m'
            $'\033[1;38;2;255;209;102m'
        )
        SWATCH_ROW1=(
            $'\033[38;2;27;30;45m'
            $'\033[38;2;155;93;229m'
            $'\033[38;2;255;77;141m'
            $'\033[38;2;255;94;126m'
            $'\033[38;2;255;154;98m'
            $'\033[38;2;247;200;115m'
            $'\033[38;2;54;214;195m'
            $'\033[38;2;245;246;250m'
        )
        SWATCH_ROW2=(
            $'\033[38;2;53;59;84m'
            $'\033[38;2;185;131;255m'
            $'\033[38;2;255;133;179m'
            $'\033[38;2;255;143;163m'
            $'\033[38;2;255;183;139m'
            $'\033[38;2;255;224;158m'
            $'\033[38;2;62;213;152m'
            $'\033[38;2;166;174;191m'
        )
    else
        C_VIOLET=$'\033[1;38;5;135m'
        C_MAGENTA=$'\033[1;38;5;205m'
        C_CORAL=$'\033[1;38;5;204m'
        C_PEACH=$'\033[1;38;5;209m'
        C_GOLD=$'\033[1;38;5;221m'
        C_AQUA=$'\033[1;38;5;80m'
        C_MINT=$'\033[1;38;5;78m'
        C_WHITE=$'\033[1;38;5;255m'
        C_MUTED=$'\033[38;5;248m'
        C_SLATE=$'\033[38;5;244m'

        ART_GRAD=(
            $'\033[1;38;5;135m'
            $'\033[1;38;5;170m'
            $'\033[1;38;5;170m'
            $'\033[1;38;5;205m'
            $'\033[1;38;5;204m'
            $'\033[1;38;5;204m'
            $'\033[1;38;5;209m'
            $'\033[1;38;5;209m'
            $'\033[1;38;5;215m'
            $'\033[1;38;5;221m'
        )
        SWATCH_ROW1=(
            $'\033[38;5;235m'
            $'\033[38;5;135m'
            $'\033[38;5;205m'
            $'\033[38;5;204m'
            $'\033[38;5;209m'
            $'\033[38;5;221m'
            $'\033[38;5;80m'
            $'\033[38;5;255m'
        )
        SWATCH_ROW2=(
            $'\033[38;5;239m'
            $'\033[38;5;141m'
            $'\033[38;5;211m'
            $'\033[38;5;210m'
            $'\033[38;5;216m'
            $'\033[38;5;222m'
            $'\033[38;5;78m'
            $'\033[38;5;248m'
        )
    fi
}

# --- System Telemetry Probes (all safe under set -Eeuo pipefail) ---

get_user_host() {
    local user host
    user="${USER:-}"
    if [ -z "$user" ]; then
        user=$(id -un 2>/dev/null || printf 'vice')
    fi
    host=$(hostname -s 2>/dev/null || uname -n 2>/dev/null || printf 'vice-os')
    printf '%s@%s' "$user" "$host"
}

get_os_info() {
    local arch pretty deb_ver deb_label
    arch=$(uname -m 2>/dev/null || printf 'x86_64')
    pretty=""
    deb_ver=""
    if [ -r /etc/debian_version ]; then
        deb_ver=$(head -n 1 /etc/debian_version 2>/dev/null | tr -d '[:space:]' || true)
    fi
    if [ -r /etc/os-release ]; then
        pretty=$(grep -m1 '^PRETTY_NAME=' /etc/os-release 2>/dev/null | cut -d= -f2- | tr -d '"' || true)
    fi

    if [ -n "$deb_ver" ] && [[ "$deb_ver" == 12* || "$deb_ver" == *bookworm* ]]; then
        deb_label="Debian 12 Bookworm"
    elif [ -n "$deb_ver" ]; then
        deb_label="Debian $deb_ver"
    else
        deb_label="Debian 12 Bookworm"
    fi

    if [ -z "$pretty" ]; then
        local sys_name
        sys_name=$(uname -s 2>/dev/null || printf 'Linux')
        if [[ "$sys_name" == *MINGW* || "$sys_name" == *MSYS* || "$sys_name" == *CYGWIN* ]]; then
            printf 'Vice OS — GTA VI Edition (%s) %s' "$deb_label" "$arch"
        else
            printf 'Vice OS — GTA VI Edition (%s) %s' "$sys_name" "$arch"
        fi
    elif [[ "$pretty" == *"GTA VI OS"* || "$pretty" == *"Vice OS"* ]]; then
        printf 'Vice OS — GTA VI Edition (%s) %s' "$deb_label" "$arch"
    else
        printf '%s %s' "$pretty" "$arch"
    fi
}

get_host_info() {
    local vendor="" name="" ver="" out=""
    if [ -r /sys/devices/virtual/dmi/id/sys_vendor ]; then
        vendor=$(tr -d '\0\r\n' < /sys/devices/virtual/dmi/id/sys_vendor 2>/dev/null || true)
    fi
    if [ -r /sys/devices/virtual/dmi/id/product_name ]; then
        name=$(tr -d '\0\r\n' < /sys/devices/virtual/dmi/id/product_name 2>/dev/null || true)
    fi
    if [ -r /sys/devices/virtual/dmi/id/product_version ]; then
        ver=$(tr -d '\0\r\n' < /sys/devices/virtual/dmi/id/product_version 2>/dev/null || true)
    fi

    local dummy_re='^(To Be Filled By O\.E\.M\.|Default string|System Product Name|System Version|None|Not Specified|OEM)$'
    if [[ "$vendor" =~ $dummy_re ]]; then vendor=""; fi
    if [[ "$name" =~ $dummy_re ]]; then name=""; fi
    if [[ "$ver" =~ $dummy_re ]]; then ver=""; fi

    if [ -n "$name" ]; then
        if [ -n "$vendor" ] && [[ "${name,,}" != *"${vendor,,}"* ]]; then
            out="$vendor $name"
        else
            out="$name"
        fi
        if [ -n "$ver" ] && [[ "$ver" != "1.0" || "$name" == *VirtualBox* ]]; then
            out="$out $ver"
        fi
    elif [ -r /proc/device-tree/model ]; then
        out=$(tr -d '\0\r\n' < /proc/device-tree/model 2>/dev/null || true)
    fi

    if [ -z "$out" ]; then
        if command -v systemd-detect-virt >/dev/null 2>&1; then
            local virt
            virt=$(systemd-detect-virt 2>/dev/null || true)
            if [ -n "$virt" ] && [ "$virt" != "none" ]; then
                out="$virt VM"
            fi
        fi
    fi

    if [ -z "$out" ]; then
        out=$(hostname -s 2>/dev/null || uname -n 2>/dev/null || printf 'Vice Workstation')
    fi
    printf '%s' "$out"
}

get_kernel_info() {
    local rel
    rel=$(uname -r 2>/dev/null || printf '6.1.0-amd64')
    printf '%s' "$rel"
}

get_uptime_info() {
    if [ -r /proc/uptime ]; then
        local up_sec_raw up_sec days hours mins parts
        up_sec_raw=$(awk '{print int($1)}' /proc/uptime 2>/dev/null || printf '0')
        up_sec="${up_sec_raw:-0}"
        days=$((up_sec / 86400))
        hours=$(((up_sec % 86400) / 3600))
        mins=$(((up_sec % 3600) / 60))
        parts=()
        if [ "$days" -gt 0 ]; then
            parts+=("${days}d")
        fi
        if [ "$hours" -gt 0 ]; then
            if [ "$hours" -eq 1 ]; then
                parts+=("1 hour")
            else
                parts+=("${hours} hours")
            fi
        fi
        if [ "$mins" -gt 0 ] || [ "${#parts[@]}" -eq 0 ]; then
            if [ "$mins" -eq 1 ]; then
                parts+=("1 min")
            else
                parts+=("${mins} mins")
            fi
        fi
        local joined=""
        local item
        for item in "${parts[@]}"; do
            if [ -z "$joined" ]; then
                joined="$item"
            else
                joined="$joined, $item"
            fi
        done
        printf '%s' "$joined"
        return 0
    fi
    if command -v uptime >/dev/null 2>&1; then
        local up_p
        up_p=$(uptime -p 2>/dev/null | sed 's/^up //' || true)
        if [ -n "$up_p" ]; then
            printf '%s' "$up_p"
            return 0
        fi
    fi
    printf 'Active'
}

get_packages_info() {
    if command -v dpkg-query >/dev/null 2>&1; then
        local cnt
        cnt=$(dpkg-query -f '${binary:Package}\n' -W 2>/dev/null | wc -l | tr -d '[:space:]' || true)
        if [ -n "$cnt" ] && [ "$cnt" -gt 0 ] 2>/dev/null; then
            printf '%s (dpkg)' "$cnt"
            return 0
        fi
    fi
    printf 'Debian Bookworm (dpkg)'
}

get_vice_tools_info() {
    local reg=""
    local cand
    for cand in \
        "${VICE_TOOLS_REGISTRY:-}" \
        "/opt/vice-os/tools_registry.json" \
        "${SCRIPT_DIR}/../config/tools_registry.json" \
        "./config/tools_registry.json"; do
        if [ -n "$cand" ] && [ -r "$cand" ]; then
            reg="$cand"
            break
        fi
    done

    if [ -z "$reg" ]; then
        printf 'Registry not installed'
        return 0
    fi

    local stats="" py_bin=""
    if command -v python3 >/dev/null 2>&1; then
        py_bin=$(command -v python3 2>/dev/null || true)
        if [[ "$py_bin" == *WindowsApps* ]]; then
            py_bin=""
        fi
    fi
    if [ -z "$py_bin" ] && command -v python >/dev/null 2>&1; then
        py_bin=$(command -v python 2>/dev/null || true)
        if [[ "$py_bin" == *WindowsApps* ]]; then
            py_bin=""
        fi
    fi

    if [ -n "$py_bin" ]; then
        stats=$("$py_bin" - "$reg" 2>/dev/null <<'PY' || true
import json, sys
with open(sys.argv[1], "r", encoding="utf-8") as fp:
    data = json.load(fp)
tools = data.get("tools", [])
cnt = len(tools) if isinstance(tools, list) and tools else int(data.get("implemented_count") or data.get("current_count") or 0)
tgt = int(data.get("target_count") or 500)
pct = int((cnt * 100) // tgt) if tgt > 0 else 0
print(f"{cnt} / {tgt} ({pct}%)")
PY
)
    elif command -v jq >/dev/null 2>&1; then
        stats=$(jq -r '
            ((.tools | length) // .implemented_count // .current_count // 0) as $c |
            (.target_count // 500) as $t |
            "\($c) / \($t) (\(($c * 100 / $t) | floor)%)"
        ' "$reg" 2>/dev/null || true)
    fi

    if [ -z "$stats" ]; then
        local cnt tgt pct
        cnt=$(grep -c '"id"[[:space:]]*:' "$reg" 2>/dev/null || printf '0')
        tgt=$(grep -m1 '"target_count"' "$reg" 2>/dev/null | sed 's/[^0-9]//g' || printf '500')
        tgt="${tgt:-500}"
        if [ "$tgt" -gt 0 ] 2>/dev/null; then
            pct=$((cnt * 100 / tgt))
        else
            pct=0
        fi
        stats="${cnt} / ${tgt} (${pct}%)"
    fi
    printf '%s' "$stats"
}

get_shell_info() {
    local sh_path="${SHELL:-bash}"
    local sh_name="${sh_path##*/}"
    local ver=""
    case "$sh_name" in
        bash)
            if [ -n "${BASH_VERSION:-}" ]; then
                ver="${BASH_VERSION%%(*}"
            else
                ver=$(bash --version 2>/dev/null | head -n 1 | sed -n 's/.*version \([0-9.]*\).*/\1/p' || true)
            fi
            ;;
        zsh)
            ver=$(zsh --version 2>/dev/null | awk '{print $2}' || true)
            ;;
        fish)
            ver=$(fish --version 2>/dev/null | awk '{print $3}' || true)
            ;;
    esac
    if [ -n "$ver" ]; then
        printf '%s %s' "$sh_name" "$ver"
    else
        printf '%s' "$sh_name"
    fi
}

get_resolution_info() {
    if [ -n "${DISPLAY:-}" ] && command -v xrandr >/dev/null 2>&1; then
        local res
        res=$(xrandr --current 2>/dev/null | awk '/\*/{
            mode=$1; rate="";
            for(i=2;i<=NF;i++) if($i ~ /\*/){gsub(/[*+]/,"",$i); rate=$i; break}
            if(rate != "") printf "%s @ %sHz", mode, int(rate+0.5); else printf "%s", mode;
            exit
        }' || true)
        if [ -n "$res" ]; then
            printf '%s' "$res"
            return 0
        fi
    fi

    local drm_mode
    for drm_mode in /sys/class/drm/*/modes; do
        if [ -r "$drm_mode" ]; then
            local m
            m=$(head -n 1 "$drm_mode" 2>/dev/null | tr -d '[:space:]' || true)
            if [ -n "$m" ]; then
                printf '%s' "$m"
                return 0
            fi
        fi
    done

    if command -v tput >/dev/null 2>&1; then
        local cols lines
        cols=$(tput cols 2>/dev/null || printf '104')
        lines=$(tput lines 2>/dev/null || printf '30')
        printf 'TTY (%sx%s cells)' "$cols" "$lines"
        return 0
    fi
    printf 'Headless / TTY'
}

get_de_wm_info() {
    local de="" wm=""
    if pgrep -f "vice_shell.py" >/dev/null 2>&1; then
        de="Vice Shell"
    elif [ -n "${XDG_CURRENT_DESKTOP:-}" ]; then
        de="${XDG_CURRENT_DESKTOP}"
    elif [ -n "${DESKTOP_SESSION:-}" ]; then
        de="${DESKTOP_SESSION}"
    else
        de="Vice Shell"
    fi

    if pgrep -x openbox >/dev/null 2>&1; then
        wm="Openbox"
    elif pgrep -x labwc >/dev/null 2>&1; then
        wm="Labwc (Wayland)"
    elif command -v wmctrl >/dev/null 2>&1 && [ -n "${DISPLAY:-}" ]; then
        wm=$(wmctrl -m 2>/dev/null | awk -F': ' '/^Name:/{print $2; exit}' || true)
    fi

    if [ -n "$wm" ] && [[ "${de,,}" != *"${wm,,}"* ]]; then
        printf '%s / %s' "$de" "$wm"
    elif [ -n "$wm" ]; then
        printf '%s' "$wm"
    else
        printf '%s / Openbox' "$de"
    fi
}

get_theme_icons_info() {
    local gtk_theme="" icon_theme="" cfg
    for cfg in "$HOME/.config/gtk-3.0/settings.ini" "/etc/gtk-3.0/settings.ini"; do
        if [ -r "$cfg" ]; then
            if [ -z "$gtk_theme" ]; then
                gtk_theme=$(awk -F= '/^gtk-theme-name=/{print $2; exit}' "$cfg" 2>/dev/null | tr -d '\r' || true)
            fi
            if [ -z "$icon_theme" ]; then
                icon_theme=$(awk -F= '/^gtk-icon-theme-name=/{print $2; exit}' "$cfg" 2>/dev/null | tr -d '\r' || true)
            fi
        fi
    done
    gtk_theme="${gtk_theme:-Arc-Dark}"
    icon_theme="${icon_theme:-Papirus-Dark}"
    printf '%s / %s' "$gtk_theme" "$icon_theme"
}

get_terminal_info() {
    if [ -n "${TERM_PROGRAM:-}" ]; then
        printf '%s' "$TERM_PROGRAM"
        return 0
    fi
    if [ -r "/proc/${PPID:-0}/comm" ]; then
        local pid="$PPID"
        local depth=0
        while [ "$depth" -lt 6 ] && [ "$pid" -gt 1 ] 2>/dev/null; do
            local comm=""
            comm=$(tr -d '\0\r\n' < "/proc/${pid}/comm" 2>/dev/null || true)
            case "$comm" in
                bash|sh|zsh|fish|env|sudo|vicefetch|vice-run-tool*)
                    pid=$(awk '/^PPid:/{print $2}' "/proc/${pid}/status" 2>/dev/null || printf '0')
                    depth=$((depth + 1))
                    ;;
                "")
                    break
                    ;;
                *)
                    printf '%s' "$comm"
                    return 0
                    ;;
            esac
        done
    fi
    printf '%s' "${TERM:-xterm-256color}"
}

get_cpu_info() {
    local model="" cores=""
    if [ -r /proc/cpuinfo ]; then
        model=$(awk -F': ' '/^model name/{print $2; exit}' /proc/cpuinfo 2>/dev/null || true)
        cores=$(grep -c '^processor[[:space:]]*:' /proc/cpuinfo 2>/dev/null || true)
    fi
    if [ -z "$model" ] && command -v lscpu >/dev/null 2>&1; then
        model=$(lscpu 2>/dev/null | awk -F': *' '/^Model name:/{print $2; exit}' || true)
    fi
    if [ -z "$cores" ] && command -v nproc >/dev/null 2>&1; then
        cores=$(nproc 2>/dev/null || true)
    fi

    model=$(printf '%s' "${model:-x86_64 Processor}" | sed -E 's/\(R\)//g; s/\(TM\)//g; s/ CPU @.*//; s/[[:space:]]+/ /g; s/^ //; s/ $//')
    if [ -n "$cores" ] && [ "$cores" -gt 0 ] 2>/dev/null; then
        printf '%s (%s)' "$model" "$cores"
    else
        printf '%s' "$model"
    fi
}

get_gpu_info() {
    local gpu=""
    if command -v lspci >/dev/null 2>&1; then
        gpu=$(lspci 2>/dev/null | grep -iE 'vga|3d|display' | head -n 1 | sed -E 's/^[^ ]+ [^:]+: //; s/ \(rev [^)]+\)$//; s/Corporation //g; s/Technology Co\., Ltd\. //g' || true)
    fi
    if [ -z "$gpu" ] && command -v glxinfo >/dev/null 2>&1 && [ -n "${DISPLAY:-}" ]; then
        gpu=$(glxinfo -B 2>/dev/null | awk -F': ' '/Device:/{print $2; exit}' || true)
    fi
    if [ -z "$gpu" ]; then
        gpu="Standard Display Adapter"
    fi
    if [ "${#gpu}" -gt 46 ]; then
        gpu="${gpu:0:43}..."
    fi
    printf '%s' "$gpu"
}

get_memory_info() {
    if [ -r /proc/meminfo ]; then
        awk '
            /^MemTotal:/     { total = $2 }
            /^MemAvailable:/ { avail = $2 }
            /^MemFree:/      { free = $2 }
            /^Buffers:/      { buf = $2 }
            /^Cached:/       { cache = $2 }
            /^SReclaimable:/ { srec = $2 }
            END {
                if (total > 0) {
                    if (avail == 0) { avail = free + buf + cache + srec }
                    used = total - avail
                    if (used < 0) used = 0
                    used_m = int(used / 1024)
                    total_m = int(total / 1024)
                    pct = int((used * 100) / total)
                    printf "%d MiB / %d MiB (%d%%)", used_m, total_m, pct
                }
            }
        ' /proc/meminfo 2>/dev/null || true
        return 0
    fi
    if command -v free >/dev/null 2>&1; then
        free -m 2>/dev/null | awk '/^Mem:/{printf "%d MiB / %d MiB (%d%%)", $3, $2, int(($3*100)/$2)}' || true
        return 0
    fi
    printf 'N/A'
}

get_audio_info() {
    local srv="" pw_on=0 wp_on=0
    if pgrep -x pipewire >/dev/null 2>&1; then
        pw_on=1
    fi
    if pgrep -x wireplumber >/dev/null 2>&1; then
        wp_on=1
    fi

    if command -v pactl >/dev/null 2>&1; then
        srv=$(pactl info 2>/dev/null | awk -F': ' '/^Server Name:/{print $2; exit}' || true)
    fi

    if [ -n "$srv" ]; then
        if [[ "$srv" == *"PipeWire"* ]]; then
            local pw_ver
            pw_ver=$(printf '%s' "$srv" | sed -n 's/.*PipeWire \([0-9.]*\).*/\1/p')
            if [ "$wp_on" -eq 1 ]; then
                printf 'PipeWire %s + WirePlumber' "${pw_ver:-}" | sed 's/  */ /g'
            else
                printf 'PipeWire %s' "${pw_ver:-Active}" | sed 's/  */ /g'
            fi
            return 0
        fi
        printf '%s' "$srv"
        return 0
    fi

    if [ "$pw_on" -eq 1 ] && [ "$wp_on" -eq 1 ]; then
        printf 'PipeWire + WirePlumber (Active)'
    elif [ "$pw_on" -eq 1 ]; then
        printf 'PipeWire (Active)'
    elif [ -d /proc/asound/card0 ]; then
        printf 'ALSA Sound Card'
    else
        printf 'PipeWire / ALSA'
    fi
}

get_local_ip_info() {
    local ip_addr=""
    if command -v ip >/dev/null 2>&1; then
        ip_addr=$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src"){print $(i+1); exit}}' || true)
        if [ -z "$ip_addr" ]; then
            ip_addr=$(ip -br -4 addr show scope global 2>/dev/null | awk 'NR==1{split($3,a,"/"); print a[1]}' || true)
        fi
    fi
    if [ -z "$ip_addr" ] && command -v hostname >/dev/null 2>&1; then
        ip_addr=$(hostname -I 2>/dev/null | awk '{print $1}' || true)
    fi
    if [ -z "$ip_addr" ]; then
        ip_addr="127.0.0.1 (local)"
    fi
    printf '%s' "$ip_addr"
}

# --- Art & Spec Renderer ---

render_fetch() {
    init_colors

    local user_host os_val host_val kernel_val uptime_val pkg_val tools_val
    local shell_val res_val de_val theme_val term_val cpu_val gpu_val
    local mem_val audio_val ip_val

    user_host=$(get_user_host)
    os_val=$(get_os_info)
    host_val=$(get_host_info)
    kernel_val=$(get_kernel_info)
    uptime_val=$(get_uptime_info)
    pkg_val=$(get_packages_info)
    tools_val=$(get_vice_tools_info)
    shell_val=$(get_shell_info)
    res_val=$(get_resolution_info)
    de_val=$(get_de_wm_info)
    theme_val=$(get_theme_icons_info)
    term_val=$(get_terminal_info)
    cpu_val=$(get_cpu_info)
    gpu_val=$(get_gpu_info)
    mem_val=$(get_memory_info)
    audio_val=$(get_audio_info)
    ip_val=$(get_local_ip_info)

    # 20 artwork rows, each exactly 38 display columns wide
    local art_swirl=(
        "         _,met\$\$\$\$\$gg.                "
        "      ,g\$\$\$\$\$\$\$\$\$\$\$\$\$\$\$P.             "
        "    ,g\$\$P\"\"       \"\"\"Y\$\$.\".           "
        "   ,\$\$P'              \`\$\$\$.           "
        " ',\$\$P       ,ggs.     \`\$\$b:          "
        " \`d\$\$'     ,\$P\"'   .    \$\$\$           "
        "  \$\$P      d\$'     ,    \$\$P           "
        "  \$\$:      \$\$.   -    ,d\$\$'           "
        "  \$\$;      Y\$b._   _,d\$P'   "
        "  Y\$\$.    \`.\`\"Y\$\$\$\$P\"'      "
        "  \`\$\$b      \"-.__           "
        "   \`Y\$\$                     "
        "    \`Y\$\$.                   "
        "      \`\$\$b.                           "
        "        \`Y\$\$b.            "
        "           \`\"Y\$b._        "
        "               \`\"\"\"       "
        "                          "
        ""
        ""
    )

    local art_vi=(
        "" "" "" "" "" "" "" ""
        "██   ██ ██"
        "██   ██ ██"
        "▀█▄ ▄█▀ ██"
        " ▀███▀  ██"
        "  ▀█▀   ▀▀"
        "" "" "" "" "" "" ""
    )

    local art_aqua=(
        "" "" "" "" "" "" "" ""
        "" "" "" "" "" ""
        "  \\ | /     "
        "~-.\\|/.-~   "
        "  / ) \\     "
        "   (        "
        " ~~~~════════════════════════╧═══~~~~ "
        "   ──  L E O N I D A  ·  V I C E  ──  "
    )

    local grad_idx=(0 1 1 2 3 3 4 4 5 5 6 6 7 7 8 8 9 9 9 9)

    local user_part="${user_host%%@*}"
    local host_part="${user_host#*@}"
    local sep_line
    sep_line="${C_VIOLET}━━━━${C_MAGENTA}━━━━${C_CORAL}━━━━${C_PEACH}━━━━${C_GOLD}━━━━${C_AQUA}━━━━━${RST}"
    if [ "$COLOR_MODE" = "plain" ]; then
        sep_line="-------------------------"
    fi

    local sw_line1="" sw_line2=""
    local idx
    for idx in "${!SWATCH_ROW1[@]}"; do
        if [ "$idx" -gt 0 ]; then
            sw_line1+=" "
            sw_line2+=" "
        fi
        sw_line1+="${SWATCH_ROW1[$idx]}███${RST}"
        sw_line2+="${SWATCH_ROW2[$idx]}███${RST}"
    done

    local spec_lines=(
        "${C_CORAL}${user_part}${C_SLATE}@${C_AQUA}${host_part}${RST}  ${C_SLATE}·${RST}  ${C_GOLD}LEONIDA${RST}"
        "$sep_line"
        "$(printf '%s%-14s%s %s' "$C_AQUA" "OS" "$RST" "$os_val")"
        "$(printf '%s%-14s%s %s' "$C_AQUA" "Host" "$RST" "$host_val")"
        "$(printf '%s%-14s%s %s' "$C_AQUA" "Kernel" "$RST" "$kernel_val")"
        "$(printf '%s%-14s%s %s' "$C_AQUA" "Uptime" "$RST" "$uptime_val")"
        "$(printf '%s%-14s%s %s' "$C_AQUA" "Packages" "$RST" "$pkg_val")"
        "$(printf '%s%-14s%s %s%s%s' "$C_AQUA" "Vice Tools" "$RST" "$C_GOLD" "$tools_val" "$RST")"
        "$(printf '%s%-14s%s %s' "$C_AQUA" "Shell" "$RST" "$shell_val")"
        "$(printf '%s%-14s%s %s' "$C_AQUA" "Resolution" "$RST" "$res_val")"
        "$(printf '%s%-14s%s %s' "$C_AQUA" "DE / WM" "$RST" "$de_val")"
        "$(printf '%s%-14s%s %s' "$C_AQUA" "Theme / Icons" "$RST" "$theme_val")"
        "$(printf '%s%-14s%s %s' "$C_AQUA" "Terminal" "$RST" "$term_val")"
        "$(printf '%s%-14s%s %s' "$C_AQUA" "CPU" "$RST" "$cpu_val")"
        "$(printf '%s%-14s%s %s' "$C_AQUA" "GPU" "$RST" "$gpu_val")"
        "$(printf '%s%-14s%s %s' "$C_AQUA" "Memory" "$RST" "$mem_val")"
        "$(printf '%s%-14s%s %s' "$C_AQUA" "Audio" "$RST" "$audio_val")"
        "$(printf '%s%-14s%s %s' "$C_AQUA" "Local IP" "$RST" "$ip_val")"
        ""
        "$sw_line1"
        "$sw_line2"
    )

    local total_rows="${#spec_lines[@]}"
    if [ "${#art_swirl[@]}" -gt "$total_rows" ]; then
        total_rows="${#art_swirl[@]}"
    fi

    printf '\n'
    local row=0
    while [ "$row" -lt "$total_rows" ]; do
        local sw="" vi="" aq="" left_rendered=""
        if [ "$row" -lt "${#art_swirl[@]}" ]; then
            sw="${art_swirl[$row]}"
            vi="${art_vi[$row]}"
            aq="${art_aqua[$row]}"

            if [ -n "$sw" ]; then
                local g_color="${ART_GRAD[${grad_idx[$row]}]}"
                left_rendered+="${g_color}${sw}${RST}"
            fi
            if [ -n "$vi" ]; then
                local vi_color="$C_WHITE"
                if [ "$row" -eq 10 ] || [ "$row" -eq 11 ]; then
                    vi_color="$C_GOLD"
                elif [ "$row" -ge 12 ]; then
                    vi_color="$C_PEACH"
                fi
                left_rendered+="${vi_color}${vi}${RST}"
            fi
            if [ -n "$aq" ]; then
                left_rendered+="${C_AQUA}${aq}${RST}"
            fi
        else
            printf -v left_rendered '%*s' 38 ""
        fi

        local spec=""
        if [ "$row" -lt "${#spec_lines[@]}" ]; then
            spec="${spec_lines[$row]}"
        fi

        if [ -n "$spec" ]; then
            printf '  %s   %s\n' "$left_rendered" "$spec"
        else
            printf '  %s\n' "$left_rendered"
        fi
        row=$((row + 1))
    done
    printf '\n'
}

hold_prompt() {
    if [ "$HOLD_ON_EXIT" -ne 1 ]; then
        return 0
    fi
    printf '  %sPress Enter to close...%s ' "$C_MUTED" "$RST"
    if [ -t 0 ]; then
        read -r _ || true
    elif [ -r /dev/tty ]; then
        read -r _ </dev/tty || true
    fi
}

main() {
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --plain|--no-color)
                USE_COLOR=0
                ;;
            --256)
                COLOR_MODE="256"
                ;;
            --truecolor)
                COLOR_MODE="truecolor"
                ;;
            --hold)
                HOLD_ON_EXIT=1
                ;;
            -v|--version)
                print_version
                exit 0
                ;;
            -h|--help)
                print_help
                exit 0
                ;;
            *)
                printf 'vicefetch: unknown option: %s\n' "$1" >&2
                printf "Try 'vicefetch --help' for more information.\n" >&2
                exit 2
                ;;
        esac
        shift
    done

    render_fetch
    hold_prompt
}

main "$@"
