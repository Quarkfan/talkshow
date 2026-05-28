#!/bin/sh
set -e

SSH_CMD="ssh -i /root/.ssh/id_ed25519_github -o StrictHostKeyChecking=yes -o UserKnownHostsFile=/root/.ssh/known_hosts"
export GIT_SSH_COMMAND="$SSH_CMD"

if [ -d "/content/.git" ]; then
  echo "[entrypoint] /content already has a git repo, resetting and pulling latest..."
  git -C /content fetch origin main
  git -C /content reset --hard origin/main
else
  echo "[entrypoint] Cloning talkResources into /content..."
  git clone --branch main git@github.com:Quarkfan/talkResources.git /content
fi

# Run the main command
exec "$@"
