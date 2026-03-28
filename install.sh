#!/bin/sh
set -e

if [ -t 1 ]; then
  C_RESET="$(printf '\033[0m')"
  C_BOLD="$(printf '\033[1m')"
  C_DIM="$(printf '\033[2m')"
  C_BLUE="$(printf '\033[34m')"
  C_CYAN="$(printf '\033[36m')"
  C_GREEN="$(printf '\033[32m')"
  C_YELLOW="$(printf '\033[33m')"
  C_RED="$(printf '\033[31m')"
else
  C_RESET=""
  C_BOLD=""
  C_DIM=""
  C_BLUE=""
  C_CYAN=""
  C_GREEN=""
  C_YELLOW=""
  C_RED=""
fi

print_header() {
  printf "\n%s%sXenage Installer%s\n" "${C_BOLD}${C_BLUE}" "" "${C_RESET}"
  printf "%sCross-platform CLI setup with PATH auto-config%s\n\n" "${C_DIM}" "${C_RESET}"
}

step() {
  printf "%s==>%s %s\n" "${C_CYAN}${C_BOLD}" "${C_RESET}" "$1"
}

info() {
  printf "%s[i]%s %s\n" "${C_BLUE}" "${C_RESET}" "$1"
}

ok() {
  printf "%s[ok]%s %s\n" "${C_GREEN}" "${C_RESET}" "$1"
}

warn() {
  printf "%s[warn]%s %s\n" "${C_YELLOW}" "${C_RESET}" "$1"
}

fail() {
  printf "%s[err]%s %s\n" "${C_RED}" "${C_RESET}" "$1" >&2
  exit 1
}

show_cmd() {
  printf "%s$%s %s\n" "${C_DIM}" "${C_RESET}" "$*"
}

CHANNEL_RAW="${XENAGE_CHANNEL:-}"
CHANNEL=""
ALLOW_CHANNEL_CHOICE=0
SKIP_INIT=0

for arg in "$@"
do
  case "${arg}" in
    --choose|--chose)
      ALLOW_CHANNEL_CHOICE=1
      ;;
    --skip-init)
      SKIP_INIT=1
      ;;
    *)
      fail "Unknown argument: ${arg}. Usage: sh install.sh [--choose] [--skip-init]"
      ;;
  esac
done

print_header

step "Detecting platform"
OS="$(uname -s)"
ARCH="$(uname -m)"
TARGET=""

case "${OS}" in
  Linux)
    case "${ARCH}" in
      x86_64|amd64|x64) TARGET="linux-x86_64" ;;
      aarch64|arm64|arm64e) TARGET="linux-aarch64" ;;
    esac
    ;;
  Darwin)
    case "${ARCH}" in
      x86_64|amd64|x64) TARGET="darwin-x86_64" ;;
      aarch64|arm64|arm64e) TARGET="darwin-aarch64" ;;
    esac
    ;;
  MINGW64_NT*|MINGW32_NT*|MSYS_NT*|CYGWIN_NT*)
    case "${ARCH}" in
      x86_64|amd64|x64) TARGET="windows-x86_64" ;;
      aarch64|arm64|arm64e) TARGET="windows-aarch64" ;;
    esac
    ;;
esac

[ -n "${TARGET}" ] || fail "Unsupported OS/arch: ${OS} / ${ARCH}"
ok "Detected ${TARGET}"

step "Selecting release channel"
if [ -n "${CHANNEL_RAW}" ]; then
  case "${CHANNEL_RAW}" in
    latest|main|nightly) CHANNEL="latest" ;;
    development|dev) CHANNEL="development" ;;
    *) fail "Unsupported channel '${CHANNEL_RAW}'. Use latest/main/nightly or development/dev." ;;
  esac
fi

if [ -z "${CHANNEL}" ]; then
  if [ "${ALLOW_CHANNEL_CHOICE}" = "1" ] && [ -r /dev/tty ]; then
    echo "  1) Main (nightly latest_cli.json)"
    echo "  2) Development"
    printf "Select [1/2] (default 1): "
    read answer < /dev/tty || true
    case "${answer}" in
      ""|1|latest|Latest|main|nightly) CHANNEL="latest" ;;
      *) CHANNEL="development" ;;
    esac
  else
    CHANNEL="latest"
  fi
