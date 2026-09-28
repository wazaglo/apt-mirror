# Contributing

## Workflow

Branch off `main`, open a PR, wait for `pr-validate` and `secret-scan`, then
merge. Merging to `main` deploys `envs/dev/` automatically.

Conventional commits, and the subject should say what changed *and why it was
wrong before* when it is a fix:

```
fix(mirror): alias pointed one directory too high — every apt path 404'd
perf(monitoring): free a pod slot for the Ubuntu sync, stay on 5 nodes
```

## Validate locally

```bash
kubectl kustomize envs/dev/  > /dev/null && echo "dev renders"
kubectl kustomize envs/prod/ > /dev/null && echo "prod renders"
grep -rEn 'image:[[:space:]]*[^ ]+:latest([[:space:]]|$)' apps/ platform/ && echo "FAIL: unpinned image"
terraform -chdir=terraform/eks fmt -check
```

**Rendering is not validation.** Kustomize does no schema checking, and
`kubectl apply --dry-run=client` does not do strict decoding. Two real bugs —
an invented `containerName` field and an nginx alias one level too high — passed
both and were only caught by `--dry-run=server` and an actual HTTP request. If
you change anything the API server validates, dry-run server-side:

```bash
kubectl kustomize envs/dev/ | kubectl apply --dry-run=server -f -
```

## Rules

**Manifests carry no comments.** The reasoning lives in
[docs/mirror.md](docs/mirror.md) and [docs/adr/](docs/adr/). If you find
yourself writing a comment explaining a non-obvious field, that is a docs
change, not a comment.

The exception is data shipped *inside* a `|` block — `mirror.list`, `apt.conf`,
`postmirror.sh`, `snapshot.sh`, the nginx configs. Those `#` lines are read at
runtime by the shell or by nginx. `hack/strip-manifest-comments.py` knows the
difference; do not strip them with `sed`.

**Cluster-scoped objects are applied by hand.** `platform/` and Helm in
`infra/` never go through CI, and the PR must carry the exact command. This is
a security property, not a convention — see
[ADR-0004](docs/adr/0004-push-gitops-least-privilege.md).

**Never commit secrets.** They live in SSM and reach the cluster through
External Secrets.

**Pin images by digest.** A tag is not enough and `:latest` is a CI failure.

**One site per file** in `apps/nginx/base/sites/`, listed in that app's
`configMapGenerator`.

## Things that will bite you

- **A new app directory must be referenced from an `envs/*/kustomization.yaml`.**
  Kustomize is not a recursive walker. An unreferenced directory deploys nothing
  and CI stays green. Check with
  `kubectl kustomize envs/dev/ | grep -c '^kind:'`.
- **A KEDA ScaledObject overrides `Deployment.replicas`.** Editing the manifest
  does nothing; the HPA resets it each morning. Edit the ScaledObject.
- **A plain ConfigMap does not trigger a rollout.** `mirror-nginx-conf` is not
  a `configMapGenerator` output, so editing it leaves the pod on its startup
  config. `nginx-sites` *is* generated, so its name change forces a rollout
  automatically.
- **A new RoleBinding whose Role does not exist yet will fail `kubectl diff`**,
  and the deploy job dies before applying anything. Put bootstrap RBAC in
  `platform/`.
- **The nodegroup has one free pod slot.** Check
  `kubectl get pods -A --no-headers | grep -vcE 'Completed|Error'` before adding
  any pod.

## Docs

Behaviour changes need a docs change in the same PR. If it took you a while to
work out, someone else will hit it — put it in [docs/mirror.md](docs/mirror.md)
or a runbook. A durable decision gets an ADR in [docs/adr/](docs/adr/).
