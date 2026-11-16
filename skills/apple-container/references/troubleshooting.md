# Troubleshooting

## Where to look

```bash
container system status
container logs <name>
container logs --boot <name>
container system logs --last 10m
container inspect <name>
container system property list
```

`logs --boot` shows the VM kernel and init log, the place to start when a container exits at once.
`logs -f` waits for output, so do not use it in a tool call; read `logs` again instead.
`system property list` prints the settings the service is really using.

## Symptoms

| Symptom | Cause | Fix |
|:--|:--|:--|
| `container: command not found` | Not installed | The signed `.pkg` from github.com/apple/container/releases. |
| Commands fail to reach the service | Service not started | `container system start`. |
| Asked to install a kernel | No guest kernel yet | Accept, or `container system kernel set --recommended`. |
| `--network` errors, no `container network` | macOS 15 | Needs macOS 26; use `--publish` meanwhile. |
| One container cannot reach another | macOS 15, different networks, or a bare hostname on a custom network | macOS 26, same network, and the IP or `<name>.<domain>` on `default`. |
| Container has no network on macOS 15 | vmnet and the network helper disagree on the subnet | Restart the service; nothing else may use `192.168.64.0/24`. Fixed only on macOS 26. |
| `localhost:PORT` does not answer | No `-p`, or the app listens on `127.0.0.1` inside | Add `-p host:container`; bind the app to `0.0.0.0` or `::`. |
| `<name>.test` does not resolve on the Mac | Only one of the two DNS steps done | Set `[dns] domain`, restart the service, and run `sudo container system dns create test`. |
| Push or pull to a local registry fails on TLS | Default scheme is `https` | `--scheme http` for a plain-HTTP registry. |
| Build is slow or runs out of memory | Builder VM is 2 CPUs and 2 GiB | `container builder stop`, `container builder delete`, `container builder start --cpus 8 --memory 16G`. |
| Host RAM stays high after heavy work | Freed guest memory is not returned to macOS | Restart the container. |
| Disk keeps growing | Sparse images do not shrink on delete | `container clean <name>`, then the prunes in [storage](storage.md) after asking. |
| `machine set` had no effect | Applied only on next boot | `container machine stop <name>`, then `container machine run`. |
| Cluster gone after `system stop` | Control plane does not restart | `container cluster delete` then `create`. |
| Private Relay stopped working | A `dns create --localhost` domain disables it | Expected while the domain exists; `sudo container system dns rm <domain>` when it is no longer needed. |
| Nested virtualization unsupported | Needs M3 or later and a `CONFIG_KVM=y` kernel | Pass `--virtualization --kernel <path>`. |

## config.toml

`~/.config/container/config.toml` is read once at start, so restart with `container system stop` and `container system start` after an edit, and ask before either.

```toml
[build]
cpus = 2
memory = "2048mb"
rosetta = true

[container]
cpus = 4
memory = "1gb"

[dns]
domain = "test"

[network]
subnet = "192.168.100.0/24"
subnetv6 = "fd00:abcd::/64"

[registry]
domain = "docker.io"
```

Memory sizes are quoted strings with binary units: `"2g"`, `"2048mb"`.
`[build] rosetta = false` stops builds from using Rosetta for `amd64`.

## Install, update, remove

The installer puts files under `/usr/local`.
Stop the service first, then run `/usr/local/bin/update-container.sh` to upgrade, and `container system start` after.
To downgrade, `/usr/local/bin/uninstall-container.sh -k` then `update-container.sh -v <version>`.
`uninstall-container.sh -k` keeps user data and `-d` deletes it.
Ask before uninstalling.
