# 0001 — Kustomize with base + per-environment overlays

**Status:** accepted

## Context

Multiple apps (nginx, the observability stack) must render differently per
environment (replica counts, retention windows, resource limits) without
duplicating manifests, and deployment must go through GitHub Actions.

## Decision

- One `base/` per app holding all manifests, then `overlays/{dev,prod}` that
  add only the deltas. `envs/<name>/kustomization.yaml` composes the overlays
  and is the **only** directory CI deploys.
- Helm is used for infrastructure the repo does not own (`infra/`), never for
  app workloads — so app state is reviewable YAML in git.
- Terraform mirrors the network/EKS layer (`terraform/`) and is deliberately
  **not** part of CI; it is planned and applied manually.

## Consequences

- `pr-validate` builds every overlay, so a broken overlay fails before merge.
- Environment differences are visible in a few lines of YAML rather than
  scattered across duplicated files.
- ConfigMap edits do not restart pods: a rollout restart is a manual step
  (documented in CONTRIBUTING.md) or a future reloader sidecar.
- Adding an environment means a new `envs/<name>/` root — no workflow change
  beyond the matrix.
