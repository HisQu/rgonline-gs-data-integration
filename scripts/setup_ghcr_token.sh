#!/usr/bin/env bash
set -euo pipefail

# Sets up GHCR credentials for Singularity pulls by writing:
#   SINGULARITY_DOCKER_USERNAME
#   SINGULARITY_DOCKER_PASSWORD
# into an env file (default: ~/.config/rgonline-ghcr.env).
#
# Preferred path uses GitHub CLI OAuth web login to acquire a token
# with `read:packages`. Fallback path opens the PAT page in a browser and
# prompts for manual token paste.

ENV_FILE="${1:-$HOME/.config/rgonline-ghcr.env}"
mkdir -p "$(dirname "$ENV_FILE")"
touch "$ENV_FILE"
chmod 600 "$ENV_FILE"

username=""
token=""

if command -v gh >/dev/null 2>&1; then
  echo "Using GitHub CLI OAuth flow (browser sign-in if needed)..."
  if gh auth status -h github.com >/dev/null 2>&1; then
    gh auth refresh -h github.com -s read:packages >/dev/null
  else
    gh auth login -h github.com --web --git-protocol https --scopes read:packages
  fi
  username="$(gh api user --jq '.login' 2>/dev/null || true)"
  token="$(gh auth token -h github.com 2>/dev/null || true)"
fi

if [ -z "$token" ]; then
  echo "Falling back to manual token setup."
  token_url="https://github.com/settings/tokens/new?description=Singularity%20GHCR%20Pull%20(rgonline)&scopes=read:packages"
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$token_url" >/dev/null 2>&1 || true
  elif command -v open >/dev/null 2>&1; then
    open "$token_url" >/dev/null 2>&1 || true
  fi
  echo "Create a token with at least read:packages and paste it below."
  if [ -z "$username" ]; then
    read -r -p "GitHub username: " username
  fi
  read -r -s -p "GitHub token: " token
  echo
fi

if [ -z "$username" ]; then
  read -r -p "GitHub username: " username
fi

if [ -z "$token" ]; then
  echo "Error: token is empty." >&2
  exit 1
fi

esc() {
  printf "%s" "$1" | sed "s/'/'\"'\"'/g"
}

cat > "$ENV_FILE" <<EOF
export SINGULARITY_DOCKER_USERNAME='$(esc "$username")'
export SINGULARITY_DOCKER_PASSWORD='$(esc "$token")'
EOF

chmod 600 "$ENV_FILE"
echo "Wrote GHCR env vars to: $ENV_FILE"
echo "Run: source '$ENV_FILE'"
echo "Then: just singularity-pull-oci-private"
