# Demo — Secure VM and web app, and attack them

> Objective — Run a reproducible, isolated lab: bring up two VMs with Vagrant, harden the target VM and a simple web app, run attacker scenarios from the other VM, observe defender controls and metrics.

---

## Intro

**What this demo covers**

* Provision a small lab (2 VMs) with Vagrant.
* Harden the target VM and a simple web app.
* Run attacker scenarios (recon, brute, load/slow attacks) from an attacker VM.
* Tune defenses (Fail2Ban, firewall, Nginx limits) and measure impact.

**Why / relation to other tutorials**

* This demo ties together the three tutorial topics: lab provisioning, VM hardening and web-app hardening + testing. See the full guides used during the demo:
* Vagrant / lab setup: [https://github.com/Sight-ech/how_to/blob/main/set_up_vagrant_ubuntu.md](https://github.com/Sight-ech/how_to/blob/main/set_up_vagrant_ubuntu.md)
* VPS hardening (Rocky): [https://github.com/Sight-ech/how_to/blob/main/secure_vps_rocky.md](https://github.com/Sight-ech/how_to/blob/main/secure_vps_rocky.md)
* Web app hardening & security layers: [https://github.com/Sight-ech/how_to/blob/main/secure_web_app.md](https://github.com/Sight-ech/how_to/blob/main/secure_web_app.md)

**Security layers (quick pointer)**

* We follow the layered model in the secure_web_app guide: (edge / network) → (host / OS) → (reverse proxy / web server) → (app / auth / rate limits) → (monitoring & response).
  For more detail and the diagram, open the web-app security doc above.

**Quick difference: libvirt/KVM vs VirtualBox**

* **libvirt / KVM**

  * Hypervisor based on QEMU/KVM; kernel-level virtualization (better raw performance).
  * Runs headless easily (good for CI and servers).
  * Better integration with system-level tooling (virsh, virt-manager).
  * Requires `vagrant-libvirt` plugin to use with Vagrant.
* **VirtualBox**

  * User-space hypervisor with GUI support; simple desktop setup and snapshots.
  * Easier for cross-platform desktop demos (Windows/Mac).
  * Slightly lower I/O/CPU performance vs KVM for heavy workloads.
* **Which to choose for this demo:** prefer **libvirt/KVM** for headless, reproducible, closer-to-production behaviour; use VirtualBox if demoing on a laptop with a GUI or where libvirt isn't available.

**Assumptions / prerequisites**

* You already have the repo / project files, Vagrantfile and provisioning scripts in place.
* On your host machine you have at least one of:

  * libvirt + qemu + vagrant + `vagrant-libvirt` plugin OR
  * VirtualBox + Vagrant
* Basic host commands available: `git`, `vagrant`, `virsh` (if using libvirt), `ssh`, `curl`.
* The test uses:

  * VM1 = **attacker/operator** (run loadtests, nmap, locust, ab, curl)
  * VM2 = **target** (Rocky Linux, web app, Nginx, Fail2Ban, firewall)

---

# Steps

## Init
```bash
git clone https://github.com/Sight-ech/demos.git
cd demos/1_how_to_protect_a_vm_and_webapp/
```

### Share
Vagrant / lab setup: https://github.com/Sight-ech/how_to/blob/main/set_up_vagrant_ubuntu.md
Secure VPS Rocky Linux: https://github.com/Sight-ech/how_to/blob/main/secure_vps_rocky_linux.md
Secure Web App: https://github.com/Sight-ech/how_to/blob/main/secure_web_app.md


## Set up Vagrant VMs
```bash
# Check hardware virtualization support
egrep -c '(vmx|svm)' /proc/cpuinfo   # Prerequisite: hardware virtualization support
# should return a number > 0

# Check libvirt installation
sudo systemctl status libvirtd
sudo systemctl enable --now libvirtd

# Check Vagrant and libvirt plugin installation
vagrant --version
virsh --version   # if using libvirt

# Check Vagrant libvirt plugin
vagrant plugin list | grep vagrant-libvirt

# Set up and start Vagrant VMs
cd ./vagrant/
vagrant up attacker --provider=libvirt
vagrant up target --no-provision --provider=libvirt
vagrant provision target --provision-with install_docker

# Check VMs status
vagrant global-status
virsh --connect qemu:///system list --all
```

## SSH Attack and Protection

### First brute force attack
```bash
export VM2_IP=$(vagrant ssh target -c "hostname -I | awk '{print \$2}'" | tr -d '\r')

vagrant ssh attacker -c "nmap -Pn -p 22,80,443 $VM2_IP"


# Go into the attacker VM
vagrant ssh attacker

cd /vagrant/attacker/
pip install -r requirements.txt

export VM2_IP=192.168.56.102
python async_ssh_brutforce.py --host $VM2_IP \
--username vagrant \
--password-file 200_passwords.txt

# Found password is "vagrant"
ssh vagrant@$VM2_IP
```

### First protection steps

Here we will change the SSH port and limit the number of authentication attempts.

```bash
# From target VM
sudo vi /etc/ssh/sshd_config
# Change the port from 22 to 50022
# Set MaxAuthTries 3 (Not very useful, but good to have)

# Restart SSH
sudo systemctl restart sshd
```

```bash
# From attacker VM
python async_ssh_brutforce.py --host 192.168.56.102 --port 50022 --username vagrant --password-file 200_passwords.txt
```
You'll see that the brute force attack fails now and cannot find the password.
For sure, if we would improve the brute force script to retry after some time, it could eventually find the password.

Now test connection from localhost to the target with the password, you'll see that too many attempts will block you for some time.

```bash
# From localhost
ssh -p 50022 vagrant@192.168.56.102
```
(Remove MaxAuthTries to avoid being blocked when testing manually.)

### Second protection steps

Here we will set up fail2ban to block IPs that try to brute force SSH.

```bash
# From target VM

# Install fail2ban
sudo dnf install epel-release -y
sudo dnf install fail2ban -y

# Set up fail2ban for SSH
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

sudo cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local
sudo vi /etc/fail2ban/jail.local
# Under [sshd], set:
# enabled = true
# port = 50022

# Restart fail2ban
sudo systemctl restart fail2ban
sudo systemctl status fail2ban
```

> (Attention: Change the ssh port in the Vagrantfile to 50022 to keep Vagrant SSH working after changing the SSH port on the target VM.)
> config.ssh.port = 50022


```bash
# From attacker VM
python async_ssh_brutforce.py --host 192.168.56.102 --port 50022 --username vagrant --password-file 200_passwords.txt
```

Now try several times to brute force SSH again. After 3 failed attempts, your IP should be banned and further attempts will be blocked.

Find another way to access the VM, and check the fail2ban-client status:

```bash
sudo fail2ban-client status
sudo fail2ban-client status sshd
```

As you can see, the SSH protection is now effective.
```
Status
|- Number of jail:      1
`- Jail list:   sshd
#
Status for the jail: sshd
|- Filter
|  |- Currently failed: 1
|  |- Total failed:     19
|  `- Journal matches:  _SYSTEMD_UNIT=sshd.service + _COMM=sshd + _COMM=sshd-session
`- Actions
   |- Currently banned: 2
   |- Total banned:     2
   `- Banned IP list:   192.168.56.101 192.168.56.1
```

You can unban your IP with:

```bash
sudo fail2ban-client set sshd unbanip 192.168.56.1
# Or second attacker IP
sudo fail2ban-client set sshd unbanip 192.168.56.101
```

### Third protection steps

The best way to protect SSH is to use key-based authentication and disable password authentication. It will completely block brute force attacks.

For that, we will generate an SSH key pair on our host machine, copy the public key to the VM, and disable password authentication in SSH.

```bash
# Generate SSH key pair
ssh-keygen -t ed25519 -C "your_email@example.com" -f ./keys/id_rsa
ssh-copy-id -p 50022 -i ./keys/id_rsa.pub vagrant@192.168.56.102

ssh -i ./keys/id_rsa -p 50022 vagrant@192.168.56.102

# Disable password authentication
sudo vi /etc/ssh/sshd_config
# Set PasswordAuthentication no

# Restart SSH
sudo systemctl restart sshd
```

Test again the brute force attack:
```bash
# From attacker VM
python async_ssh_brutforce.py --host 192.168.56.102 --port 50022 --username vagrant --password-file 200_passwords.txt
```

It will fail to connect since password authentication is disabled.

## Web App Attack and Protection

### Set up the web app

```bash
vagrant provision target --provision-with install_docker
vagrant provision target --provision-with deploy_webapp
```

### Test the web app

```bash
# Check the health
curl http://192.168.56.102:8080/health

# Get current values (Non authenticated) --> Unauthorized
curl http://192.168.56.102:8080/add

# Login
curl -s -X POST http://192.168.56.102:8080/login   -H "Content-Type: application/json"   -d '{"username":"demo","password":"changeme"}'   -c cookies.txt

# Get current values (Authenticated) --> Return sum
curl -s http://192.168.56.102:8080/add -b cookies.txt

# Add value (Authenticated)
curl -s -X POST http://192.168.56.102:8080/add -H "Content-Type: application/json"   -d '{"value":5}' -b cookies.txt

# Get current values (Authenticated) --> Return sum: 5
curl -s http://192.168.56.102:8080/add -b cookies.txt
```

### Brute force attack on web app login

```bash
# From attacker VM
cd /vagrant/attacker/
```



### first protection steps

Verify that files:

```bash
access_log /var/log/nginx/api.access.log;
error_log  /var/log/nginx/api.error.log;
```

Or set it here:
/etc/nginx/sites-available/api.conf
sudo systemctl reload nginx

### Create the filter
sudo vi /etc/fail2ban/filter.d/nginx-api-auth.conf

Add:
```
[Definition]
failregex = ^<HOST> -.*"(GET|POST|PUT|DELETE|PATCH).*HTTP.*" (401|403)
ignoreregex =
```

### Create the jail
sudo vi /etc/fail2ban/jail.d/nginx-api-auth.local

Add:
```
[nginx-api-auth]
enabled = true
filter = nginx-api-auth
logpath = /var/log/nginx/api.access.log
maxretry = 5
findtime = 600
bantime = 86400
ignoreip = 127.0.0.1/8 ::1
action = iptables[name=APIAuth, port=http, protocol=tcp]
```

### Reload fail2ban
```bash
sudo fail2ban-client reload

# Restart fail2ban
sudo systemctl restart fail2ban
sudo systemctl status fail2ban
```

### Check the status
```bash
sudo fail2ban-client status nginx-api-auth
```




