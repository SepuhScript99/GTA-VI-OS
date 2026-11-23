#!/bin/bash
set -Eeuo pipefail

# ============================================================================
# GTA VI OS (Vice OS) Interactive CLI Tool Launcher
# Installed as /usr/local/bin/vice-run-tool
# Usage: vice-run-tool <title> <cmd> [args...]
# ============================================================================

CORAL='\033[38;2;255;94;126m'
PEACH='\033[38;2;255;154;98m'
AQUA='\033[38;2;54;214;195m'
MUTED='\033[38;2;166;174;191m'
SLATE='\033[38;2;74;82;108m'
RED='\033[38;2;242;92;110m'
BOLD='\033[1m'
RESET='\033[0m'

case ":$PATH:" in
    *":/usr/sbin:"*) ;;
    *) PATH="$PATH:/usr/local/sbin:/usr/sbin:/sbin" ;;
esac
export PATH

print_usage() {
    cat <<EOF
GTA VI OS (Vice OS) Tool Launcher

Usage:
  vice-run-tool <title> <command> [args...]
  vice-run-tool <command>

Options:
  -h, --help    Show this help message and exit
EOF
}

cleanup_tty() {
    stty sane 2>/dev/null || true
}

print_header() {
    local title="$1"
    local cmd_display="$2"
    printf '%b%bVICE OS%b  ·  %b%s%b\n' "$BOLD" "$CORAL" "$RESET" "$BOLD" "$title" "$RESET"
    printf '%bcmd:%b %b%s%b   %bcwd:%b %s\n' "$MUTED" "$RESET" "$AQUA" "$cmd_display" "$RESET" "$MUTED" "$RESET" "$PWD"
    printf '%b────────────────────────────────────────────────────────────%b\n\n' "$SLATE" "$RESET"
}

hold_terminal() {
    if [ -t 0 ] && [ "${VICE_NO_HOLD:-0}" != "1" ]; then
        printf '\n'
        read -r -p "Press [Enter] to close this Vice OS window..." _ || true
    fi
}

find_terminal_bin() {
    local candidate
    for candidate in xfce4-terminal x-terminal-emulator xterm; do
        if command -v "$candidate" >/dev/null 2>&1; then
            printf '%s' "$candidate"
            return 0
        fi
    done
    return 1
}

needs_args_prompt() {
    local base
    base=$(basename "$1")
    case "$base" in
        rg|fdfind|fd|batcat|bat|jq|yq|curl|wget|aria2c|axel|http|nmap|tcpdump|tshark|mtr|whois|dig|host|traceroute|nc|netcat|ncat|ndiff|socat|iperf3|fping|ethtool|openssl|gpg|ufw|lynis|chkrootkit|rkhunter|age|pass|macchanger|proxychains4|strace|ltrace|valgrind|gdb-multiarch|nasm|objdump|eu-readelf|patchelf|hexedit|xxd|cloc|cppcheck|shellcheck|rsync|parted|ddrescue|smartctl|nvme|lsof|convert|magick|ffmpeg|ffprobe|mediainfo|sox|oggenc|flac|opusenc|qrencode|yt-dlp|7z|7za|tar|gzip|unzip|zip|zstd|grep|egrep|sed|awk|find|xargs|git|gcc|g++|make|cmake|ssh|scp|exiftool|pandoc|pdftotext|diff|colordiff|openvpn|wg|wg-quick|tor|privoxy|torsocks|obfs4proxy|stubby|unbound-checkconf|nft|iptables|firejail|nikto|sqlmap|gobuster|dirb|hydra|medusa|ncrack|john|crunch|cewl|aircrack-ng|aireplay-ng|airodump-ng|reaver|ettercap|arp-scan|netdiscover|hping3|masscan|binwalk|foremost|steghide|fls|mmls|icat|yara|tcpflow|ngrep|ssldump|sslscan|testssl.sh|testssl|whatweb|dnsrecon|dnsenum|fierce|mat2|nbtscan|smbclient|fcrackzip|pdfcrack|dmitry|wafw00f|swaks|stunnel4|stunnel|sshuttle|autossh|mosh|tcpreplay|clamscan|freshclam|aide|auditctl|fail2ban-client|cryptsetup|hdparm|btrfs|fsck.exfat|fsck.fat|ntfsfix|jdupes|optipng|jpegoptim|hunspell|tldr|lnav|multitail|redshift|qpdf|pdfimages|pdftohtml|tesseract|zbarimg|python3|sqlite3|hyperfine|entr|chafa|UEFIExtract|ZydisDisasm|adb|affcat|airgraph-ng|arping|atk6-alive6|b3sum|braa|bruteforce-luks|bruteforce-salted-openssl|bruteforce-wallet|bt-adapter|bully|ccrypt|certtool|checksec|chntpw|cisco7crack|cmospwd|cowpatty|dc3dd|dcfldd|debsums|dhcpdump|dnsmap|dnstop|dnstracer|drill|dsniff|dwarfdump|ewfinfo|exiv2|ext4magic|fastboot|fatcat|ffuf|firewalk|flawfinder|fwknop|gdbserver|gifshuffle|hashdeep|hcidump|hcxdumptool|hcxpcapngtool|heartbleeder|hexyl|httping|icmptx|ike-scan|ipcalc-ng|iw|ldapsearch|mdk3|mdk4|minisign|ndisc6|netsed|netsniff-ng|onesixtyone|ophcrack-cli|outguess|p0f|packit|pcapfix|pixiewps|pngcheck|princeprocessor|proxytunnel|reglookup|rhash|rifiuti2|rlwrap|samdump2|scalpel|scan6|scanelf|scrypt|sendip|siege|sipcrack|smb-nat|smbmap|snmpwalk|ssdeep|ssh-audit|sshpass|ssl-cert-check|sslsniff|sslsplit|stegsnow|sublist3r|sucrack|t50|tcptraceroute|tcptraceroute.mt|tcptrack|tinyproxy|tlsh|unhide|unsquashfs|vbindiff|w3m|wapiti|weevely|wfuzz|yasm|yersinia|zmap|zzuf)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

