# APT Mirror on EKS + EFS — Implementation Plan

**Status:** planned, not started. Written 2026-09-27.
**Source of truth for the images:** `/home/wazaglo/mirrors` (built following the
conventions in `ha-apt-mirror-runbook`).

---

## 1. What we are doing

Take the existing HA apt mirror platform (Ubuntu 24.04 noble + Debian 12 bookworm,
already built as two container images and pushed to `wazaglo/mirrors`) and move
where the mirror **data** lives. Today the containers sync into a CloudStack
SharedFS NFS export. We are replacing that store with a single EFS file system
mounted as persistent volumes in EKS: One Zone in `us-west-1a`, one access point
per distro, backups deliberately off, on a dedicated `t3.medium` nodegroup.

This preserves the two properties the runbook depends on — shared POSIX access
from both mirror nodes, and support for hardlinks / `flock` / atomic renames — so
the `cp -al` snapshots and single-active sync locking keep working unchanged.

Incremental cost: **~$22/week**, versus ~$56/week for a Standard two-mount-target
EFS.

---

## 2. Verified environment facts

| Item | Value |
|---|---|
| Account | `195675606509` (`wazaglo`) |
| Region | `us-west-1` |
| VPC | `vpc-0bab80c57b59d53be` (`10.0.0.0/16`) |
| EKS cluster | `eks-lab`, v1.36, ACTIVE |
| Nodegroup | `ng-eks` — t3.small ×5, desired 5 / min 2 / max 5, ON_DEMAND, cluster-autoscaler enabled |
| Nodes | 3 in `us-west-1a` (`10.0.11/24`), 2 in `us-west-1c` (`10.0.12/24`) |
| Subnets | priv1-1a `subnet-035bd6840b31e5205`, priv2-1c `subnet-0f6034326efbaa2ae`, pub1-1a `subnet-0aa1f2e4e1e684c22`, pub2-1c `subnet-06a76730006f45c54` |
| NAT gateway | `nat-00e6923049c667c66` (1a) — single, consolidated 2026-09-27 |
| EFS (existing) | `fs-0ddb254be08c6267a` "eks-shared-efs", Standard, 2 mount targets, elastic, 356 MB, `default-backup: ENABLED` |
| EFS CSI | installed (`efs-csi-driver` v3.4.2-eksbuild.1) + `efs-sc` StorageClass (`efs-ap`), live PVC in `monitoring` |
| ALB | `k8s-nginxdem-nginx-98f1f39520` + aws-load-balancer-controller + external-dns + external-secrets |
| Domain | `azubisuccess.space` |
| Node capacity | t3.small = 1.4 GiB allocatable; memory **limits already at 121–156%** overcommitted |

### Images — already built and pushed, do not rebuild

| Image | Digest |
|---|---|
| `wazaglo/mirrors:ubuntu24-v2-noble-252G` | `sha256:c2038e8fc55868c024e40162b5f1d94a1c0dee1368c5fab1213ed0ebf780eaa5` |
| `wazaglo/mirrors:debian12-v1-bookworm-120G` | `sha256:7e10c5f693fdbb3eb27b584a63b07cadcff5ffd8c41e3b326989dfb76ac3fac3` |

Both run a long loop (`while true; apt-mirror; sleep 86400`). For noble, expect
`241.2 GiB will be downloaded`. A figure near `405 GiB` means the entrypoint
pre-filter has regressed — the filter on
`skel/*/dists/*/main|restricted/binary-amd64/Packages.gz` (excluding
`aws|azure|gcp|oracle|nvidia|cuda|fabricmanager`) must run *before* apt-mirror
builds its download list.

### EFS pricing — verified via pricing API, us-west-1

| Class | Rate |
|---|---|
| Standard General Purpose | $0.33 / GB-Mo, **per mount target** |
| One Zone General Purpose | $0.176 / GB-Mo, 1 mount target |
| Infrequent Access | $0.0283 / GB-Mo **+ $0.011 / GB read** |
| Archive | $0.01 / GB-Mo + $0.033 / GB access |

Sizing: 362 GB total (243 noble + 119 bookworm).

