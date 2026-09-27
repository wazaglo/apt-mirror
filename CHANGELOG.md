# Changelog

All notable changes to this project are documented here, newest first.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added
- Nightly cost schedule: KEDA cron ScaledObjects scale every workload to 0
  outside 10:05–17:54 UTC; Lambda + EventBridge (`infra/scheduler/`) terminates
  the node group at 17:58 and relaunches at 10:00
- Prometheus moved from `emptyDir` to EFS (access point `fsap-012a38be930c8a207`,
  POSIX 1000:1000, `/prometheus`) so the TSDB survives node termination;
  `runAsUser/Group/fsGroup: 1000` + 60s termination grace for the WAL flush
- `deploy.yml` off-hours guard: applies manifests at night (keeping git in sync
  with the cluster) but skips the rollout wait, which would hang with no nodes
- Runbook `docs/runbooks/cost-scheduler.md` (verify, override, troubleshoot)
- Production repo restructure: `apps/` + overlays, `platform/`, `infra/`, `docs/`
- Community health files: LICENSE (MIT), SECURITY.md, CONTRIBUTING.md,
  SUPPORT.md, PR/issue templates, Dependabot
- External Secrets strategy (SSM) replacing in-repo secrets
- Image pinning by digest, `pr-validate` + `secret-scan` CI gates

### Changed
- Deploy role RBAC extended for `external-secrets.io` and `keda.sh`
  ScaledObjects (namespaced, declarative) — without this, CI deploys failed

### Removed
- CODEOWNERS (no longer enforcing review ownership)

### Security
- Grafana admin password rotation (previous value was committed in plaintext)
- Hostinger API token used for DNS flagged for rotation

## [0.5.0] - 2026-09-27

### Added
- Observability: Alloy DaemonSet (all container logs → Loki), Prometheus,
  blackbox probes, Grafana Loki + Prometheus datasources
- Loki on S3 (`azubi-logs`, TSDB, 31d retention) with IRSA role
- EFS CSI driver + Grafana x2 on shared EFS in `monitoring`
- Nginx sites-per-FQDN (`sites/*.conf` via configMapGenerator)
- HTTPS on ALB (ACM wildcard `*.azubisuccess.space`, ssl-redirect)
- DNS: `grafana.azubisuccess.space` CNAME → ALB (Hostinger API)
- Terraform copies: `terraform/networking/`, `terraform/eks/`

### Fixed
- NodeCreationFailure: node IAM role policies, node group rebuilt (t3.small)
- CI pipeline: offline validate, diff errexit, generated ConfigMap namespace
- Loki compactor/retention/S3-endpoint config errors
- EFS mount SG (TCP 2049), nodes scaled 2 → 5 (t3.small, Free Tier limit)

## [0.1.0] - 2026-09-27

### Added
- Initial EKS GitOps repo: nginx via Kustomize + GitHub Actions OIDC deploy
- ALB controller (IRSA) + ServiceAccount, subnet discovery tags
- Cluster RBAC for CI deploy role
