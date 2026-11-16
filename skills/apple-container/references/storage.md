# Storage

## Bind mounts

```bash
container run --rm -v "$PWD/data:/data:ro" alpine ls /data
container run --rm --mount source="$PWD/data",target=/data,readonly alpine ls /data
```

Host paths must be absolute.
Mount the narrowest directory the task needs, read-only unless it must write.

## Named volumes

Faster than bind mounts and not shared with the host.
Each is an ext4 sparse disk image that can grow to 512 GiB unless sized.

```bash
container volume create -s 10g agent-pgdata
container run -d --name agent-pg -e POSTGRES_PASSWORD=dev -v agent-pgdata:/var/lib/postgresql/data -p 5432:5432 postgres:16
container volume ls
container volume inspect agent-pgdata
container volume rm agent-pgdata
```

`--opt journal=ordered|writeback|journal[:size]` sets the ext4 journal mode (`ordered` is the default).
A volume in use cannot be deleted.

## Anonymous volumes

`-v /path` with no source creates a volume named by a bare UUID with the label `com.apple.container.resource.anonymous`.
Unlike Docker, `--rm` does not delete it.
Avoid them; if one was made, find and delete it by label:

```bash
container volume list --format json | jq -r '.[] | select(.configuration.labels["com.apple.container.resource.anonymous"] != null) | .id'
container volume rm <id>
```

## tmpfs

`--tmpfs /scratch` or `--mount type=tmpfs,target=/scratch,size=512M,mode=1777` gives memory-backed storage that vanishes when the container stops.
`/dev/shm` defaults to 64 MiB; raise it with `--shm-size 1G`.

## Disk use

Container and volume images grow but do not shrink when files are deleted.

```bash
container system df
container clean <running-container>
container prune
```

`container clean` returns freed blocks from a running container's root filesystem and named volumes.
`container prune` removes every stopped container, `image prune` removes untagged images, `image prune --all` removes every unreferenced image, and `volume prune` removes every unreferenced volume.
Those prunes can delete the user's own data, so ask before running them.
`container builder stop` then `container builder delete` drops the build cache.

## Images from containers

`container commit <container> <image:tag>` saves a container's filesystem as an image, and `container export -o out.tar <container>` saves it as a tar.
Both work on running containers by taking a snapshot.
