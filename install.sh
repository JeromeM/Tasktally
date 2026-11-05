#!/bin/sh
set -eu

SOURCE="${TASKTALLY_SOURCE:-git+https://github.com/JeromeM/Tasktally}"
TASKRC="${TASKRC:-$HOME/.taskrc}"

info() { printf '\033[1;34m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33mwarning:\033[0m %s\n' "$1"; }
fail() { printf '\033[1;31merror:\033[0m %s\n' "$1" >&2; exit 1; }
has() { command -v "$1" >/dev/null 2>&1; }

as_root() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  elif has sudo; then
    sudo "$@"
  else
    fail "root privileges are required to run: $*"
  fi
}

install_taskwarrior() {
  case "$(uname -s)" in
    Darwin)
      has brew || fail "Homebrew is required on macOS: https://brew.sh"
      brew install task
      ;;
    Linux)
      if has apt-get; then
        as_root apt-get update
        as_root apt-get install -y taskwarrior
      elif has dnf; then
        as_root dnf install -y task
      elif has pacman; then
        as_root pacman -S --noconfirm task
      elif has zypper; then
        as_root zypper --non-interactive install taskwarrior
      elif has apk; then
        as_root apk add task
      else
        fail "no supported package manager found, install Taskwarrior manually: https://taskwarrior.org/download/"
      fi
      ;;
    *)
      fail "unsupported system: $(uname -s)"
      ;;
  esac
}

info "Checking Taskwarrior"
if has task; then
  echo "Taskwarrior $(task --version) already installed"
else
  install_taskwarrior
  has task || fail "Taskwarrior installation failed"
fi

case "$(task --version)" in
  1.*|2.[0-5].*) warn "Taskwarrior $(task --version) is old, Tasktally is tested with 2.6+ and 3.x" ;;
esac

info "Enabling time tracking in $TASKRC"
if [ ! -f "$TASKRC" ]; then
  printf 'data.location=%s\n' "$HOME/.task" > "$TASKRC"
fi
if grep -q '^journal.time=' "$TASKRC"; then
  sed -i.bak 's/^journal\.time=.*/journal.time=on/' "$TASKRC" && rm -f "$TASKRC.bak"
else
  printf 'journal.time=on\n' >> "$TASKRC"
fi

info "Checking uv"
if ! has uv; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  has uv || fail "uv installation failed"
fi

info "Installing Tasktally"
uv tool install --force "$SOURCE"

BIN_DIR="$(uv tool dir --bin)"
case ":$PATH:" in
  *":$BIN_DIR:"*)
    info "Done! Run 'tally' to start"
    ;;
  *)
    uv tool update-shell >/dev/null 2>&1 || true
    info "Done! Open a new terminal (or add $BIN_DIR to your PATH), then run 'tally'"
    ;;
esac
