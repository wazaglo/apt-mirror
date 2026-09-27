# Security Policy

## Scope

This repository manages production-adjacent AWS/EKS infrastructure
(`eks-lab`, VPC, DNS for `azubisuccess.space`, observability). Treat every
file here as security-sensitive by default.

## Rules

1. **No secrets in git — ever.** Credentials live in AWS SSM Parameter Store
   (SecureString) and reach the cluster via External Secrets Operator.
   `*.secret.yaml`, `terraform.tfvars`, `*.pem`, `*.key` are gitignored and
   CI-scanned with gitleaks. If you paste a secret into a commit, treat it as
   compromised (see Rotation below).
2. **Least privilege.** The GitHub deploy role (`eks-gitops-deployers`) can
   manage namespaced workloads only. Cluster-scoped objects (`platform/`,
   StorageClasses, PVs, ClusterRoles, Helm releases) are applied manually by
   a cluster admin and never by CI — a compromised workflow must not be able
   to widen its own permissions.
3. **Signed, reviewed changes.** All changes land on `main` via pull request
   with at least one review. Direct pushes are for automation
   fixes only and should be the exception.
4. **Pinned supply chain.** Container images are pinned by digest, Helm charts
   by version, Terraform providers by lock file. `latest` tags are forbidden
   in `apps/` and `platform/`.

## Known past exposures (already handled)

These values appeared in git history or chat and must be considered public.
They are rotated, not trusted:

| Secret | Status |
|---|---|
| Grafana admin password (`8geml84…`) | Rotated after External Secrets cutover |
| Hostinger API token (`nyEo…`, shared in chat, rejected 401) | Revoked — never worked |
| Hostinger API token (`iXbn…`, shared in chat, used for DNS) | **Rotate in hPanel → Profile → API** |

Neither token was ever committed: the repository only ever contained the 4-char
prefixes above. Verified across full history and via `gh secret list` (which holds
only `AWS_DEPLOY_ROLE_ARN`). Rotation is still required because both values were
shared in chat, which is outside this repository's history.

## Rotation checklist

- [ ] Generate the new value (e.g. `openssl rand -base64 24`)
- [ ] Write it to SSM (`aws ssm put-parameter --type SecureString --overwrite`)
- [ ] Restart affected workloads (`kubectl rollout restart`)
- [ ] Revoke/delete the old credential at its source (hPanel, IdP, console)
- [ ] Record the rotation in CHANGELOG.md (date + scope, never the value)

## Reporting a vulnerability

Do not open a public issue for security problems. Contact the maintainer
directly (see SUPPORT.md) with: affected file or component,
impact, and reproduction steps. Expect acknowledgement within 48 hours.
