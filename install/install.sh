#!/bin/sh
# Copyright Solace Corporation
# SPDX-License-Identifier: BUSL-1.1

# Install Agent Mesh Desktop Application (Solace Agent Mesh) on macOS or Linux,
# from the latest GitHub release.
#
#   curl -fsSL https://raw.githubusercontent.com/SolaceProducts/solace-agent-mesh/main/install/install.sh | sh
#
# Options (flags, or the matching environment variables):
#   --format deb|rpm|tarball   Linux package format      (SAM_INSTALL_FORMAT; default: detected)
#   --webkit 4.0|4.1           Linux WebKitGTK ABI       (SAM_INSTALL_WEBKIT; default: detected)
#   --download-only            Download and verify, but do not install
#   --dry-run                  Print what would happen; download nothing
#
# SAM_INSTALL_REPO selects the GitHub repository (owner/name) to install from.
# GITHUB_TOKEN or GH_TOKEN, if set, is used to read a private repository.
#
# Every download is checked against the SHA-256 digest that GitHub publishes for
# the release asset. On macOS the app's Apple notarization is also verified.
set -eu

REPO="${SAM_INSTALL_REPO:-SolaceProducts/solace-agent-mesh}"
TOKEN="${GITHUB_TOKEN:-${GH_TOKEN:-}}"
RELEASE_API="https://api.github.com/repos/$REPO/releases/latest"
FORMAT="${SAM_INSTALL_FORMAT:-}"
WEBKIT="${SAM_INSTALL_WEBKIT:-}"
DOWNLOAD_ONLY=0
DRY_RUN=0
APP_NAME="Solace Agent Mesh"

say()  { printf '%s\n' "$*"; }
warn() { printf 'warning: %s\n' "$*" >&2; }
die()  { printf 'error: %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'USAGE'
Usage: install.sh [--format deb|rpm|tarball] [--webkit 4.0|4.1] [--download-only] [--dry-run]
Installs Agent Mesh Desktop Application (Solace Agent Mesh) on macOS or Linux.
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --format) FORMAT="${2:?--format needs a value}"; shift 2 ;;
    --webkit) WEBKIT="${2:?--webkit needs a value}"; shift 2 ;;
    --download-only) DOWNLOAD_ONLY=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done

command -v curl >/dev/null 2>&1 || die "curl is required"

as_root() {
  if [ "$(id -u)" -eq 0 ]; then "$@"
  elif command -v sudo >/dev/null 2>&1; then sudo "$@"
  else die "root privileges are needed to run: $*"
  fi
}

# curl with the GitHub token, if any, passed on stdin so that it stays out of
# the process list. curl drops the header when a redirect leaves api.github.com.
gh_curl() {
  if [ -n "$TOKEN" ]; then
    printf 'header = "Authorization: Bearer %s"\n' "$TOKEN" | curl -K - "$@"
  else
    curl "$@"
  fi
}

file_size() { wc -c < "$1" | tr -d ' '; }

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | awk '{print $1}'
  fi
}

RELEASE_JSON=""
load_release() {
  [ -n "$RELEASE_JSON" ] && return
  RELEASE_JSON="$(gh_curl -fsSL -H "Accept: application/vnd.github+json" "$RELEASE_API")" \
    || die "could not read the latest release of $REPO (for a private repository, set GITHUB_TOKEN)"
}

# Sets ASSET_NAME, ASSET_API_URL, ASSET_URL, ASSET_SHA256 and ASSET_SIZE for the
# asset of the latest release whose name ends with $1.
find_asset() {
  load_release
  row="$(printf '%s' "$RELEASE_JSON" | tr ',{}' '\n\n\n' | awk -v suffix="$1" '
    function val(s) { sub(/^[^:]*:[ \t]*"?/, "", s); sub(/"?[ \t]*$/, "", s); return s }
    /^[ \t]*"url":[ \t]*"[^"]*\/releases\/assets\/[0-9]+"/ { api = val($0); name = ""; digest = ""; size = ""; next }
    /^[ \t]*"name":/ { if (name == "") name = val($0); next }
    /^[ \t]*"size":/ { size = val($0); next }
    /^[ \t]*"digest":/ { digest = val($0); next }
    /^[ \t]*"browser_download_url":/ {
      n = length(suffix)
      if (length(name) > n && substr(name, length(name) - n + 1) == suffix) {
        sub(/^sha256:/, "", digest); if (digest == "null") digest = ""
        printf "%s|%s|%s|%s|%s\n", name, api, val($0), digest, size; exit
      }
    }')"
  [ -n "$row" ] || die "the latest release of $REPO has no asset ending in $1"
  IFS="|" read -r ASSET_NAME ASSET_API_URL ASSET_URL ASSET_SHA256 ASSET_SIZE <<EOF
