#!/usr/bin/env bash
# provision_secure_vm2_key.sh
# Usage:
# sudo bash provision_secure_vm2_key.sh --port 50022 --user secuser --pubkey-file /vagrant/keys/id_rsa.pub --allow-ip 192.168.56.1
# or
# sudo bash provision_secure_vm2_key.sh --port 50022 --user secuser --pubkey "ssh-ed25519 AAAA..." --allow-ip 192.168.56.1

set -euo pipefail

DEFAULT_PORT=50022
DEFAULT_USER="secuser"
DEFAULT_ALLOW_IP="127.0.0.1"

# parse args
PUBKEY_FILE=""
PUBKEY_STR=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --port) NEW_SSH_PORT="$2"; shift 2;;
    --user) NEW_USER="$2"; shift 2;;
    --pubkey-file) PUBKEY_FILE="$2"; shift 2;;
    --pubkey) PUBKEY_STR="$2"; shift 2;;
    --allow-ip) ALLOW_IP="$2"; shift 2;;
    --help) echo "Usage: $0 --port <port> --user <name> --pubkey-file <path> | --pubkey '<key>' --allow-ip <ip>"; exit 0;;
    *) echo "Unknown arg $1"; exit 1;;
  esac
done

NEW_SSH_PORT="${NEW_SSH_PORT:-$DEFAULT_PORT}"
NEW_USER="${NEW_USER:-$DEFAULT_USER}"
ALLOW_IP="${ALLOW_IP:-$DEFAULT_ALLOW_IP}"

if [[ -z "$PUBKEY_FILE" && -z "$PUBKEY_STR" ]]; then
  echo "ERROR: provide either --pubkey-file or --pubkey"
  exit 2
fi

echo "Configuring SSH -> port ${NEW_SSH_PORT}, user ${NEW_USER}, allow-ip ${ALLOW_IP}"
echo "Using public key from: ${PUBKEY_FILE:-<provided inline>}"

backup() {
  local f="$1"
  if [[ -f "$f" ]]; then
    cp -n "$f" "$f.bak.$(date +%s)" || true
  fi
}

# 1) system update + packages
dnf -y update
dnf -y install firewalld fail2ban policycoreutils-python-utils sudo which

systemctl enable --now firewalld
systemctl enable --now fail2ban

# 2) create non-root user (no password set)
if ! id -u "$NEW_USER" >/dev/null 2>&1; then
  useradd -m -s /bin/bash "$NEW_USER"
  usermod -aG wheel "$NEW_USER"
  # create .ssh dir and restrict perms (we'll place key below)
  mkdir -p /home/"$NEW_USER"/.ssh
  chown "$NEW_USER":"$NEW_USER" /home/"$NEW_USER"/.ssh
  chmod 700 /home/"$NEW_USER"/.ssh
  echo "Created user ${NEW_USER}"
else
  echo "User ${NEW_USER} already exists — ensuring .ssh exists and perms set"
  mkdir -p /home/"$NEW_USER"/.ssh
  chown "$NEW_USER":"$NEW_USER" /home/"$NEW_USER"/.ssh
  chmod 700 /home/"$NEW_USER"/.ssh
fi

# 3) add public key (idempotent)
AUTHORIZED_KEYS="/home/${NEW_USER}/.ssh/authorized_keys"
touch "$AUTHORIZED_KEYS"
chmod 600 "$AUTHORIZED_KEYS"
chown "$NEW_USER":"$NEW_USER" "$AUTHORIZED_KEYS"

if [[ -n "$PUBKEY_FILE" ]]; then
  if [[ ! -f "$PUBKEY_FILE" ]]; then
    echo "ERROR: pubkey-file $PUBKEY_FILE does not exist"
    exit 3
  fi
  PUBKEY_CONTENT=$(sed -e 's/[[:space:]]*$//' "$PUBKEY_FILE")
else
  PUBKEY_CONTENT="$PUBKEY_STR"
fi

# avoid duplicate
if grep -Fxq "$PUBKEY_CONTENT" "$AUTHORIZED_KEYS"; then
  echo "Public key already present in authorized_keys"
else
  echo "$PUBKEY_CONTENT" >> "$AUTHORIZED_KEYS"
  chown "$NEW_USER":"$NEW_USER" "$AUTHORIZED_KEYS"
  chmod 600 "$AUTHORIZED_KEYS"
  echo "Added public key to $AUTHORIZED_KEYS"
