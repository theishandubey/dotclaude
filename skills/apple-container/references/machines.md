# Container machines

A machine is a persistent Linux environment: it boots the image's `/sbin/init`, keeps its filesystem across stop and start, and runs commands as a user matching the host account.
`container machine` has the alias `m`.

## What a machine can reach

Apple's docs say a machine is closer to running a program directly on the Mac than to running a container.
By default it:

- mounts the Mac home read-write at the same path (`/Users/<you>`), so anything inside can change repos and dotfiles with the user's permissions;
- forwards the host `SSH_AUTH_SOCK`, so anything inside can use the user's ssh-agent;
- has all Linux capabilities and no masked or read-only `/proc` and `/sys` paths;
- gives the account passwordless sudo, so root inside can write anywhere in the mounted home.

So create machines only from images the user trusts, and pass `--home-mount ro` (or `none`) unless the user wants Linux to write to their Mac home.
Say which you chose and why in one line.
There is no documented flag to stop the ssh-agent forwarding.

## Create and use

```bash
container machine create --name agent-dev --home-mount ro --cpus 4 --memory 8G ubuntu:24.04
container machine run -n agent-dev -- uname -a
container machine run -n agent-dev --root -- apt-get update
container machine ls
container machine stop agent-dev
container machine rm agent-dev
```

- `create` boots the machine unless `--no-boot` is passed.
- Memory defaults to half of host RAM, which is usually too much; set `--memory`.
- `run` boots a stopped machine, runs as the host user, and starts in the matching directory when the Mac's current directory is under the home.
  With no command it opens an interactive login shell, which a tool call cannot use, so always pass a command.
- Put `--` before a command whose arguments start with `-`.
- `set-default <name>` lets later commands drop `-n`.
- `rm` deletes the machine's persistent storage; anything outside the mounted home is gone.
  Ask first.
- `--user`, `--uid`, `--gid` and `--home` override the account at creation; the Linux home defaults to `/home/<user>`.

## Change resources or mounts

`container machine set` writes to disk and applies after the next stop and start:

```bash
container machine set -n agent-dev cpus=2 memory=4G home-mount=none
container machine stop agent-dev
container machine run -n agent-dev -- nproc
```

## systemd and custom images

Any image with `/sbin/init`, a POSIX `/bin/sh`, `getent`, `date`, `chown`, `mkdir`, `cp` and `tr` works.
A bare `alpine` gives a shell but not `systemctl`.
For systemd, build Apple's Ubuntu example as written:

```dockerfile
FROM ubuntu:24.04
ENV container container
RUN apt-get update && \
    apt-get install -y dbus systemd openssh-server net-tools iproute2 iputils-ping curl wget vim-tiny man sudo && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    yes | unminimize
RUN >/etc/machine-id
RUN >/var/lib/dbus/machine-id
RUN systemctl set-default multi-user.target
RUN systemctl mask dev-hugepages.mount sys-fs-fuse-connections.mount \
      systemd-update-utmp.service systemd-tmpfiles-setup.service console-getty.service
RUN systemctl disable networkd-dispatcher.service
RUN sed -i -e 's/^AcceptEnv LANG LC_\*$/#AcceptEnv LANG LC_*/' /etc/ssh/sshd_config
```

```bash
container build -t local/ubuntu-machine:latest .
container machine create local/ubuntu-machine:latest --name agent-ubuntu --home-mount ro
```

The user account is provisioned on every boot by editing `/etc/passwd`, `/etc/group` and `/etc/shadow` directly, so the image needs no `useradd`.
Passwordless sudo works only if `sudo` is installed.

## Nested virtualization

Needs an M3 or later Mac and a kernel built with `CONFIG_KVM=y`; the default kernel lacks it.

```bash
container machine create --virtualization --kernel ./vmlinux-kvm --name agent-kvm alpine:latest
container machine run -n agent-kvm -- ls -l /dev/kvm
```

`container machine set virtualization=true kernel=<path>` turns it on later; `kernel=` resets to the default kernel.
