# Runbook: secrets

Policy and threat model live in [SECURITY.md](../SECURITY.md). This is the
mechanics.

## Where secrets live

```
AWS SSM Parameter Store (SecureString)
        │  ClusterSecretStore/aws-ssm (IRSA: eso-controller-role)
        ▼
External Secrets Operator
        │  syncs every 5m
        ▼
Kubernetes Secret (monitoring/grafana-admin)
        │  referenced via secretKeyRef
        ▼
Grafana container env
```

Nothing sensitive is stored in this repository. `*.secret.yaml`,
`terraform.tfvars`, `*.pem`, `*.key` are gitignored and gitleaks blocks the PR.

## Reading the current value

```bash
aws ssm get-parameter --region us-west-1 \
  --name /eks-gitops/monitoring/grafana-admin-password --with-decryption
```

## Rotating

1. Generate a value:
   ```bash
   openssl rand -base64 24
   ```
2. Write it to SSM (value typed inline; never echoed to a file or a log you
   paste elsewhere):
   ```bash
   aws ssm put-parameter --region us-west-1 \
     --name /eks-gitops/monitoring/grafana-admin-password \
     --value '<new-value>' --type SecureString --overwrite
   ```
3. Force a sync and restart the consumer:
   ```bash
   kubectl -n monitoring annotate externalsecret grafana-admin force-sync=$(date +%s) --overwrite
   kubectl -n monitoring rollout restart deploy/grafana
   ```
4. **Grafana caveat:** changing the env var does not change an existing
   database's admin password. Reset it in-cluster:
   ```bash
   kubectl -n monitoring exec deploy/grafana -- \
     grafana cli --homepath /usr/share/grafana admin reset-admin-password '<new-value>'
   ```
5. Revoke the old credential anywhere else it existed (hPanel tokens, etc.).
6. Note the rotation in `CHANGELOG.md` (date + scope, never the value).

## Adding a new secret

1. `aws ssm put-parameter --type SecureString --overwrite`
2. Add an entry under `data:` in the `ExternalSecret`
   (`apps/monitoring/base/externalsecret.yaml`) pointing at the new key.
3. Consume via `secretKeyRef` — never `stringData` in a manifest.
4. `kubectl -n monitoring apply -f apps/monitoring/base/externalsecret.yaml`
   (or let CI do it) and restart the workload.

## If ESO breaks

```bash
kubectl -n external-secrets get pods
kubectl -n external-secrets logs deploy/external-secrets --tail=50
kubectl get clustersecretstore aws-ssm -o yaml
kubectl -n monitoring get externalsecret -o yaml   # status.conditions explains
```

A broken ESO pipeline leaves existing Secrets intact (it only syncs), so
workloads keep running with the last good value.
