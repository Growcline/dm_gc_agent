#!/usr/bin/env bash
# growcline_dm_agent installer (Ubuntu / Debian / WSL2). Safe to re-run.
#
#   bash install.sh                 # interactive
#   bash install.sh --yes --delivery-dir "C:\Users\me\Desktop\from_dm_agent"
#
# Options:
#   --delivery-dir PATH   where finished sets are copied (<PATH>/growcline/<topic>/<date>/); Windows C:\ paths OK on WSL
#   --global-agent        also make the agent available in every folder (~/.claude/agents)   [asked if interactive]
#   --no-global-agent     don't
#   --yes                 no prompts (defaults: keep current delivery folder, no global agent)
#   --skip-apt            don't install system packages
#
# Steps: 1 system tools · 2 Python venv for reels · 3 ~/growcline_dm_agent link · 4 config.env · 5 agent · 6 checks
set -euo pipefail

P="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
HOME_LINK="$HOME/growcline_dm_agent"
VENV="$HOME/.local/share/growcline_dm_agent/venv"
DELIVERY=""; YES=0; SKIP_APT=0; GLOBAL=""
while [ $# -gt 0 ]; do
  case "$1" in
    --delivery-dir) DELIVERY="${2:?}"; shift 2 ;;
    --global-agent) GLOBAL=1; shift ;;
    --no-global-agent) GLOBAL=0; shift ;;
    --yes|-y) YES=1; shift ;;
    --skip-apt) SKIP_APT=1; shift ;;
    -h|--help) sed -n 2,15p "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
step() { printf '\n\033[1m%s\033[0m\n' "$*"; }
ask()  { local a=""; if [ "$YES" = 0 ] && [ -t 0 ]; then read -r -p "  $1 [$2]: " a || true; fi; echo "${a:-$2}"; }

echo "Installing growcline_dm_agent from $P"

