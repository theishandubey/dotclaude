---
name: apple-container
description: Use when running, building or debugging Linux containers, container machines or local Kubernetes clusters with Apple's `container` CLI on a Mac. Not for Docker, Podman, Colima or OrbStack.
---

# Apple container

[`container`](https://github.com/apple/container) runs each Linux container in its own lightweight VM on Apple silicon, and reads and writes OCI images.
Most `run` and `build` flags match Docker's, so this file covers only where it differs and the defaults to apply when you act.

## Before the first command

- Run `container --version` and `container system status`.
  If it is missing, the install is the signed `.pkg` from the releases page; there is no Homebrew formula.
  If the service is down, run `container system start` and accept the kernel download on first run.
- Run `sw_vers -productVersion`.
  macOS 26 is the supported target.
  On macOS 15 there is no `container network`, `--network` errors, and containers cannot reach each other; use `--publish` only.
- Before using a flag you have not used in this session, run `container <command> --help`.
  The CLI changes between releases and its help is the authority, not this file or your memory.

## Where it differs from Docker

- Every container has its own IP (`container ls` shows it), not a shared localhost.
  Reach a service from the Mac with `-p host:container` or that IP.
  A service bound to `127.0.0.1` inside is unreachable; bind `0.0.0.0`, which the virtual network keeps off the outside world.
- Defaults are 4 CPUs and 1 GiB per container, and 2 CPUs and 2 GiB for the builder VM.
  To resize the builder: `container builder stop`, `container builder delete`, `container builder start --cpus N --memory M`.
- Memory freed inside a VM is not returned to macOS; restart a long-running memory-heavy container to release it.
- There is no Compose.
  Start services one by one, and see [networking](references/networking.md) for how they find each other.
- Anonymous volumes (`-v /path`) survive `--rm`; prefer named volumes.
- `--scheme` is `http` or `https` (default `https`); a plain-HTTP registry needs `--scheme http`.
- `amd64` images run under Rosetta; build both with `container build --arch arm64 --arch amd64`.

## Container, machine or cluster

- **Container** (`container run`): one app, service or job.
  The default choice.
- **Machine** (`container machine create`): a persistent Linux box that boots the image's init, uses the host username and mounts the Mac home.
  Only when the user wants a Linux environment to live in or needs systemd.
  Read [machines](references/machines.md) first.
- **Cluster** (`container cluster create`): local Kubernetes, experimental.
  Read [cluster](references/cluster.md) first.

## Defaults when you act

Apply these unless the user asks otherwise.

- Name what you create `agent-<task>`, for example `agent-pg-test`.
  Before finishing, remove what you started: `for c in $(container ls -a -q | grep '^agent-'); do container rm -f "$c"; done`, then the same with `container volume ls -q` and `container network ls -q` and their `rm`.
- Tool calls have no TTY, so never pass `-it`.
  Use `container run --rm <image> <cmd>` for one-off commands, `-d` plus `container logs` for services, and `container exec <name> <cmd>` inside a running one.
- Set `--cpus` and `--memory` for anything heavier than a shell.
- Mount the narrowest host path the task needs, with `:ro` unless it must write; never mount `$HOME`.
- Pass `--ssh` only when asked, since it lets the container use the user's ssh-agent.
- For code you did not write or do not trust, use a plain container with no `--ssh` and no bind mounts, and on macOS 26 attach it to a network made with `container network create --internal` so it has no internet.
  Never run such code in a machine.
- Ask before anything that touches what you did not create: `rm --all`, `image prune -a`, `volume prune`, `network prune`, `machine rm`, `cluster delete`, `system stop`, or a `config.toml` edit.

## References

Read the one that matches the task:

- [machines](references/machines.md): container machine safety, creation, resizing and custom images.
- [networking](references/networking.md): ports, DNS names, container-to-container, host services, custom networks.
- [storage](references/storage.md): named and anonymous volumes, bind mounts, tmpfs, disk cleanup.
- [cluster](references/cluster.md): local Kubernetes clusters.
- [troubleshooting](references/troubleshooting.md): symptoms with causes and fixes, logs, `config.toml`.
