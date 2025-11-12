#!/usr/bin/env bash
# install_docker.sh — idempotent installer for Docker Engine + Compose plugin on Rocky
# Usage: sudo bash install_docker.sh --user secuser

set -euo pipefail

USER_TO_ADD="${1:-secuser}"

# Install required packages and the repo
dnf -y update
dnf -y install -y dnf-plugins-core curl

# Add Docker CE repo (centos/repo works for Rocky/RHEL8-family)
if ! grep -q "^\\[docker-ce-stable\\]" /etc/yum.repos.d/docker-ce.repo 2>/dev/null; then
  dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
fi

# Install Docker Engine and Compose plugin
dnf -y install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin || {
  echo "Install failed; retrying with --nobest"
  dnf -y install --nobest -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
}

# Enable and start docker
systemctl enable --now docker

# Create docker group if missing and add user
if ! getent group docker >/dev/null; then
  groupadd docker
fi

if id "${USER_TO_ADD}" >/dev/null 2>&1; then
  usermod -aG docker "${USER_TO_ADD}" || true
  echo "Added ${USER_TO_ADD} to docker group (log out/in for group to take effect)"
else
  echo "User ${USER_TO_ADD} not found — create user or run again with correct user"
fi

# Basic test: pull and run hello-world (non-blocking)
if command -v docker >/dev/null 2>&1; then
  docker --version || true
  docker compose version || true
  # try running hello-world quietly to verify runtime (won't fail the script)
  docker run --rm hello-world >/dev/null 2>&1 || echo "docker hello-world pull/run skipped or failed (ok to investigate manually)"
fi

echo "Docker + Compose installed. Verify with: docker --version && docker compose version"