$row
EOF
}

download_asset() {
  dest="$1"
  say "Downloading $ASSET_NAME ..."
  if [ -n "$TOKEN" ]; then
    gh_curl -fL --progress-bar -H "Accept: application/octet-stream" -o "$dest" "$ASSET_API_URL" \
      || die "download failed: $ASSET_NAME"
  else
    curl -fL --progress-bar -o "$dest" "$ASSET_URL" || die "download failed: $ASSET_URL"
  fi
  actual="$(sha256_of "$dest")"
  if [ -n "$ASSET_SHA256" ] && [ -n "$actual" ]; then
    [ "$actual" = "$ASSET_SHA256" ] || die "SHA-256 of $ASSET_NAME does not match the release; not installing"
    say "Verified SHA-256 $actual"
  else
    warn "could not verify the SHA-256 digest; checking the size only"
    [ "$(file_size "$dest")" = "$ASSET_SIZE" ] || die "downloaded size of $ASSET_NAME does not match the release"
  fi
}

detect_linux_arch() {
  case "$(uname -m)" in
    x86_64|amd64) echo amd64 ;;
    aarch64|arm64) echo arm64 ;;
    *) die "unsupported CPU architecture: $(uname -m) (supported: x86_64, aarch64)" ;;
  esac
}

detect_linux_format() {
  if command -v apt-get >/dev/null 2>&1 && command -v dpkg >/dev/null 2>&1; then echo deb
  elif command -v dnf >/dev/null 2>&1 || command -v yum >/dev/null 2>&1; then echo rpm
  else echo tarball
  fi
}

apt_has_candidate() {
  apt-cache policy "$1" 2>/dev/null | awk '/Candidate:/{print $2}' | grep -qv '(none)'
}

rpm_repo_has() {
  if command -v dnf >/dev/null 2>&1; then dnf -q list "$1" >/dev/null 2>&1
  else yum -q list "$1" >/dev/null 2>&1
  fi
}

shared_lib_present() {
  ldconfig -p 2>/dev/null | grep -q "$1"
}

# WebKitGTK 4.1 is preferred wherever the distribution offers it; 4.0 is the
# fallback for older releases (Ubuntu 22.04, Debian 12, RHEL/Rocky/Alma 9).
detect_webkit() {
  case "$1" in
    deb)
      if apt_has_candidate libwebkit2gtk-4.1-0; then echo 41
      elif apt_has_candidate libwebkit2gtk-4.0-37; then echo 40
      else warn "could not find WebKitGTK in apt; assuming 4.1 (override with --webkit)"; echo 41
      fi ;;
    rpm)
      if rpm_repo_has webkit2gtk4.1; then echo 41
      elif rpm_repo_has webkit2gtk3; then echo 40
      else warn "could not find WebKitGTK in dnf/yum; assuming 4.1 (override with --webkit)"; echo 41
      fi ;;
    tarball)
      if shared_lib_present libwebkit2gtk-4.1.so; then echo 41
      elif shared_lib_present libwebkit2gtk-4.0.so; then echo 40
      else warn "WebKitGTK is not installed; assuming 4.1 (install libwebkit2gtk-4.1 or override with --webkit)"; echo 41
      fi ;;
  esac
}

normalize_webkit() {
  case "$1" in
    4.0|40) echo 40 ;;
    4.1|41) echo 41 ;;
    *) die "--webkit must be 4.0 or 4.1" ;;
  esac
}

