# Runbook: CI pipeline

```bash
gh run list --repo wazaglo/apt-mirror --limit 5
gh run view <run-id> --repo wazaglo/apt-mirror --log-failed
```

## Which job failed?

| Job | Meaning | Fix |
|---|---|---|
| `Validate manifests (no cluster)` | rendering/YAML problem, nothing touched the cluster | fix manifests, re-push |
| `pr-validate` | overlay doesn't build, `:latest` image, or secret detected | see message |
| `Apply manifests to EKS` | RBAC or apply error against the real cluster | usually missing CRD/ClusterRole |
| `secret-scan` | gitleaks found a credential | rotate it, then fix the file (SECURITY.md) |

## Traps already hit here (do not repeat)

0. **A new RBAC object in `envs/` kills the whole deploy.** `kubectl diff` runs
   before apply and dry-run-creates each object in isolation. A RoleBinding
   whose `roleRef` Role does not exist yet is rejected, diff exits 2, and the
   job dies *before applying anything* — so a change that looks additive
   silently ships nothing. Bootstrap RBAC belongs in `platform/`, applied by
   hand.
1. **A new directory under `apps/` deploys nothing, and CI stays green.**
   Kustomize is not a recursive walker. Verify with
   `kubectl kustomize envs/dev/ | grep -c '^kind:'`.
2. **`kustomize build` and `--dry-run=client` do not validate schema.** An
   invented field (`containerName` on `ContainerPort`) passed both and was
   rejected only by `--dry-run=server`. Use it whenever the API server is
   involved.
3. **A deploy is triggered only by `apps/**`, `envs/**`, or the workflow
   file.** A commit touching only `platform/`, `infra/` or `terraform/` will not
   run the workflow at all. That is correct — CI cannot apply those paths — but
   it means you must dispatch manually to test:
   `gh workflow run deploy.yml -f environment=dev`.

1. **`kubectl apply --dry-run=client` needs an apiserver.** Even with
   `--validate=false` it tries discovery on `localhost:8080` and dies. The
   validate job therefore does `kustomize build` + a YAML sanity check; the
   real dry-run lives in the deploy job which has cluster access.
2. **`kubectl diff` exits 1 when there are changes.** The runner's shell runs
   with `-e`, so the step aborted before `$?` was read. That step needs
   `set +e` around the diff.
3. **Don't wait on `deployment --all` across namespaces** — a namespace with
   no deployments returns exit 1 and fails the job. Wait on the one
   deployment you care about.
4. **Generated ConfigMaps have no namespace.** `configMapGenerator` output
   lands in `default` unless a patch pins it, which breaks any Deployment
   mounting it in a real namespace.
5. **Cluster-scoped objects break the deploy job.** The CI role is
   namespace-scoped on purpose. `platform/` is never referenced from `envs/`.

## Nothing was applied but CI is green

Check that your change is actually reachable from an environment root:

```bash
kubectl kustomize envs/dev/ | grep -c '^kind:'   # objects CI would apply
git diff --stat main...HEAD
```

Files under `platform/` or `infra/` are **never** applied by CI — that's
intentional. Run the manual command from the PR description and record the
output in the PR.
