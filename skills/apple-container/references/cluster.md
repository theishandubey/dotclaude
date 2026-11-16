# Clusters

`container cluster` runs a local Kubernetes cluster as container VMs, using a `kindest/node` image and `kubeadm`.
It is experimental, so check `container cluster create --help` before relying on a flag.
It needs `kubectl` on the Mac and a running `container system`.

## Lifecycle

```bash
container cluster create --name agent-k8s --cpus 4 --memory 8g
kubectl --context agent-k8s get nodes
container cluster list
container cluster delete --name agent-k8s
```

- The name defaults to `cluster-dev`, and the kubectl context has the same name.
- `create` merges credentials into `~/.kube/config` and `delete` removes them.
  Tell the user, and pass the context explicitly rather than switching their current one.
- `container cluster write-config --name <n> --kubeconfig <path>` writes the context to another file instead.
- Each node defaults to 1/4 of host CPUs and memory, at least 2 CPUs and 2 GB.
- `--workers 3` adds worker nodes and taints the control plane; `--workers count=2,cpus=4,memory=8g` sizes a group and can repeat.
- `--node-image docker.io/kindest/node:<version>` picks the Kubernetes version.
- `--cni ./manifest.yaml` replaces the bundled kindnet with a plain manifest; `--cni NONE` installs none and does not wait for nodes to be Ready.
- `--rm` removes node containers on stop, but the cluster stays listed as `stopped` until `cluster delete`.
- After `container system stop`, a cluster does not come back: delete and create it again.

## Node containers

`container ls` hides cluster nodes even with `--all`, and `start`, `stop`, `kill` and `rm` report them as not found.
`inspect`, `logs`, `exec`, `stats` and `clean` work on a named node.
Use `container cluster list --nodes` to see them.

## Local images

Without `--shared-image-store`, nodes pull every image from a registry.
With it, nodes use the local image store first, so `container build -t my-app:dev .` then `kubectl run my-app --image=my-app:dev` works without a push.
It is set at creation only.
After rebuilding a tag, use a new tag or `imagePullPolicy: Always`.

Ask before turning it on: anything with root on a node, including privileged pods and `hostPath` mounts, can read every local image, private ones included, and a local image wins over a registry image of the same name.