install_macos() {
  if [ "$(uname -m)" = arm64 ] || [ "$(sysctl -n hw.optional.arm64 2>/dev/null || echo 0)" = 1 ]; then
    find_asset -desktop-free-macos-apple-silicon.dmg
  else
    find_asset -desktop-free-macos-intel.dmg
  fi
  dest_dir=/Applications
  [ -w "$dest_dir" ] || dest_dir="$HOME/Applications"

  if [ "$DRY_RUN" -eq 1 ]; then
    say "Would download: $ASSET_URL"
    say "Would verify:   SHA-256 ${ASSET_SHA256:-(not published)}"
    say "Would install:  $dest_dir/$APP_NAME.app"
    return
  fi

  tmp="$(mktemp -d)"
  trap 'hdiutil detach "$tmp/mnt" -quiet >/dev/null 2>&1 || true; rm -rf "$tmp"' EXIT INT TERM
  dmg="$tmp/$ASSET_NAME"
  download_asset "$dmg"
  if [ "$DOWNLOAD_ONLY" -eq 1 ]; then
    mv "$dmg" .; say "Saved $(basename "$dmg")"; return
  fi

  mkdir -p "$tmp/mnt" "$dest_dir"
  hdiutil attach "$dmg" -nobrowse -quiet -mountpoint "$tmp/mnt"
  app="$tmp/mnt/$APP_NAME.app"
  [ -d "$app" ] || die "'$APP_NAME.app' not found in the disk image"
  spctl --assess --type execute "$app" 2>/dev/null \
    || die "the app failed the macOS Gatekeeper / notarization check; not installing"
  rm -rf "$dest_dir/$APP_NAME.app"
  ditto "$app" "$dest_dir/$APP_NAME.app"
  hdiutil detach "$tmp/mnt" -quiet

  cli="$dest_dir/$APP_NAME.app/Contents/MacOS/sam-desktop"
  say ""
  say "Installed $dest_dir/$APP_NAME.app"
  say "Open it from Launchpad or Spotlight. To use the sam CLI from a terminal, add:"
  say "  alias sam='\"$cli\"'"
}

install_linux() {
  arch="$(detect_linux_arch)"
  [ -n "$FORMAT" ] || FORMAT="$(detect_linux_format)"
  case "$FORMAT" in deb|rpm|tarball) ;; *) die "--format must be deb, rpm or tarball" ;; esac
  if [ -n "$WEBKIT" ]; then WEBKIT="$(normalize_webkit "$WEBKIT")"; else WEBKIT="$(detect_webkit "$FORMAT")"; fi

  case "$FORMAT" in tarball) ext=tar.gz ;; *) ext="$FORMAT" ;; esac
  find_asset "-desktop-free-linux-$arch-webkit2gtk-${WEBKIT%?}.${WEBKIT#?}.$ext"
  install_dir="${XDG_DATA_HOME:-$HOME/.local/share}/solace-agent-mesh"
  bin_dir="$HOME/.local/bin"

  if [ "$DRY_RUN" -eq 1 ]; then
    say "Detected:       $arch, $FORMAT, WebKitGTK ${WEBKIT%?}.${WEBKIT#?}"
    say "Would download: $ASSET_URL"
    say "Would verify:   SHA-256 ${ASSET_SHA256:-(not published)}"
    case "$FORMAT" in
      deb) say "Would install:  apt-get install ./<file> (needs sudo)" ;;
      rpm) say "Would install:  dnf install ./<file> (needs sudo)" ;;
      tarball) say "Would install:  $install_dir, linked from $bin_dir/solace-agent-mesh" ;;
    esac
    return
  fi

  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT INT TERM
  file="$tmp/$ASSET_NAME"
  download_asset "$file"
  if [ "$DOWNLOAD_ONLY" -eq 1 ]; then
    mv "$file" .; say "Saved $(basename "$file")"; return
  fi

  case "$FORMAT" in
    deb)
      as_root apt-get install -y "$file" ;;
    rpm)
      if command -v dnf >/dev/null 2>&1; then as_root dnf install -y "$file"
      else as_root yum install -y "$file"
      fi ;;
    tarball)
      rm -rf "$install_dir"
      mkdir -p "$install_dir" "$bin_dir"
      tar -xzf "$file" -C "$install_dir" --strip-components=1
      ln -sf "$install_dir/solace-agent-mesh" "$bin_dir/solace-agent-mesh"
      if [ -x "$install_dir/install.sh" ]; then "$install_dir/install.sh" >/dev/null || warn "could not add a desktop menu entry"; fi
      case ":$PATH:" in *":$bin_dir:"*) ;; *) warn "$bin_dir is not on your PATH" ;; esac ;;
  esac

  say ""
  say "Installed Agent Mesh Desktop Application. Launch it from your applications menu, or run: solace-agent-mesh"
  say "To use the sam CLI from a terminal, add:  alias sam='solace-agent-mesh'"
}

case "$(uname -s)" in
  Darwin) install_macos ;;
  Linux) install_linux ;;
  *) die "unsupported OS: $(uname -s). On Windows, use install.ps1." ;;
esac
