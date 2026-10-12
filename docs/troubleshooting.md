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
