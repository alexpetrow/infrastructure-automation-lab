# Troubleshooting

## Ansible become timeout on Ubuntu 26.04

**Symptom:** Tasks with `become: true` fail with
`Timeout (12s) waiting for privilege escalation prompt`, even with the correct sudo password.

**Root cause:** Starting with Ubuntu 25.10, the default `sudo` is `sudo-rs` (Rust rewrite).
Its password prompt handling is not compatible with how Ansible detects the become prompt.
Reported in Launchpad bug #2122414.

**Fix:** Point Ansible to the classic sudo binary, which is still installed as `sudo.ws`:
`ansible_become_exe: sudo.ws` in the inventory. No system-wide changes on the managed hosts.

**Alternative:** Switch the system default with
`sudo update-alternatives --set sudo /usr/bin/sudo.ws` (changes behavior for all users).

## Locked out after SSH hardening

**Symptom:** `Permission denied (publickey)` for a user that should have access.

**Checks:**
- The user is listed in `AllowUsers` (`ssh_hardening_allow_users`).
- The public key is in `~/.ssh/authorized_keys` of that user.
- `sudo sshd -T | grep -i -E 'passwordauthentication|allowusers|permitrootlogin'`
  shows the effective configuration after all drop-in files are merged.

**Recovery:** Use the VM console (VNC in the lab, serial console or cloud provider console
in production), fix or remove `/etc/ssh/sshd_config.d/10-hardening.conf`,
then run `sudo systemctl restart ssh`.

**Prevention:** Keep an active SSH session open while applying SSH changes,
and validate configuration with `sshd -t` before restarting the service.

## Docker published ports bypass UFW

**Symptom:** A container started with `-p 8080:80` is reachable from the network,
even though UFW is set to default deny and port 8080 is not allowed.

**Root cause:** Docker manages its own iptables rules for port publishing and inserts them
before the UFW chains. Traffic to published ports never reaches UFW rules.

**Mitigation used in this lab:**
- Publish container ports on localhost only: `-p 127.0.0.1:8080:80`.
- Expose services through a reverse proxy (nginx) on ports explicitly allowed in UFW.

**Production options:**
- Filter traffic in the `DOCKER-USER` iptables chain, which Docker evaluates before its own rules.
- Cloud security groups or network firewalls in front of the host.
- Never rely on host firewall alone for containers with published ports.

## Disk full: root volume uses only half of the disk

**Symptom:** `no space left on device` (seen on the control node during `terraform init`),
although the VM disk is 20 GB.

**Root cause:** The Ubuntu Server installer with LVM allocates only part of the volume group
to the root logical volume and leaves the rest unallocated.
`df -h /` shows about 10 GB, while `sudo vgs` shows free space in `VFree`.

**Fix (manual, control node):**
`sudo lvextend -r -l +100%FREE /dev/ubuntu-vg/ubuntu-lv`
extends the logical volume and the filesystem online, without reboot.

**Prevention (automated, managed nodes):** The `common` role extends the root logical volume
whenever the volume group has free space. The task is skipped on hosts without LVM
or without free space, so it is safe to re-run.

**Related:** Terraform downloads a separate copy of each provider (~700 MB for AWS) per
working directory. A shared `plugin_cache_dir` in `~/.terraformrc` avoids duplicates.
