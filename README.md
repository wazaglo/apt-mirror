# apt-mirror

Centralised Debian and Ubuntu package mirrors running inside EKS, with the
archive on EFS and served through the existing ALB + nginx edge. Internal
clients point apt at an internal endpoint instead of reaching the public Debian
and Ubuntu archives directly.

| | |
|---|---|
| Debian 12 (bookworm) | `https://debian-mirror.azubisuccess.space` |
| Ubuntu 24.04 (noble) | `https://ubuntu-mirror.azubisuccess.space` |
| Snapshots | `https://debian-mirror.azubisuccess.space/snapshots/<name>/` |
| Cluster | `eks-lab` (EKS 1.36), `us-west-1` |
| Storage | EFS `archcloud-mirror-efs` `fs-0b0491ead2bac1c8c`, one access point per distro |

**Start here → [docs/mirror.md](docs/mirror.md)** for the operating guide and
the failure modes that are easy to reintroduce.

## Client configuration

Debian 12:

```
deb http://debian-mirror.azubisuccess.space/debian bookworm main contrib non-free non-free-firmware
deb http://debian-mirror.azubisuccess.space/debian bookworm-updates main contrib non-free non-free-firmware
deb http://debian-mirror.azubisuccess.space/debian-security bookworm-security main contrib non-free non-free-firmware
```

Ubuntu 24.04:

```
deb http://ubuntu-mirror.azubisuccess.space/ubuntu noble main restricted
deb http://ubuntu-mirror.azubisuccess.space/ubuntu noble-updates main restricted
deb http://ubuntu-mirror.azubisuccess.space/ubuntu noble-security main restricted
```

HTTPS works too — the ALB terminates the wildcard `*.azubisuccess.space`
certificate. Internal-only clients can use `http://` to avoid a CA bundle
requirement.

A client pinned to a frozen set instead of the live mirror:

```
deb http://debian-mirror.azubisuccess.space/snapshots/20260928-140036Z/debian bookworm main contrib non-free non-free-firmware
```

## What is where

```
apps/
  mirror/          the product: sync, snapshots, serving tier, image build context
  nginx/           public edge — host-based vhosts, the ALB Ingress
  monitoring/      observability for the mirror and the edge
  alb/             ALB controller service account (IRSA)
envs/{dev,prod}/   the only directories CI deploys
platform/          cluster-scoped: PVs, the deploy ClusterRole, trigger RBAC — applied BY HAND
infra/             Helm releases and the nightly node scheduler — applied BY HAND
terraform/         VPC and EKS. NOT in CI
docs/              operating guide, ADRs, runbooks
```

Deploy model, in one line: `apps/**` and `envs/**` are applied by CI on push to
`main`; everything cluster-scoped or Helm-managed is applied by a human. The
reason, and what it costs, is in
[ADR-0004](docs/adr/0004-push-gitops-least-privilege.md).

## How a sync happens

A trigger CronJob patches a `sync-at` annotation on the sync Deployment, which
rolls its pod. The new pod runs `apt-mirror` against the EFS spool, then idles
holding the mount warm until the next trigger.

| job | schedule (UTC) | state |
|---|---|---|
| Debian 12 sync | 10:00 daily | active |
| Ubuntu 24.04 sync | 12:30 daily | active |
| Snapshot | 12:30 daily | suspended — run by hand first |

Ubuntu is staggered off the Debian slot so the two do not contend for the same
node bandwidth.

**Compute is off every night.** The node group terminates at 17:58 UTC and
returns at 10:00, so endpoints answer `502` overnight and a sync in progress is
interrupted and resumed the next morning. apt-mirror keeps its state, so this
resumes rather than restarts.

## Capacity

The node group sits at its pod ceiling: 5 nodes × 11 = 55 slots, currently 54 in
use. That is why the serving tier is a single replica, why Grafana runs one
replica, and why the monitoring rollouts use `maxSurge: 0`. See
[node-pressure.md](docs/runbooks/node-pressure.md).

## Repository conventions

- Manifests carry no comments. The reasoning lives in
  [docs/mirror.md](docs/mirror.md) and [docs/adr/](docs/adr/).
- Images are pinned by digest.
- A new app directory must be referenced from an `envs/*/kustomization.yaml`.
  Kustomize is not a recursive walker, and an unreferenced directory deploys
  nothing while CI stays green.

## Evidence

`docs/evidence/` holds captured proof of the running system — AWS resource
state, endpoint checks, and console screenshots. Regenerate with
`hack/capture-evidence.sh`.
