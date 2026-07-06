#!/bin/bash
# ============================================================================
# GTA VI OS (Vice OS) State Manager Library
# Version: 1.0
# 
# Provides functions to manage build and installation state in a file.
# Uses flock for atomic, concurrency-safe operations.
# ============================================================================

# Prevent direct execution
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "This library is meant to be sourced, not executed directly."
    exit 1
fi

# --- Fallback Logging ---
# In case lib/common.sh is not sourced first, provide basic logging
if ! command -v log_info > /dev/null 2>&1; then
    log_info() { echo "[INFO] $1"; }
    log_error() { echo "[ERROR] $1" >&2; }
fi

# --- Configuration ---
# Default state file location. Can be overridden by the calling script.
STATE_FILE="${STATE_FILE:-$WORKDIR/state/build.state}"

# Ensure STATE_FILE is an absolute path
if [[ "$STATE_FILE" != /* ]]; then
    STATE_FILE="$PWD/$STATE_FILE"
fi

# --- Internal Functions ---

# Ensure the state directory exists
__ensure_state_dir() {
    local state_dir
    state_dir=$(dirname "$STATE_FILE")
    if [ ! -d "$state_dir" ]; then
        mkdir -p "$state_dir" || {
            log_error "Failed to create state directory: $state_dir"
            return 1
        }
    fi
}

# --- Public API ---

# Initializes the state file. Clears any existing state.
state_init() {
    __ensure_state_dir || return 1
    log_info "Initializing state file: $STATE_FILE"
    (
        flock -x 9 || exit 1
        echo "# GTA VI OS Build State" > "$STATE_FILE"
        echo "STARTED=$(date +%s)" >> "$STATE_FILE"
    ) 9>"$STATE_FILE"
}

# Sets a state variable to a value.
# Usage: state_set "KEY" "VALUE"
state_set() {
    local key="$1"
    local value="$2"
    
    if [ -z "$key" ]; then
        log_error "state_set: Key cannot be empty."
        return 1
    fi

    __ensure_state_dir || return 1
    
    # Use flock for atomic write to prevent race conditions
    (
        flock -x 9 || exit 1
        
        # If the file doesn't exist, create it
        if [ ! -f "$STATE_FILE" ]; then
            echo "# GTA VI OS Build State" > "$STATE_FILE"
        fi
        
        # Check if key exists, if so update it, otherwise append
        if grep -q "^${key}=" "$STATE_FILE"; then
            # Escape special characters in value for sed replacement
            local escaped_value=$(echo "$value" | sed 's/[\/&|]/\\&/g')
            sed -i "s|^${key}=.*|${key}=${escaped_value}|" "$STATE_FILE"
        else
            echo "${key}=${value}" >> "$STATE_FILE"
        fi
    ) 9>"$STATE_FILE"
}

# Gets a state variable value.
# Usage: value=$(state_get "KEY")
state_get() {
    local key="$1"
    
    if [ ! -f "$STATE_FILE" ]; then
        return 0 # Return empty if file doesn't exist
    fi
    
    # Read lock is not strictly required for grep, but ensures consistency 
    # if we were reading multiple values. For a single grep, it's safe.
    grep "^${key}=" "$STATE_FILE" 2>/dev/null | cut -d'=' -f2-
}

# Checks if a state variable is set to a specific value.
# Usage: if state_check "PHASE" "COMPLETE"; then ...
state_check() {
    local key="$1"
    local expected_value="$2"
    local current_value
    
    current_value=$(state_get "$key")
    
    if [ "$current_value" == "$expected_value" ]; then
        return 0
    else
        return 1
    fi
}

# Deletes a state variable from the file.
# Usage: state_delete "KEY"
state_delete() {
    local key="$1"
    
    if [ ! -f "$STATE_FILE" ]; then
        return 0
    fi

    (
        flock -x 9 || exit 1
        # Delete the line containing the key
        sed -i "/^${key}=/d" "$STATE_FILE"
    ) 9>"$STATE_FILE"
}

# Clears the state file completely.
state_clear() {
    if [ -f "$STATE_FILE" ]; then
        log_info "Clearing state file: $STATE_FILE"
        (
            flock -x 9 || exit 1
            rm -f "$STATE_FILE"
        ) 9>"$STATE_FILE"
    fi
}

# Marks a phase as complete.
# Usage: state_mark_complete "BOOTSTRAP"
state_mark_complete() {
    local phase="$1"
    state_set "${phase}_PHASE" "COMPLETE"
}

# Checks if a phase is complete.
# Usage: if state_is_complete "BOOTSTRAP"; then ...
state_is_complete() {
    local phase="$1"
    if state_check "${phase}_PHASE" "COMPLETE"; then
        return 0
    else
        return 1
    fi
}