# eks-gitops

Production-shaped EKS platform, deployed from git. Kubernetes manifests for
apps, GitHub Actions for delivery, AWS-native storage, DNS, TLS, and a full
observability stack — with the cluster-wide surfaces deliberately kept out of
CI's reach.

**Cluster:** `eks-lab` (EKS 1.36) · **Region:** `us-west-1` · **Account:** `195675606509`
**Live URL:** <https://grafana.azubisuccess.space>

---

## What runs here

| Component | Where | Storage | Applied by |
|---|---|---|---|
| nginx (multi-site reverse proxy) | `nginx-demo` | — | CI |
| Grafana ×2 | `monitoring` | EFS (`fs-0ddb…`, AP 472:472) | CI |
| Prometheus | `monitoring` | EFS (`fs-0ddb…`, AP 1000:1000) | CI |
| Loki | `monitoring` | S3 `azubi-logs` | CI |
| blackbox exporter | `monitoring` | `emptyDir` | CI |
| Alloy DaemonSet (logs + node metrics) | `monitoring` | `emptyDir` | CI |
| ALB controller, EFS CSI, External Secrets, external-dns | `kube-system`, `external-secrets`, `external-dns` | — | Helm (manual) |
| KEDA (nightly scale-to-zero) | `keda` | — | Helm (manual) |
| Node group scheduler (Lambda + EventBridge) | — | — | AWS (manual) |
| ClusterRoles, StorageClass, PVs, ClusterSecretStore | — | — | `kubectl` (manual) |
| VPC, EKS, IAM | — | — | Terraform (manual) |

Traffic: `DNS → ALB (TLS) → nginx (Host-based) → app Service`. Logs:
`Alloy → Loki → S3`. Metrics: `Alloy → remote_write → Prometheus → Grafana`.

**Compute is off every night.** KEDA scales all workloads to 0 outside
10:05–17:54 UTC and a Lambda terminates the node group at 17:58, relaunching at
10:00. The site returns 502 while the nodes are gone. Full details, override
procedure and troubleshooting: [docs/runbooks/cost-scheduler.md](docs/runbooks/cost-scheduler.md).

## Repository layout

```
apps/                      # everything CI deploys (namespaced only)
  nginx/base/              #   + sites/*.conf, one file per FQDN
    overlays/{dev,prod}/
  monitoring/base/         #   grafana, loki, alloy, prometheus, blackbox
    overlays/{dev,prod}/
  alb/                     #   ALB controller ServiceAccount (IRSA)
envs/{dev,prod}/           # environment roots — the CI deploy target
platform/                  # cluster-scoped, applied MANUALLY
infra/                     # Helm releases + the node scheduler Lambda
  keda/                    #   KEDA values + infra ScaledObjects (manual)
  scheduler/               #   Lambda: node group off 17:58 / on 10:00 UTC
terraform/{networking,eks} # infra as code, run manually, NOT in CI
docs/                      # architecture, onboarding, runbooks, ADRs, ACTIONS
bootstrap → platform/      # CI deploy RBAC (moved)
```

`apps/**` and `envs/**` are the only paths that reach the cluster from CI.

## Quick start

```bash
git clone https://github.com/wazaglo/eks-gitops.git && cd eks-gitops
kubectl kustomize envs/dev/ > /dev/null && echo "manifests render OK"

aws eks update-kubeconfig --region us-west-1 --name eks-lab
kubectl get nodes
```

Deploying, validating, and the full onboarding path: **[docs/onboarding.md](docs/onboarding.md)**.

## How deployment works

1. Branch off `main`, edit under `apps/`.
2. PR → `pr-validate` builds every overlay, rejects `:latest` images; `secret-scan` runs gitleaks.
3. Review + merge to `main` → `deploy` assumes the OIDC role and applies `envs/dev/`.
4. Prod is a separate overlay, deployed only on manual dispatch.

The CI role can only manage namespaced workloads. Cluster-scoped and Helm-managed
objects are applied by a human — a compromised workflow cannot widen its own
permissions. See [ADR-0004](docs/adr/0004-push-gitops-least-privilege.md) and [SECURITY.md](SECURITY.md).

## Secrets

No credentials in git. Values live in **SSM Parameter Store** and reach the
cluster through the **External Secrets Operator**. Reading, rotating, and
adding secrets: [docs/runbooks/secrets.md](docs/runbooks/secrets.md).

## Adding a site (one FQDN → one backend)

```bash
# 1. write the server block
cat > apps/nginx/base/sites/api.azubisuccess.space.conf <<'EOF'
server {
  listen 80;
  server_name api.azubisuccess.space;
  location / {
    proxy_pass http://api.default.svc.cluster.local:8080;
    proxy_set_header Host $host;
  }
}
EOF

# 2. register it in the generator list
#    apps/nginx/base/kustomization.yaml -> configMapGenerator.files

# 3. point DNS at the ALB, then push and reload nginx
kubectl -n nginx-demo rollout restart deploy/nginx
```

`apps/nginx/base/sites/_default.conf` must keep serving `/` — it is the ALB
health-check target. Breaking it fails every target at once.

## Operations

| Need | Go to |
|---|---|
| Symptom → fix | [docs/runbooks/README.md](docs/runbooks/README.md) |
| Nightly schedule, manual override, cost | [docs/runbooks/cost-scheduler.md](docs/runbooks/cost-scheduler.md) |
| What was actually done, with commands | [docs/ACTIONS.md](docs/ACTIONS.md) |
| What is installed / next | [docs/ROADMAP.md](docs/ROADMAP.md) |
| How it fits together | [docs/architecture.md](docs/architecture.md) |
| Why we chose this | [docs/adr/](docs/adr/) |
| Recent changes | [CHANGELOG.md](CHANGELOG.md) |

## Contributing

Branch `feat/*`, Conventional Commits, get a review before merge.
Local validation commands: [CONTRIBUTING.md](CONTRIBUTING.md).

## Known limitations (deliberate)

- Grafana runs 2 replicas on one SQLite file over NFS — can hit
  "database is locked"; prod overlay pins 1 replica, real fix is external Postgres.
- Loki and Prometheus are single-writer with `emptyDir` WAL/cache: a restart
  drops the last few seconds of unshipped data.
- TLS terminates at the ALB; in-cluster traffic is plain HTTP.
- EFS mounts are not using `encryptInTransit`; Grafana has no
  `GF_SECURITY_SECRET_KEY`; cluster Secrets are not KMS-encrypted.
- No alerting yet (Prometheus has no Alertmanager rules) and no alerting
  receiver wired.
- `terraform/` mirrors live infrastructure but is not adopted with
  `terraform import` — applying it as-is would create duplicates.

## License

[MIT](LICENSE)
