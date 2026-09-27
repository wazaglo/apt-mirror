# Runbook: Loki

## CrashLoopBackOff

```bash
kubectl -n monitoring logs deploy/loki --tail=40 | grep -iE 'level=error'
```

Errors seen in this cluster and their fixes:

| Error | Cause | Fix |
|---|---|---|
| `field shared_store not found in type compactor.Config` | `compactor.shared_store` removed in Loki 3.x | delete the key |
| `compactor.delete-request-store should be configured when retention is enabled` | retention on, no delete store | `delete_request_store: s3` |
| `WebIdentityErr: … status code: 405 … MethodNotAllowed POST` on the S3 host | a custom `storage.s3.endpoint` makes dskit send **STS** calls to S3 | remove `endpoint:`; let the region default apply |
| `no ring members found` / pending forever | ring kvstore not ready | single-replica needs `replication_factor: 1` + `inmemory` kvstore (current config) |

The S3 endpoint trap is the nastiest: IRSA works perfectly (proved with an
`aws sts get-caller-identity` pod on the same ServiceAccount) while Loki still
fails, because dskit reuses the S3 endpoint for credential fetches.

## Not receiving logs from Alloy

```bash
kubectl -n monitoring logs -l app=alloy --tail=50 | grep -iE 'error|forbidden|retry'
```

Typical: `cannot get resource "pods/log"` — the ClusterRole is missing
`pods/log`. Apply it and give the tailers a moment:

```bash
kubectl apply -f platform/cluster-rbac.yaml
```

## Not receiving metrics in Prometheus

Alloy scrapes locally and remote-writes; Prometheus must have the receiver
enabled (`--web.enable-remote-write-receiver`):

```bash
kubectl -n monitoring exec deploy/prometheus -- \
  wget -q -O- 'http://localhost:9090/api/v1/query?query=count(node_uname_info)'
kubectl -n monitoring logs -l app=alloy --tail=30 | grep -i remote_write
```

## Chunks not landing in S3

```bash
aws s3 ls s3://azubi-logs/ --region us-west-1
kubectl -n monitoring logs deploy/loki --tail=100 | grep -iE 'uploading tables|error'
```

WAL/TSDB cache live on `emptyDir`, so a restart drops the last few seconds of
*unshipped* data. Shipped objects are durable. Replica count stays at 1 — a
second replica without a shared WAL would double-ingest.
