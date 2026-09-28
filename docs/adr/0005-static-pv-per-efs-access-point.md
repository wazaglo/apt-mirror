# 0005 — Static PV per EFS access point, not dynamic provisioning

**Status:** accepted

## Context

The mirror stores its data on EFS and mounts it into two very different
consumers: the sync Deployment, which writes, and the serving Deployment, which
only reads. The obvious configuration is a StorageClass with
`provisioningMode: efs-ap` and let the CSI driver create the target on demand.

That configuration cannot work on this cluster.

## Decision

Bind every mirror PVC to a **static** PersistentVolume with an explicit
`volumeHandle` of `<file-system-id>::<access-point-id>`, one PV per access
point, and have the PVC pre-bind with `volumeName`.

## Why

The EFS CSI driver is installed as an EKS addon and authenticates through
addon-owned EKS Pod Identity associations. Pod Identity takes precedence over
the service account's IRSA annotation, so the addon-generated role is the one
actually used — and it lacks `elasticfilesystem:DescribeAccessPoints` and
`elasticfilesystem:CreateAccessPoint`:

    AccessDeniedException: User: …assumed-role/
      AmazonEKSPodIdentityAmazonEFSCSIDriver-efs-csi-controller-sa-Rol/…
      is not authorized to perform: elasticfilesystem:DescribeAccessPoints

Every dynamic provisioning attempt fails with
`Unauthenticated desc = Access Denied` and the PVC stays `Pending` forever. A
correctly-permissioned IRSA role (`efs-csi-driver-role`, with
`AmazonEFSCSIDriverPolicy` attached) exists in the account and is never used.

A static PV never reaches the EFS control plane. The `volumeHandle` is resolved
at mount time, so provisioning needs no IAM beyond the node's NFS permissions.

## Consequences

- The existing `grafana-efs` and `prometheus-efs` static PVs are the same
  pattern and were never affected. That is why they bind and the mirror's
  dynamic PVC did not.
- The StorageClass becomes decorative for a statically bound PVC: it is read
  only to match `storageClassName`. Any `accessPointId` in it is inert. It is
  kept for documentation, but changing it will not move data.
- `spec.capacity.storage` is cosmetic — EFS has no quota — so PVC-reported
  capacity never reflects real usage. `du -sh` on the mount is the only
  honest number.
- One PV per access point, **never two PVCs against one `volumeHandle`**: they
  share a single tree and will corrupt each other's writes.
- Adding a distro means adding an access point and a PV, not a StorageClass.
  Both are cluster-scoped, so both are applied by hand from `platform/`.
