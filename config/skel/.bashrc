# ~/.bashrc: executed by bash(1) for non-login shells.
# GTA VI OS (Vice OS) Custom Bash Configuration

# If not running interactively, don't do anything
case $- in
    *i*) ;;
      *) return;;
esac

# Don't put duplicate lines or lines starting with space in the history.
HISTCONTROL=ignoreboth
# Append to the history file, don't overwrite it
shopt -s histappend
# History size and file size
HISTSIZE=1000
HISTFILESIZE=2000
# Add timestamps to history entries
HISTTIMEFORMAT="%F %T "
# Check the window size after each command and update LINES and COLUMNS
shopt -s checkwinsize

# Neon Miami Aesthetic Prompt
# Magenta username, Cyan hostname, White path
PS1='\[\e[1;35m\]\u\[\e[0m\]@\[\e[1;36m\]\h\[\e[0m\]:\[\e[1;37m\]\w\[\e[0m\]\$ '

# Color support for ls and grep
if [ -x /usr/bin/dircolors ]; then
    test -r ~/.dircolors && eval "$(dircolors -b ~/.dircolors)" || eval "$(dircolors -b)"
    alias ls='ls --color=auto'
    alias grep='grep --color=auto'
fi

# Standard Aliases
alias ll='ls -alF'
alias la='ls -A'
alias l='ls -CF'
alias ..='cd ..'
alias ...='cd ../..'
alias update='sudo /usr/local/bin/vp-autoupdate.sh'
alias clean='sudo apt autoremove -y && sudo apt clean'

# Vice OS specific aliases
alias vp-menu='sudo /usr/local/bin/vice-os-menu.sh'
alias vp-update='sudo /usr/local/bin/vp-autoupdate.sh'

# Add /usr/local/bin to PATH if not already there
case ":$PATH:" in
    *":/usr/local/bin:"*) ;;
    *) PATH="/usr/local/bin:$PATH";;
esac

# Set default editor for CLI applications (e.g., git, visudo)
export EDITOR="geany"
export VISUAL="geany"

# Set default umask for secure file permissions
umask 022

export PATH