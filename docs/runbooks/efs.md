# Runbook: EFS

## Facts for this cluster

| | |
|---|---|
| Filesystem | `fs-0ddb254be08c6267a` (encrypted, elastic throughput) |
| Mount DNS | `fs-0ddb254be08c6267a.efs.us-west-1.amazonaws.com:/` |
| Mount targets | one per AZ: `subnet-035bd6…` (1a), `subnet-06a767…` (1c) |
| Access point | `fsap-088c8c16707025698` — POSIX `472:472`, root `/grafana`, perms 700 |
| StorageClass | `efs-sc` (provisioner `efs.csi.aws.com`, mode `efs-ap`) |
| PV | `grafana-efs` (static, `Retain`, 5Gi, RWX) |

**You mount EFS by DNS name, never by IP.** The IPs on the mount-target
network interfaces are internal plumbing.

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
