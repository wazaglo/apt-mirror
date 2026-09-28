# Onboarding

## Prerequisites

`aws` (v2, configured for the `personal` profile), `kubectl`, `gh` (authenticated),
`terraform`. No Helm unless you are touching `infra/`.

## Clone and validate

```bash
git clone https://github.com/wazaglo/apt-mirror.git && cd apt-mirror
kubectl kustomize envs/dev/  > /dev/null && echo "dev renders"
kubectl kustomize envs/prod/ > /dev/null && echo "prod renders"
```

Both must render. Kustomize does no schema validation, so this catches
assembly errors only — not a field the API server will reject.

## Point kubectl at the cluster

```bash
aws eks update-kubeconfig --region us-west-1 --name eks-lab
kubectl get nodes                       # 5 nodes
kubectl -n mirrors get deploy,pod,svc   # the mirror
```

## Know what CI does and does not do

| Path | Who applies it |
|---|---|
| `apps/**`, `envs/**` | **CI**, on push to `main` |
| `platform/**` | **You**, by hand |
| `infra/**` (Helm) | **You**, by hand |
| `terraform/**` | **You**, by hand, after `terraform plan` |
| Secrets | Never in git — SSM, synced by External Secrets |

The split is a security property, not a preference: the CI role
(`apt-mirror-deployer`) holds namespaced verbs only and cannot create
ClusterRoles, StorageClasses or PVs, so a compromised workflow cannot widen its
own access. See
[ADR-0004](adr/0004-push-gitops-least-privilege.md).

The cost: a change under `platform/` or `infra/` is a two-step change. Say so in
the PR and include the exact command.

### The manual objects, and how to apply them

```bash
kubectl apply -f platform/                    # PVs, deploy ClusterRole, trigger RBAC
kubectl apply -f platform/pv-ubuntu24-mirror.yaml   # or just the one you changed
```

`platform/` is safe to apply wholesale; it is idempotent and the CI role already
holds everything in it.

## Deploy

Push to `main`. CI renders `envs/dev/`, diffs, and applies.

```bash
gh run list --repo wazaglo/apt-mirror --limit 3   # did it apply?
gh run view <id> --repo wazaglo/apt-mirror --log-failed
```

**CI is triggered only by `apps/**`, `envs/**`, or changes to the deploy
workflow itself.** A commit that touches only `platform/`, `infra/` or
`terraform/` will not trigger a run — which is correct, because CI cannot apply
those paths.

## Verify

```bash
# the mirror
curl -sSI https://debian-mirror.azubisuccess.space/debian/dists/bookworm/Release
curl -sSI https://ubuntu-mirror.azubisuccess.space/ubuntu/dists/noble/Release

# observability
curl -sS https://grafana.azubisuccess.space/api/health

# capacity — this is the number that bites
kubectl get pods -A --no-headers | grep -vcE 'Completed|Error'   # must stay under 55
```

`/` on a mirror host returns 404 on purpose. Check a real archive path, not the
root.

A `dists/` 404 while a sync is in progress is normal — see
[mirror.md](mirror.md#first-sync-expect-404s-until-it-finishes).

## Grafana credentials

Held in SSM, not in git:

```bash
aws ssm get-parameter --name /eks-gitops/monitoring/grafana-admin-password \
  --with-decryption --query Parameter.Value --output text
```

The `/eks-gitops/` prefix is intentional and does **not** follow the repository
name — it is a live AWS resource, and renaming it would mean rotating a working
secret for nothing.

## When something breaks

Go to [runbooks/README.md](runbooks/README.md) for symptom → fix. For the mirror
specifically, start at [mirror.md](mirror.md).

Four traps worth knowing before your first incident, all of which cost real
time already:

- A directory under `apps/` that no kustomization references **deploys nothing
  and CI stays green**.
- Editing `Deployment.replicas` does nothing if a KEDA ScaledObject targets it.
- A ConfigMap that is not a `configMapGenerator` output **does not roll anything**
  when edited.
- `kubectl diff` runs before apply, so a new RoleBinding whose Role does not
  exist yet kills the whole deploy.
