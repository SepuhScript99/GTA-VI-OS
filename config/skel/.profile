# ~/.profile: executed by the command interpreter for login shells.
# This file is sourced by /bin/bash for login shells, and also by /bin/sh
# if it is invoked as a login shell.

# GTA VI OS (Vice OS) Custom Profile

# if running bash, source .bashrc for aliases and prompt
if [ -n "$BASH_VERSION" ]; then
    if [ -f "$HOME/.bashrc" ]; then
        . "$HOME/.bashrc"
    fi
fi

# set PATH so it includes user's private bin if it exists
if [ -d "$HOME/bin" ] ; then
    PATH="$HOME/bin:$PATH"
fi

# set PATH so it includes user's private .local/bin if it exists
if [ -d "$HOME/.local/bin" ] ; then
    PATH="$HOME/.local/bin:$PATH"
fi

export PATH

# Vice OS Auto-Login & Session Initialization
# If on tty1 and no display server is running, launch the configured session.
# The session type is determined by /etc/vice-os/session.conf (or a user
# override at ~/.config/vice-os/session.conf).
#
#   SESSION=x11     → X11 with Openbox + picom + login.py greeter (default)
#   SESSION=wayland → Wayland with labwc compositor (native Wayland shell)
#
# We use 'exec' to replace the shell process with the session launcher.
# If the session launcher fails, the user is left at a shell prompt on tty1.
if [[ -z ${DISPLAY:-} ]] && [[ -z ${WAYLAND_DISPLAY:-} ]] && [[ $(tty) = /dev/tty1 ]]; then
    SESSION_TYPE="x11"
    SESSION_FILE="$HOME/.config/vice-os/session.conf"
    if [ ! -f "$SESSION_FILE" ]; then
        SESSION_FILE="/etc/vice-os/session.conf"
    fi
    if [ -f "$SESSION_FILE" ]; then
        # shellcheck disable=SC1090
        source "$SESSION_FILE"
    fi
    SESSION_TYPE="${SESSION_TYPE:-${SESSION:-x11}}"

    case "$SESSION_TYPE" in
        wayland)
            exec /opt/vice-os/wayland_session.sh
            ;;
        x11|*)
            exec xinit /opt/vice-os/login.py -- :0 vt1
            ;;
    esac
fi