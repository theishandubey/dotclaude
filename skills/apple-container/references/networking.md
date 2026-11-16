# Networking

`container system start` creates a vmnet network named `default`.
Each container gets its own IP on its network, reachable from the Mac and from other containers on the same network.
Find it with `container ls` or `container inspect <name>`.

## From the Mac to a container

```bash
container run -d --name agent-web -p 8080:80 nginx:latest
container run -d --name agent-api -p 127.0.0.1:8080:8000 node:latest npx http-server -a :: -p 8000
container run -d --name agent-v6 -p '[::1]:8080:8000' node:latest npx http-server -a :: -p 8000
```

The spec is `[host-ip:]host-port:container-port[/tcp|udp]`.
With several networks, published ports go to the first one.
`--publish-socket host_path:container_path` publishes a Unix socket.

## Names instead of IPs

Two steps, both needed, and both change the user's system, so ask first:

1. Set the domain in `~/.config/container/config.toml`, then restart the service with `container system stop` and `container system start`:

   ```toml
   [dns]
   domain = "test"
   ```

2. Point macOS at it: `sudo container system dns create test`.

After that, `agent-web` resolves as `agent-web.test` from the Mac and from other containers on `default`.
`--network default,alias=api.test,alias=.gateway.test` adds names; a leading dot matches every name below it.
Aliases resolve on the Mac only under domains made with `dns create`.

## Container to container

Needs macOS 26.
Use the domain-qualified name on `default` (`curl http://agent-web.test:8000`) or the target's IP.
Lookup by bare hostname on a custom network does not work yet (apple/container#1809); use the IP there.

## Custom networks

macOS 26 only.

```bash
container network create agent-net
container network create agent-net --subnet 192.168.100.0/24 --subnet-v6 fd00:1234::/64
container network create --internal agent-sandbox
container run -d --name agent-web --network agent-net nginx:latest
container network rm agent-net
```

Networks are isolated from each other.
`--internal` makes a host-only network with no outside access.
A network can be deleted only once no container is attached.

## From a container to a Mac service

```bash
sudo container system dns create host.container.internal --localhost 203.0.113.113
container run --rm alpine/curl curl http://host.container.internal:8000
```

Pick the IP from `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24` or `172.16.0.0/12` to avoid clashes.
This disables iCloud Private Relay, and the packet-filter rule is lost on restart, so ask before setting it up.

## SSH agent

`--ssh` mounts the host agent socket at `/var/host-services/ssh-auth.sock` and sets `SSH_AUTH_SOCK`, so the container can act as the user over SSH.
Use it only when asked.

## DNS defaults for containers

`[container.dns]` in `config.toml` sets `domain`, `nameservers`, `searchDomains` and `options` for every run and build.
`--dns`, `--dns-search` and `--dns-option` override per run, and `--no-dns` skips DNS setup.