run_help_and_prompt() {
    local bin="$1"
    local rc=0
    local help_out=""
    local h_out=""

    set +e
    help_out=$("$bin" --help </dev/null 2>&1)
    rc=$?
    if [ "$rc" -eq 0 ] && [ -n "$help_out" ]; then
        printf '%s\n' "$help_out" | head -n 36
    else
        h_out=$("$bin" -h </dev/null 2>&1)
        if [ -n "$h_out" ] && ! printf '%s\n' "$h_out" | grep -qiE 'invalid option|unrecognized option|unknown option'; then
            printf '%s\n' "$h_out" | head -n 36
        elif [ -n "$help_out" ]; then
            printf '%s\n' "$help_out" | head -n 36
        fi
    fi
    set -e
    rc=0

    if [ ! -t 0 ] || [ "${VICE_NO_HOLD:-0}" = "1" ]; then
        return 0
    fi

    while true; do
        printf '\n%bArgs for "%s" ("sh" for shell, Enter to close): %b' "$PEACH" "$bin" "$RESET"
        local user_line=""
        if ! read -r user_line; then
            break
        fi
        if [ -z "$user_line" ]; then
            break
        fi
        if [ "$user_line" = "sh" ] || [ "$user_line" = "bash" ]; then
            bash -i || true
            continue
        fi
        local extra_args=()
        read -r -a extra_args <<< "$user_line"
        printf '\n'
        set +e
        "$bin" "${extra_args[@]}"
        rc=$?
        set -e
        printf '\n%b[exit %d]%b\n' "$MUTED" "$rc" "$RESET"
    done
    return "$rc"
}

main() {
    if [ "$#" -eq 0 ] || [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
        print_usage
        exit 0
    fi

    local title
    local cmd_args=()
    if [ "$#" -eq 1 ]; then
        title="$1"
        cmd_args=("$1")
    else
        title="$1"
        shift
        cmd_args=("$@")
    fi

    if [ "${#cmd_args[@]}" -eq 1 ] && [[ "${cmd_args[0]}" == *" "* ]] && ! command -v "${cmd_args[0]}" >/dev/null 2>&1; then
        local split_cmd=()
        read -r -a split_cmd <<< "${cmd_args[0]}"
        if [ "${#split_cmd[@]}" -gt 0 ]; then
            cmd_args=("${split_cmd[@]}")
        fi
    fi

    if [ -z "${VICE_IN_TERMINAL:-}" ] && { [ ! -t 0 ] || [ ! -t 1 ]; }; then
        if [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ]; then
            local term_bin=""
            if term_bin=$(find_terminal_bin); then
                local self_path
                self_path=$(readlink -f "${BASH_SOURCE[0]}" 2>/dev/null || printf '%s' "${BASH_SOURCE[0]}")
                local term_base
                term_base=$(basename "$term_bin")
                if [ "$term_base" = "xfce4-terminal" ]; then
                    exec "$term_bin" --disable-server -T "Vice OS - $title" -x env VICE_IN_TERMINAL=1 VICE_NO_HOLD="${VICE_NO_HOLD:-0}" "$self_path" "$title" "${cmd_args[@]}"
                else
                    exec "$term_bin" -T "Vice OS - $title" -e env VICE_IN_TERMINAL=1 VICE_NO_HOLD="${VICE_NO_HOLD:-0}" "$self_path" "$title" "${cmd_args[@]}"
                fi
            fi
        fi
    fi

    trap 'cleanup_tty' INT TERM EXIT

    local cmd_display
    cmd_display=$(printf '%s ' "${cmd_args[@]}")
    cmd_display="${cmd_display% }"

    print_header "$title" "$cmd_display"

    if ! command -v "${cmd_args[0]}" >/dev/null 2>&1; then
        printf '%b[ERROR] Command not found: %s%b\n' "$RED" "${cmd_args[0]}" "$RESET" >&2
        printf '%bInstall the corresponding Debian package or check PATH.%b\n' "$MUTED" "$RESET" >&2
        hold_terminal
        exit 127
    fi

    local rc=0
    if [ "${#cmd_args[@]}" -eq 1 ] && needs_args_prompt "${cmd_args[0]}"; then
        set +e
        run_help_and_prompt "${cmd_args[0]}"
        rc=$?
        set -e
        cleanup_tty
        exit "$rc"
    fi

    set +e
    "${cmd_args[@]}"
    rc=$?
    set -e

    cleanup_tty
    printf '\n%b────────────────────────────────────────────────────────────%b\n' "$SLATE" "$RESET"
    if [ "$rc" -eq 0 ]; then
        printf '%b[DONE]%b %s exited cleanly (status 0).\n' "$AQUA" "$RESET" "$title"
    else
        printf '%b[INFO]%b %s finished with exit status %d.\n' "$PEACH" "$RESET" "$title" "$rc"
    fi
    hold_terminal
    exit "$rc"
}

main "$@"
