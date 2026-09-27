# Runbook: Grafana

## Login fails / password "invalid"

Credentials come from SSM via External Secrets. Check what the cluster
actually has (do NOT assume the manifest value):

```bash
aws ssm get-parameter --region us-west-1 \
  --name /eks-gitops/monitoring/grafana-admin-password --with-decryption
kubectl -n monitoring get externalsecret grafana-admin -o jsonpath='{.status.conditions}'; echo
kubectl -n monitoring get secret grafana-admin -o jsonpath='{.data.admin-password}' | base64 -d; echo
```

If the Secret is empty, the ESO controller cannot reach SSM:

```bash
kubectl -n external-secrets logs deploy/external-secrets --tail=50
kubectl get clustersecretstore aws-ssm -o yaml
```

**Known trap:** `GF_SECURITY_ADMIN_PASSWORD` only applies to a **fresh**
database. If the volume already has a `grafana.db`, the env var is ignored.
The current DB was created with the default `admin/admin`; we reset it with:

```bash
kubectl -n monitoring exec deploy/grafana -- \
  grafana cli --homepath /usr/share/grafana admin reset-admin-password '<new-password>'
```

## CrashLoopBackOff or "database is locked"

Cause: two replicas writing one SQLite file over NFS. Symptoms in
`kubectl -n monitoring logs deploy/grafana` include
`failed to open database: database is locked` or `SQLITE_BUSY`.

```bash
kubectl -n monitoring get pods -l app=grafana
kubectl -n monitoring logs deploy/grafana --tail=50 | grep -iE 'lock|sqlite|error'
```

Fixes, in order of preference:

1. Scale to one replica (what the `prod` overlay does):
   `kubectl -n monitoring scale deploy/grafana --replicas=1`
2. Point Grafana at an external Postgres and keep 2+ replicas (real fix).
3. Swap `emptyDir`/NFS for a `ReadWriteOnce` EBS volume — but then the two
   replicas can't both mount it, so this only pairs with option 2.

## Datasources missing

Datasources are provisioned from `grafana-datasources.yaml`. A ConfigMap edit
does not restart pods:

```bash
kubectl -n monitoring rollout restart deploy/grafana
kubectl -n monitoring exec deploy/grafana -- \
  wget -q -O- --header="Authorization: Basic $(printf 'admin:%s' "$PW" | base64)" \
  http://localhost:3000/api/datasources
```

## Data directory is empty / volume not bound

```bash
kubectl -n monitoring get pvc grafana-data      # must be Bound
kubectl get pv grafana-efs
kubectl -n monitoring exec deploy/grafana -- ls -la /var/lib/grafana
```

If the pod is stuck with `FailedMount … DeadlineExceeded`, the EFS mount
targets can't reach the node security group — see
[efs.md](efs.md).