| Option | /month | /week |
|---|---|---|
| Standard, 2 mount targets | $238.92 | $55.75 |
| Standard, 1 mount target | $119.46 | $27.87 |
| **One Zone, 1 mount target (chosen)** | **$63.71** | **$14.87** |

**Rejected alternatives**

- *Infrequent Access / Archive* — storage is cheap but the per-GB retrieval fee
  across 24k+ files on every `apt-get` is a net loss.
- *S3 via mountpoint-s3 / rclone / s3fs* — no hardlinks, no reliable `flock`,
  no atomic rename. Breaks `cp -al` snapshots and the single-active sync lock.
- *EBS gp3* — cannot be shared between mirror nodes, so it breaks the HA design
  unless permanently single-writer.

**No backups — a deliberate decision.** The store is a byte-for-byte copy of a
public upstream repo, so a restore is just `apt-mirror` re-run, costing hours and
free upstream bandwidth. EFS backup bills per GB-month at a premium over storage
in exchange for zero recovery value here.

---

## 3. Target topology

```
CI → main → envs/dev/ → namespace "apt-mirror"
  ├── ubuntu24-mirror  (1 replica) ─┐
  ├── debian12-mirror  (1 replica) ─┤ PVCs (static PV → access point)
  └── mirror-nginx     (1 replica) ─┘
                            ↓
        apt-mirror-fs (EFS One Zone, us-west-1a, backup DISABLED)
            AP fsap-ubuntu24 → /ubuntu24
            AP fsap-debian12 → /debian12

ALB (existing) → mirror-nginx (Host-based) → /mirror/ + /snapshots/
```

New nodegroup `ng-apt-mirror`: **t3.medium**, subnet **1a only**, min 1 /
desired 1 / max 3, ON_DEMAND, label `workload=apt-mirror`, launch template with
`cpu_credits = "unlimited"`, and **no cluster-autoscaler tag** (so it never
scales to zero — unlike `ng-eks`, which is autoscaler-managed).

Keeping the nodegroup in 1a only keeps all EFS I/O intra-AZ. A 1c node talking
to a 1a One Zone file system pays $0.01/GB egress and adds latency.

---

## 4. Phase 1 — infrastructure (manual, Terraform)

New file `terraform/eks/apt-mirror.tf` containing:

1. **`aws_efs_file_system.apt_mirror`** — `availability_zone_name = "us-west-1a"`,
   `performance_mode = "generalPurpose"`, elastic throughput, `encrypted = true`,
   `backup_policy { status = "DISABLED" }`, tagged `Name = apt-mirror-fs`.
   - Deliberately **no `lifecycle_policy`** — it must never transition to
     Infrequent Access (see rejected alternatives).
   - For One Zone the throughput attributes differ from Standard
     (`provisioned_throughput_mode` vs `throughput_mode`). Confirm the exact
     names against provider `6.66.0` before `apply`.
2. **`aws_efs_access_point.ubuntu24` / `.debian12`** — POSIX `uid=0 gid=0`, roots
   `/ubuntu24` and `/debian12`, `creation_info { permissions = "0700" }`.
3. **`aws_efs_mount_target.apt_mirror`** — subnet `subnet-035bd6840b31e5205`
   (private1-1a).