fi
ok "Channel: ${CHANNEL}"

BASE_URL="${XENAGE_INSTALL_BASE_URL:-https://xenage.dev}"
URL="${BASE_URL%/}/api/install/xenage-cli?target=${TARGET}&channel=${CHANNEL}"

INSTALL_DIR="${XENAGE_INSTALL_DIR:-$HOME/.local/bin}"
BIN_NAME="xenage"
case "${TARGET}" in
  windows-*) BIN_NAME="xenage.exe" ;;
esac
INSTALL_PATH="${INSTALL_DIR}/${BIN_NAME}"
TMP_PATH="${INSTALL_PATH}.download.tmp"

step "Installing binary"
show_cmd "mkdir -p \"${INSTALL_DIR}\""
mkdir -p "${INSTALL_DIR}"

info "Downloading from ${URL}"
show_cmd "curl -fL --progress-bar -o \"${TMP_PATH}\" \"${URL}\""
if ! curl -fL --progress-bar -o "${TMP_PATH}" "${URL}"; then
  rm -f "${TMP_PATH}" 2>/dev/null || true
  fail "Download failed"
fi

show_cmd "mv \"${TMP_PATH}\" \"${INSTALL_PATH}\""
mv "${TMP_PATH}" "${INSTALL_PATH}"
show_cmd "chmod a+x \"${INSTALL_PATH}\""
chmod a+x "${INSTALL_PATH}" || true
ok "Installed: ${INSTALL_PATH}"

path_contains_dir() {
  case ":$PATH:" in
    *":$1:"*) return 0 ;;
    *) return 1 ;;
  esac
}

append_path_block() {
  rc_file="$1"
  marker="# >>> xenage installer >>>"
  if [ -f "${rc_file}" ] && grep -F "${marker}" "${rc_file}" >/dev/null 2>&1; then
    return 0
  fi

  {
    echo ""
    echo "${marker}"
    echo "export PATH=\"${INSTALL_DIR}:\$PATH\""
    echo "# <<< xenage installer <<<"
  } >> "${rc_file}"
}

step "Configuring shell PATH"
if path_contains_dir "${INSTALL_DIR}"; then
  ok "PATH already contains ${INSTALL_DIR}"
else
  UPDATED=0
  for rc in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile" "$HOME/.zprofile"
  do
    if [ -f "${rc}" ]; then
      show_cmd "append PATH block to ${rc}"
      append_path_block "${rc}"
      UPDATED=1
    fi
  done

  if [ "${UPDATED}" = "0" ]; then
    show_cmd "create $HOME/.profile with PATH block"
    append_path_block "$HOME/.profile"
  fi

  export PATH="${INSTALL_DIR}:$PATH"
  ok "Added ${INSTALL_DIR} to PATH (new shells will pick it up)"
fi

step "Verifying installation"
show_cmd "\"${INSTALL_PATH}\" --help"
"${INSTALL_PATH}" --help >/dev/null 2>&1 || warn "Binary installed, but '--help' returned non-zero."

if [ "${SKIP_INIT}" = "1" ]; then
  warn "Skipping 'xenage init' (--skip-init was provided)"
else
  step "Running xenage init"
  show_cmd "\"${INSTALL_PATH}\" init"
  if "${INSTALL_PATH}" init; then
    ok "xenage init completed"
  else
    warn "'xenage init' failed or was interrupted. Run manually:"
    printf "  %s%s%s\n" "${C_BOLD}" "${INSTALL_PATH} init" "${C_RESET}"
  fi
fi

printf "\n%sInstallation complete.%s\n" "${C_GREEN}${C_BOLD}" "${C_RESET}"
printf "Binary: %s\n" "${INSTALL_PATH}"
printf "If your shell doesn't see xenage yet, restart terminal or run:\n"
printf "  %sexport PATH=\"%s:\$PATH\"%s\n\n" "${C_BOLD}" "${INSTALL_DIR}" "${C_RESET}"
