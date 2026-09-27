# 0003 — EFS for Grafana data, static PV bound to an access point

**Status:** accepted

## Context

Grafana needs a POSIX filesystem with working file locking (its state is
`grafana.db`, SQLite). Nodes span two AZs, and cheap instance types cap pod
counts, so the data must follow the pod across nodes and AZs.

## Decision

EFS (`fs-0ddb254be08c6267a`) with:

- an **access point** enforcing POSIX `472:472` (Grafana's uid/gid) and
  auto-creating `/grafana` with `CreationInfo` — otherwise the directory is
  root-owned and Grafana cannot write its database;
- a **static** PV (`volumeHandle: <fs-id>::<ap-id>`) rather than dynamic
  provisioning, because we want exactly one access point for one application,
  not a spread of PVCs;
- `reclaimPolicy: Retain` so deleting the PV never deletes data.

S3 was rejected for the live database: object storage has no locking and no
random writes, so SQLite cannot run on it. S3 is the right place for *backups*
of dashboard JSON, and is in fact what Loki uses for its own chunks.

## Consequences

- Grafana is not node- or AZ-bound; `ReadWriteMany` works.
- NFS is slower than EBS for small writes, and the traffic is **not** TLS
  (no `encryptInTransit` mount option set) — acceptable inside the VPC, but
  the gap is recorded in this ADR.
- Two Grafana replicas sharing one SQLite file can hit "database is locked".
  The `prod` overlay pins one replica; the dev overlay keeps two for
  demonstration purposes. Moving to external Postgres is the real fix.
