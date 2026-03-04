#!/bin/bash
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log_info() {
    echo "[INFO] $1"
}

log_error() {
    echo "[ERROR] $1" >&2
}

install_and_build() {
    local dir=$1
    local name=$2

    if [ ! -d "$dir" ]; then
        log_error "Directory not found: $dir"
        return 1
    fi

    log_info "Processing $name at $dir"

    cd "$dir"

    log_info "Installing dependencies for $name..."
    if ! npm install; then
        log_error "Failed to install dependencies for $name"
        return 1
    fi

    log_info "Building $name..."
    if ! npm run build; then
        log_error "Failed to build $name"
        return 1
    fi

    log_info "Successfully built $name"
    cd "$ROOT_DIR"
}

main() {
    log_info "Starting UI build process"

    install_and_build "$ROOT_DIR/client/webui/frontend" "solace-agent-mesh-ui"
    install_and_build "$ROOT_DIR/config_portal/frontend" "config-portal-frontend"

    log_info "All UI libraries built successfully"
}

main "$@"
