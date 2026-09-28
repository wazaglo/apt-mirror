# 0004 — Push-based GitOps with a namespace-scoped CI role

**Status:** accepted

## Context

Deploys must be reproducible from git, and the credential available to
GitHub Actions is a standing risk: whatever it can do, a compromised workflow
can do.

## Decision

- **Push-based**: GitHub Actions assumes an OIDC role
  (`apt-mirror-github-actions` → `apt-mirror-deployers`) and applies
  `envs/dev/`. No cluster-side polling component to operate.
- **Least privilege by construction**: the `apt-mirror-deployer` ClusterRole
  (`platform/bootstrap-rbac.yaml`) grants namespaced verbs only. It cannot
  create ClusterRoles, StorageClasses, PVs, or webhook configurations.
- **Cluster-scoped and Helm-managed things are manual**: `platform/`
  (RBAC, storage, ClusterSecretStore) and `infra/` (ALB controller, EFS CSI,
  External Secrets) are applied by a human, and the PR must state the command.
- **Secrets never enter git**: SSM Parameter Store is the source of truth and
  External Secrets syncs it into the cluster.

## Consequences

- The pipeline cannot escalate its own permissions — the main security
  property we wanted.
- Some changes need two people-shaped steps (merge, then manual apply). This
  is the accepted cost; ArgoCD would remove the second step but adds a
  cluster-side component with its own RBAC and availability concerns.
- Drift is possible between a manual apply and git. Mitigated by keeping
  manual objects in `platform/`/`infra/` with the exact command documented.
- We deliberately did **not** rewrite git history to purge a committed
  secret: the value was pushed and therefore must be considered public, so
  rotation (not rewriting) is the actual fix.