# ------------------------------------------------------------------ 1
step "1/6  System tools"
need=()
command -v python3 >/dev/null       || need+=(python3)
python3 -c 'import venv, ensurepip' 2>/dev/null || need+=(python3-venv)
command -v ffmpeg >/dev/null        || need+=(ffmpeg)          # reels + ffprobe
command -v wkhtmltoimage >/dev/null || need+=(wkhtmltopdf)     # provides wkhtmltoimage (renders PNGs)
fc-list 2>/dev/null | grep -qi "noto color emoji" || need+=(fonts-noto-color-emoji)
if [ ${#need[@]} -eq 0 ]; then
  ok "python3, venv, ffmpeg, wkhtmltoimage, emoji font"
elif [ "$SKIP_APT" = 1 ]; then
  warn "missing: ${need[*]} (skipped: --skip-apt)"
elif command -v apt-get >/dev/null; then
  SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"
  echo "  installing: ${need[*]} (may ask for your password)"
  if $SUDO apt-get update -qq && $SUDO apt-get install -y -qq "${need[@]}"; then ok "installed"
  else warn "install failed. Run yourself:  sudo apt-get install -y ${need[*]}"; fi
else
  warn "no apt-get; install yourself: ${need[*]}"
fi

# ------------------------------------------------------------------ 2
step "2/6  Python venv for reels (edge-tts, numpy, pillow)"
if python3 -c 'import venv, ensurepip' 2>/dev/null; then
  [ -x "$VENV/bin/python" ] || python3 -m venv "$VENV"
  if "$VENV/bin/pip" install -q --upgrade pip >/dev/null 2>&1 && "$VENV/bin/pip" install -q -r "$P/requirements.txt"; then
    [ -e "$P/.venv" ] && [ ! -L "$P/.venv" ] && rm -rf "$P/.venv"
    ln -sfn "$VENV" "$P/.venv"
    ok ".venv -> ${VENV/#$HOME/~}"
  else
    warn "pip install failed (only reels need it). Retry: $VENV/bin/pip install -r $P/requirements.txt"
  fi
else
  warn "python3-venv missing; skipped (only reels need it)"
fi

# ------------------------------------------------------------------ 3
step "3/6  ~/growcline_dm_agent (the agent's commands use this path)"
if [ "$P" = "$(readlink -f "$HOME_LINK" 2>/dev/null || true)" ]; then
  ok "project is at ~/growcline_dm_agent"
elif [ -L "$HOME_LINK" ]; then
  warn "~/growcline_dm_agent links to $(readlink -f "$HOME_LINK"). To use this copy:  ln -sfn \"$P\" ~/growcline_dm_agent"
elif [ -e "$HOME_LINK" ]; then
  warn "~/growcline_dm_agent already exists as a separate folder; move it away, then re-run to link this copy"
else
  ln -s "$P" "$HOME_LINK"; ok "created ~/growcline_dm_agent -> $P"
fi
mkdir -p "$P/output"

# ------------------------------------------------------------------ 4
step "4/6  Delivery folder (config.env)"
cur=""; [ -f "$P/config.env" ] && cur="$(grep -E '^DELIVERY_DIR=' "$P/config.env" | tail -1 | cut -d= -f2- || true)"
[ -n "$DELIVERY" ] || DELIVERY="$(ask "Copy finished sets to (empty = keep them in output/)" "$cur")"
if [[ "$DELIVERY" =~ ^[A-Za-z]:\\ ]]; then
  if command -v wslpath >/dev/null; then DELIVERY="$(wslpath -u "$DELIVERY")"; else warn "Windows path given but not on WSL"; fi
fi
if [ -n "$DELIVERY" ] && ! mkdir -p "$DELIVERY" 2>/dev/null; then warn "can't create $DELIVERY (check the path)"; fi
printf '# growcline_dm_agent local settings (written by install.sh)\n# finished sets are copied to $DELIVERY_DIR/growcline/<topic>/<date>/ (empty = keep them in output/)\nDELIVERY_DIR=%s\n' "$DELIVERY" > "$P/config.env"
ok "DELIVERY_DIR=${DELIVERY:-<empty: sets stay in output/>}"

# ------------------------------------------------------------------ 5
step "5/6  Agent"
ok "project agent: .claude/agents/growcline_dm_agent.md  (run inside the folder: claude --agent growcline_dm_agent)"
if [ -z "$GLOBAL" ]; then
  g="$(ask "Also make it available from any folder? (y/n)" "n")"; [[ "$g" =~ ^[Yy] ]] && GLOBAL=1 || GLOBAL=0
fi
GA="$HOME/.claude/agents/growcline_dm_agent.md"
if [ "$GLOBAL" = 1 ]; then
  mkdir -p "$HOME/.claude/agents"
  if [ -e "$GA" ] && [ ! -L "$GA" ]; then warn "$GA exists and isn't a link; left unchanged"
  else ln -sfn "$P/.claude/agents/growcline_dm_agent.md" "$GA"; ok "global agent: ~/.claude/agents/growcline_dm_agent.md (cost log only runs inside the project folder)"; fi
elif [ -L "$GA" ]; then
  rm -f "$GA"; ok "removed the global agent link"
fi

# ------------------------------------------------------------------ 6
step "6/6  Checks"
if command -v claude >/dev/null; then ok "Claude Code $(claude --version 2>/dev/null | head -1)"
else warn "Claude Code not found. Install:  curl -fsSL https://claude.ai/install.sh | bash   then run claude once and log in"; fi
if command -v wkhtmltoimage >/dev/null; then
  T="$P/output/.install-test/check"; rm -rf "$P/output/.install-test"; mkdir -p "$T"   # same depth as output/<topic>/<date>
  cp "$P/references/example-spec.json" "$T/spec.json"
  if python3 "$P/scripts/render.py" "$T/spec.json" "$T/images" >/dev/null 2>&1 \
     && python3 "$P/scripts/check_footer.py" "$T/images" >/dev/null 2>&1; then
    ok "test render + footer check passed"
  else
    warn "test render failed; check wkhtmltoimage (python3 scripts/render.py ... shows the error)"
  fi
  rm -rf "$P/output/.install-test"
fi
[ -x "$P/.venv/bin/edge-tts" ] && ok "reel tools ready (edge-tts, music)" || warn "reel tools not ready (step 2)"

cat <<EOF

Done. Start:
  cd ~/growcline_dm_agent && claude --agent growcline_dm_agent
  then ask e.g. "static post: DevOps myth vs reality" or "30 s reel for the Java course"
EOF
