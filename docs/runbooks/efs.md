# Runbook: EFS

## Facts for this cluster

Two filesystems, and they are not interchangeable.

### `archcloud-mirror-efs` — the package mirror

| | |
|---|---|
| Filesystem | `fs-0b0491ead2bac1c8c` (Standard, encrypted, elastic, generalPurpose) |
| Mount targets | 2 — `us-west-1a` and `us-west-1c` |
| Backups | **DISABLED** — a restore is an `apt-mirror` re-run |
| AP (Debian) | `fsap-020b79f4588c2d482` — POSIX `1000:1000`, root `/mirrors/debian/12`, perms 755 |
| AP (Ubuntu) | `fsap-02586212ea002c468` — POSIX `1000:1000`, root `/mirrors/ubuntu/24.04`, perms 755 |
| StorageClass | `efs-mirror-sc` |
| PVs | `debian12-mirror-efs`, `ubuntu24-mirror-efs` (both static, `Retain`, RWX) |

Size is ~119 GiB Debian + ~259 GiB Ubuntu, plus whatever the snapshots pin.

**The access point forces POSIX 1000:1000 on every request regardless of the
client uid.** That is why the sync containers run as root and the serving
container runs as uid 101 and still reads everything.

### `eks-shared-efs` — observability state

| | |
|---|---|
| Filesystem | `fs-0ddb254be08c6267a` (encrypted, elastic throughput) |
| Mount DNS | `fs-0ddb254be08c6267a.efs.us-west-1.amazonaws.com:/` |
| Mount targets | one per AZ: `subnet-035bd6…` (1a), `subnet-06a767…` (1c) |
| Access points | `fsap-088c8c16707025698` POSIX `472:472` root `/grafana` 700; `fsap-012a38be930c8a207` POSIX `1000:1000` root `/prometheus` |
| StorageClass | `efs-sc` |
| PVs | `grafana-efs` (5Gi), `prometheus-efs` (10Gi), both static `Retain` |
| Backups | **ENABLED** — holds the Grafana database and Prometheus TSDB, which cannot be regenerated |

**You mount EFS by DNS name, never by IP.** The IPs on the mount-target
network interfaces are internal plumbing.

## The mirror PVC will not bind — read this before debugging the network

Dynamic provisioning cannot work on this cluster. The EFS CSI driver is
EKS-addon-managed and authenticates through addon-owned **Pod Identity**
associations, which take precedence over the service account's IRSA
annotation. The addon role lacks `DescribeAccessPoints` and
`CreateAccessPoint`:

```
AccessDeniedException: …AmazonEKSPodIdentityAmazonEFSCSIDriver-efs-csi-controller-sa-Rol…
  is not authorized to perform: elasticfilesystem:DescribeAccessPoints
```

The PVC then sits `Pending` forever with no useful event beyond a periodic
`ProvisioningFailed`. Correctly-permissioned IRSA role
(`efs-csi-driver-role` + `AmazonEFSCSIDriverPolicy`) exists and is never used.

The mirror therefore uses **static PVs with an explicit `volumeHandle`**, which
never touches the EFS control plane. See
[ADR-0005](../adr/0005-static-pv-per-efs-access-point.md).

If you add a distro: create an access point, write a PV in `platform/`, apply it
by hand, and pre-bind the PVC with `volumeName`. Never point two PVCs at one
`volumeHandle` — they share a tree and corrupt each other.

## Checking progress on a long sync

`SizeInBytes` from the EFS API is a **daily average refreshed roughly every 15
minutes**, so it looks flat between updates and will convince you a sync has
stalled when it has not. Read the process I/O instead:

```bash
kubectl -n mirrors exec deploy/ubuntu24-mirror-sync -- sh -c \
  'for p in /proc/[0-9]*; do c=$(tr "\0" " " < $p/cmdline 2>/dev/null);
   case "$c" in *apt-mirror*) grep ^wchar $p/io;; esac; done'
```

`wchar` is bytes written by the process, and the `wget` children each show
their own. This is the only reliable progress signal.

## Pod stuck in `FailedMount` / `DeadlineExceeded`

Almost always the security group, not Kubernetes:

```bash
kubectl -n monitoring describe pod <pod> | grep -A3 FailedMount
aws efs describe-mount-target-security-groups --region us-west-1 --mount-target-id fsmt-05a665e0518386d0d
```

The NFS mount targets must accept TCP **2049** from the node/cluster security
group. This cluster needed the rule added explicitly:

```bash
aws ec2 authorize-security-group-ingress --region us-west-1 \
  --group-id sg-0598a68f03d5d2a39 --protocol tcp --port 2049 \
  --source-group sg-0306e5045f5a22414
```

## Permissions wrong (pod runs as 472, gets EACCES)

An access point without a POSIX user leaves the directory root-owned:

```bash
aws efs describe-access-points --region us-west-1 --access-point-id fsap-088c8c16707025698 \
  --query 'AccessPoints[0].{Posix:PosixUser,Root:RootDirectory}'
```

`PosixUser` must be `{Uid: 472, Gid: 472}` and `CreationInfo` must own the
directory. Create new ones with:

```bash
aws efs create-access-point --region us-west-1 \
  --file-system-id fs-0ddb254be08c6267a \
  --posix-user '{"Uid":472,"Gid":472}' \
  --root-directory '{"Path":"/grafana","CreationInfo":{"OwnerUid":472,"OwnerGid":472,"Permissions":"700"}}'
```

## CSI driver missing

```bash
helm list -n kube-system | grep efs
kubectl -n kube-system get pods -l app.kubernetes.io/name=aws-efs-csi-driver
```

If Helm refuses to install because objects "exist and cannot be imported",
leftovers from a previous partial install need adopting: label them
`app.kubernetes.io/managed-by=Helm` and annotate them with
`meta.helm.sh/release-name` / `-namespace`, then retry
(`docs/ACTIONS.md` has the exact commands).

## Recreating storage

`platform/` objects are manual:

```bash
kubectl apply -f platform/storageclass.yaml
kubectl apply -f platform/pv-grafana.yaml
```

`reclaimPolicy: Retain` means deleting the PV will not delete your data.
