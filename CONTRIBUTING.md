# Contributing

## Workflow

1. Create a branch from `main`: `feat/<short-name>`, `fix/<short-name>`, `docs/<short-name>`.
2. Make focused commits using [Conventional Commits](https://www.conventionalcommits.org/):
   `feat:`, `fix:`, `docs:`, `chore:`, `ci:`, `refactor:`.
3. Open a pull request against `main`. Fill in the template. CI must be green:
   validate (kustomize build + YAML check), secret scan, terraform checks.
4. Get a review from the maintainer. Squash-merge.

## Local validation (run before pushing)

```bash
# All overlays must build
kubectl kustomize apps/nginx/overlays/dev > /dev/null
kubectl kustomize apps/monitoring/overlays/dev > /dev/null

# Rendered output sanity (mirrors CI)
kubectl kustomize envs/dev/ > /tmp/rendered.yaml
python3 - <<'EOF'
import yaml
docs = list(yaml.safe_load_all(open('/tmp/rendered.yaml')))
assert docs and all(
    isinstance(d, dict) and {'apiVersion', 'kind', 'metadata'} <= set(d)
    for d in docs
)
print(f'OK: {len(docs)} valid manifests')
EOF
```

Terraform (`terraform/`) is **not** part of CI — it mirrors live
infrastructure and is planned/applied manually by an admin. Validate it
locally when you touch it:

```bash
terraform -chdir=terraform/networking fmt -check && terraform -chdir=terraform/networking validate
terraform -chdir=terraform/eks fmt -check && terraform -chdir=terraform/eks validate
```

## Rules

- **Manifests:** kustomize only, one concern per file, `namespace:` always set on
  namespaced objects. No `:latest` images — pin tag or digest.
- **One site per file** under nginx `sites/` (`<fqdn>.conf`), registered in that
  folder's `kustomization.yaml` generator list.
- **Never commit secrets.** Use External Secrets + SSM (see SECURITY.md and
  `platform/external-secrets/`). If CI's secret scan fails, the PR is blocked.
- **Cluster-scoped objects** (`platform/`, Helm values in `infra/`) are applied
  manually, never added to CI-applied kustomizations. Note the manual command
  in your PR description.
- **Config changes need reloads:** ConfigMap edits don't restart pods — after CI
  applies, run `kubectl rollout restart` (or state why it's unnecessary).
- **Docs with behavior:** user-facing changes update `docs/` runbook or
  `CHANGELOG.md` (`Unreleased` section).