fi

# 4) configure sshd_config
SSHD_CONF="/etc/ssh/sshd_config"
backup "$SSHD_CONF"

# remove existing Port lines
sed -r -i '/^\s*Port\s+[0-9]+/d' "$SSHD_CONF"
# ensure PasswordAuthentication and PermitRootLogin set correctly
sed -r -i 's/^\s*#?\s*PasswordAuthentication\s+.*/PasswordAuthentication no/' "$SSHD_CONF" || echo "PasswordAuthentication no" >> "$SSHD_CONF"
sed -r -i 's/^\s*#?\s*PermitRootLogin\s+.*/PermitRootLogin no/' "$SSHD_CONF" || echo "PermitRootLogin no" >> "$SSHD_CONF"

# add our new Port if not present
if ! grep -qE "^\s*Port\s+${NEW_SSH_PORT}" "$SSHD_CONF"; then
  echo "Port ${NEW_SSH_PORT}" >> "$SSHD_CONF"
fi

grep -q "Configured by provision_secure_vm2_key.sh" "$SSHD_CONF" || echo "# Configured by provision_secure_vm2_key.sh" >> "$SSHD_CONF"

# 5) SELinux: map the new SSH port
if command -v semanage >/dev/null 2>&1; then
  if semanage port -l | grep -wq "${NEW_SSH_PORT}/tcp"; then
    echo "SELinux: port ${NEW_SSH_PORT}/tcp already configured"
  else
    semanage port -a -t ssh_port_t -p tcp "${NEW_SSH_PORT}" || semanage port -m -t ssh_port_t -p tcp "${NEW_SSH_PORT}"
    echo "SELinux: added ssh port ${NEW_SSH_PORT}"
  fi
else
  echo "semanage not present; attempting to install policycoreutils-python-utils and retry"
  dnf -y install policycoreutils-python-utils || true
  if command -v semanage >/dev/null 2>&1; then
    semanage port -a -t ssh_port_t -p tcp "${NEW_SSH_PORT}" || true
  else
    echo "Warning: semanage still missing; SELinux port mapping skipped"
  fi
fi

# 6) firewall: allow only ALLOW_IP -> NEW_SSH_PORT
ZONE=$(firewall-cmd --get-default-zone || echo public)
echo "Using firewalld zone: $ZONE"

# remove built-in ssh service to avoid exposing 22
if firewall-cmd --zone="$ZONE" --list-services | grep -qw ssh; then
  firewall-cmd --zone="$ZONE" --remove-service=ssh --permanent || true
fi

RICH_RULE="rule family='ipv4' source address='${ALLOW_IP}' port port='${NEW_SSH_PORT}' protocol='tcp' accept"
# remove & add cleanly
firewall-cmd --permanent --zone="$ZONE" --remove-rich-rule="$RICH_RULE" >/dev/null 2>&1 || true
firewall-cmd --permanent --zone="$ZONE" --add-rich-rule="$RICH_RULE"
firewall-cmd --reload

# 7) Fail2Ban config for ssh (ignore allowed ip)
FAIL2BAN_JAIL="/etc/fail2ban/jail.d/sshd.local"
cat > "$FAIL2BAN_JAIL" <<EOF
[sshd]
enabled = true
port    = ${NEW_SSH_PORT}
filter  = sshd
logpath = /var/log/secure
maxretry = 3
bantime = 3600
ignoreip = 127.0.0.1/8 ::1 ${ALLOW_IP}
EOF
systemctl restart fail2ban || true

# 8) test sshd config then restart
if sshd -t; then
  systemctl restart sshd
  echo "sshd restarted successfully"
else
  echo "sshd config test failed; aborting. Check $SSHD_CONF"
  exit 1
fi

# 9) final checks
echo "=== Final checks ==="
echo "sshd listening (expect port ${NEW_SSH_PORT}):"
ss -tlnp | grep ":${NEW_SSH_PORT}" || ss -tlnp | grep sshd || true
echo "firewalld rules (zone: $ZONE):"
firewall-cmd --zone="$ZONE" --list-rich-rules
echo "Fail2Ban status (sshd):"
fail2ban-client status sshd || true

echo
echo "Done. Connect from the allowed IP with your private key:"
echo "ssh -i /path/to/private_key -p ${NEW_SSH_PORT} ${NEW_USER}@<VM2_IP>"