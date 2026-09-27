# Architecture

```
                       Internet
                          │  HTTPS (ACM *.azubisuccess.space)
                          ▼
              ┌───────────────────────────┐
              │  AWS ALB (internet-facing)│  sg-0306e5045f5a22414
              │  :80 → 301 → :443          │
              └─────────────┬─────────────┘
                            │ Host header preserved
              ┌─────────────▼─────────────┐
              │  nginx (nginx-demo, x2)   │  ClusterIP
              │  sites/*.conf:             │
              │   grafana.azubisuccess.space → grafana.monitoring:3000
              │   _default (ALB health)   │
              └─────────────┬─────────────┘
                            │
              ┌─────────────▼─────────────┐
              │  Grafana (monitoring, x2) │  ClusterIP :3000
              │  /var/lib/grafana          │
              └──────┬──────────────┬───────┘
                     │ EFS          │ provisions datasources
                     │ (fs-…::fsap-088c…, 472:472)
              ┌──────▼──────┐  ┌────▼─────────────┐
              │ EFS + CSI   │  │ Loki :3100        │
              └─────────────┘  │  TSDB → S3        │
                                │  azubi-logs       │
              ┌─────────────────▼──────────────────┐
              │ Alloy DaemonSet (x1 per node)      │
              │  - tails /var/log/pods (all pods)  │──► Loki
              │  - prometheus.exporter.unix (node) │──► remote_write
              └────────────────────────────────────┘
                     │
              ┌──────▼─────────────────────────────┐
              │ Prometheus :9090 (1 replica)       │
              │  scrapes: self, blackbox            │
              └──────┬─────────────────────────────┘
                     │ probes /probe
              ┌──────▼──────────┐
              │ blackbox :9115  │──► external + in-cluster targets
              └─────────────────┘
```

## Design rules

| Concern | Owner | Applied by |
|---|---|---|
| Apps + configs (namespaced) | `apps/**` | CI (GitHub Actions, OIDC) |
| Cluster-wide objects, storage, CRDs | `platform/**` | manual `kubectl apply` |
| Helm releases (ALB controller, EFS CSI, ESO) | `infra/**` | manual `helm upgrade --install` |
| VPC / EKS / IAM as code | `terraform/**` | manual `terraform plan` + `apply` |
| Secrets | SSM Parameter Store | External Secrets Operator → K8s Secret |

**Why the split:** the CI IAM role is deliberately namespace-scoped, so a
compromised workflow cannot create ClusterRoles, StorageClasses, or webhooks.
Anything cluster-scoped is an explicit human action. See
[SECURITY.md](../SECURITY.md).

## Traffic path in one paragraph

A user hits `https://grafana.azubisuccess.space`. DNS (Hostinger) CNAMEs to the
ALB. The ALB terminates TLS with the ACM wildcard cert, sees a catch-all
Ingress rule, and forwards to nginx pods with the original `Host`. nginx
matches the `server_name` block and proxies to the Grafana Service in
`monitoring`, which load-balances across Grafana pods sharing the EFS volume.
TLS never re-encrypts inside the cluster (nginx speaks plain HTTP), which is
normal for this pattern — traffic between ALB and pods is VPC-internal.

## Storage

`efs-sc` (provisioner `efs.csi.aws.com`, `efs-ap` mode) with a **static** PV
bound to access point `fsap-088c8c16707025698` (POSIX `472:472`, root
`/grafana`). Static rather than dynamic: one deterministic volume for Grafana
instead of an access point per PVC. `reclaimPolicy: Retain` everywhere —
deleting the PV will not delete data.

Loki ships chunks and indexes to S3 (`azubi-logs`) and keeps only the WAL +
TSDB cache on `emptyDir`. A pod restart can lose the last few seconds of
buffered logs; chunks already shipped are safe. Prometheus keeps 6h (dev) /
24h (prod) of metrics on `emptyDir` for the same reason.

## Scaling

`t3.small` caps at 11 pods per node. The node group (`ng-eks`) runs 5 nodes
now. `t3.medium` is unavailable on this account (Free Tier restriction), so
capacity growth is node count only. Install Karpenter if pods start queueing
again — it would replace manual `update-nodegroup-config` calls.

## Deliberate simplifications

* Grafana runs 2 replicas on **one** SQLite database over NFS — fine for a
  lab, can hit "database is locked" under concurrent writes. One replica or an
  external Postgres for anything real.
* Prometheus and Loki are single-writer, no redundancy.
* TLS is terminated at the ALB; nothing in-cluster is mTLS.