4. **`aws_security_group.efs_nfs`** — ingress `tcp/2049` from `10.0.0.0/16`.
5. **`aws_launch_template.apt_mirror_t3`** —
   `credit_specification { cpu_credits = "unlimited" }` (see Gotchas #1).
6. **`aws_eks_node_group.apt_mirror`** — reuse the existing node role, subnets
   `[private1-1a]` only, `labels = { workload = "apt-mirror" }`.

Also disable backup on the **existing** Grafana EFS:

```bash
aws efs put-backup-configuration --file-system-id fs-0ddb254be08c6267a \
  --backup-policy Status=DISABLED
```

---

## 5. Phase 2 — cluster-scoped Kubernetes objects (manual `kubectl`)

The CI `apt-mirror-deployer` ClusterRole cannot create StorageClasses or PVs, so
these live in `platform/` and follow the existing "apply MANUALLY once" header
convention already used by `storageclass.yaml` and `pv-grafana.yaml`.

`platform/apt-mirror-storageclass.yaml`:

```yaml
provisioner: efs.csi.aws.com
parameters:
  provisioningMode: efs-ap
  fileSystemId: <new fsid>
  directoryPerms: "700"
reclaimPolicy: Retain
volumeBindingMode: Immediate
```

`platform/pv-apt-mirror-{ubuntu24,debian12}.yaml`:

```yaml
spec:
  capacity: { storage: 300Gi }   # cosmetic only — EFS ignores this
  volumeMode: Filesystem
  accessModes: [ReadWriteMany]
  persistentVolumeReclaimPolicy: Retain
  storageClassName: apt-mirror-sc
  csi:
    driver: efs.csi.aws.com
    volumeHandle: <new-fsid>::fsap-<ap-id>
```

---

## 6. Phase 3 — app manifests (CI-deployable)

New `apps/apt-mirror/{base,overlays/{dev,prod}}`, added to
`envs/dev/kustomization.yaml`. Follows the `apps/monitoring` pattern: plain
resource files with explicit namespaces (not `configMapGenerator`, which needs
the namespace patch hack the nginx app uses).

| File | Contents |
|---|---|
| `namespace.yaml` | `apt-mirror` — the CI role *can* create namespaces (it's in the ClusterRole) |
| `configmap-{ubuntu24,debian12}.yaml` | `mirror.list` + `apt.conf` + `postmirror.sh` as inline `data:`, byte-identical to the compose files |
| `pvc-{ubuntu24,debian12}.yaml` | RWX, `storageClassName: apt-mirror-sc`, `volumeName:` the static PV |
| `deployment-{ubuntu24,debian12}.yaml` | the mirror containers |
| `configmap-nginx-sites.yaml` | two Host-based vhosts → `/mirror/` + `/snapshots/` |
| `deployment-nginx.yaml`, `service.yaml`, `ingress.yml` | serving tier |
| `kustomization.yaml`, `overlays/{dev,prod}/kustomization.yaml` | mirrors the existing pattern |

Core of a mirror Deployment:

```yaml
initContainers:
  - name: prepare-spool
    image: wazaglo/mirrors@sha256:c2038e8f...
    command: ["/bin/bash", "-c"]
    args: ["set -euo pipefail; mkdir -p /spool/{mirror,skel,var,snapshots}; \
            install -m0644 /conf/mirror.list /etc/apt/mirror.list; \
            install -m0644 /conf/apt.conf /etc/apt/apt.conf.d/99custom; \
            install -m0755 /conf/postmirror.sh /spool/var/postmirror.sh"]
    volumeMounts: [{name: spool, mountPath: /spool}, {name: conf, mountPath: /conf}]
containers:
  - name: mirror
    image: wazaglo/mirrors@sha256:c2038e8f...
    securityContext: {runAsUser: 0, runAsNonRoot: false}
    env: [{name: TZ, value: "UTC"}]
    resources:
      requests: {cpu: 500m, memory: 1Gi}
      limits:   {memory: 2Gi}       # no CPU limit: IO-bound workload
    volumeMounts: [{name: spool, mountPath: /var/spool/apt-mirror}]
volumes:
  - name: spool
    persistentVolumeClaim: {claimName: ubuntu24-mirror-data}
  - name: conf
    configMap: {name: ubuntu24-mirror-conf}
terminationGracePeriodSeconds: 3600
# no probes — the entrypoint is a sleep-86400 loop
```

**Why the `initContainer`:** `mirror.list` hardcodes
`postmirror_script $base_path/var/postmirror.sh`, and the entrypoint globs
`skel/*/ubuntu/dists/*`. On a fresh access point none of those paths exist, and a
`subPath` mount into a missing EFS directory fails outright. The init container
creates them first, which lets `mirror.list` and `entrypoint.sh` stay **byte-identical**
to the compose versions already pushed.

**nginx must run as root.** With `directoryPerms: "700"` and POSIX `0:0` on the
access points, the stock nginx image's workers (uid 101) receive 403 on every
file. Set `runAsUser: 0` on the nginx container. This is the single most likely
first-run failure.

Resulting client sources:

```
deb http://apt-ubuntu24.<domain>/mirror/archive.ubuntu.com/ubuntu noble main restricted
deb http://apt-debian12.<domain>/mirror/deb.debian.org/debian bookworm main contrib non-free non-free-firmware
```

---

## 7. Phase 4 — validate

```bash
kubectl kustomize envs/dev/ > /dev/null && echo "manifests render OK"   # CI gate

kubectl -n apt-mirror logs deploy/ubuntu24-mirror -f | grep "will be downloaded"
# expect 241.2 GiB — anything near 405 GiB means the pre-filter regressed

# hardlink proof: this is the whole point of choosing EFS over S3
kubectl -n apt-mirror exec deploy/ubuntu24-mirror -- \
  cp -al /var/spool/apt-mirror/mirror /var/spool/apt-mirror/snapshots/test
kubectl -n apt-mirror exec deploy/ubuntu24-mirror -- \
  du -sh /var/spool/apt-mirror/snapshots/test
```

---

## 8. Cost

| Item | /week |
|---|---|
| EFS 362 GB, One Zone, no backup | ~$14.87 |
| 1x t3.medium ON_DEMAND | ~$6.99 |
| **incremental total** | **~$21.86** |

Storage bills as a daily average of GB-month, so ramp-up week 1 comes in roughly
half that. ALB hosts ride the existing ALB, so only LCU applies. Scaling the
nodegroup to 0 when idle drops the $6.99.

---

## 9. Gotchas

1. **t3 CPU credits are the real risk.** Depleted credits throttle the instance
   to 0.2 vCPU. With `nthreads 10` plus the `gzip|awk` filter, that turns a ~3h
   noble sync into potentially 30h. Hence `cpu_credits = "unlimited"` on the
   launch template. Zero-cost alternative if you'd rather skip the launch
   template: drop `nthreads` to 3 and accept a slower sync.
2. **EFS is many-small-files slow.** Single-digit-millisecond metadata latency
   across 24k+ `.deb`/index files. IO-bound, not bandwidth-bound — CloudStack NFS
   managed 16 MB/s, expect similar. Budget hours, not minutes.
3. **One PV per access point.** Never point two PVCs at the same
   `volumeHandle`; they share a tree and will corrupt each other.
4. **`set -e` in the entrypoint** (added, not present in the original runbook)
   means a failed `apt-mirror` exits the container → CrashLoopBackOff with
   backoff up to 5 minutes. This is preferred over the runbook's silent 24-hour
   stall, but it does retry against upstream on persistent failure. Revert to the
   loop-only form if that is unwanted.
5. **Cluster-scoped objects stay manual.** Phase 2 never goes through CI.
6. **`terraform import`** — applying `terraform/eks` as-is creates duplicates
   (per the repo README). Import the new resources or scope the new file
   carefully.
7. **Inter-AZ egress.** Keep the nodegroup in 1a only; a 1c node on a 1a One Zone
   file system pays $0.01/GB.
8. **Static PV capacity is cosmetic.** EFS has no quota, so `kubectl describe pvc`
   will not reflect real usage — watch `du -sh` on the access point instead.
9. **Memory.** The existing t3.small nodes are already at 121–156% memory limit
   overcommit, and the runbook documents a prior `Exited 137` (OOM-kill) incident.
   This is precisely why a dedicated t3.medium nodegroup exists rather than
   reusing the lab nodes.

---

## 10. Open questions

- **Hostname / TLS:** new ACM certificate for `apt-*.azubisuccess.space`, or
  plain HTTP as the runbook used? Plain HTTP avoids cert work and matches
  existing clients.
- **Consumption path:** confirm consumers are in-cluster. If on-prem CloudStack
  UAT servers must also use this mirror, the on-prem NFS mirror still needs to
  exist — this plan does not replace it.
- **Snapshot automation:** manual `cp -al` (as today) or a CronJob?

---

## 11. Already done — do not repeat

- Built and pushed both images to `wazaglo/mirrors`.
- Consolidated EKS to a single NAT gateway (`nat-00e6…` in 1a): retargeted the
  1c private route, verified egress from 1c, deleted `nat-0975…`, released its
  EIP. Saved ~$7.56/week.
- The Docker Hub repos `wazaglo/ubuntu24-apt-mirror` and
  `wazaglo/debian12-apt-mirror` are empty; deleting them via API returned 403
  (the PAT lacks delete scope). Their local tags were removed. Delete them in the
  Hub UI if still wanted.
