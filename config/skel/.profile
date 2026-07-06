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

# Vice OS Auto-Login & X Session Initialization
# If on tty1 and no display server is running, start the custom PyQt5 login screen.
# We use 'exec' to replace the shell process with xinit.
# If xinit fails to start, the 'exec' command fails, and the script continues,
# leaving the user at a shell prompt on tty1 for troubleshooting.
if [[ -z $DISPLAY ]] && [[ $(tty) = /dev/tty1 ]]; then
    exec xinit /opt/vice-os/login.py -- :0 vt1
fi