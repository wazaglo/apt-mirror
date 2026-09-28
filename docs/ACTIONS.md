# ACTIONS

What was actually done, and why. Chronological. For current state see
[mirror.md](mirror.md); for symptom → fix see
[runbooks/README.md](runbooks/README.md).

The platform below predates the mirror. The mirror work starts at §A1, and most
of §1–§6 exists only to support it.

---

## A. The mirror

### A1. Nothing deployed, and CI was green

The first mirror push added `apps/mirror/` and the deploy job went green in 39
seconds having applied nothing.

`deploy.yml` renders exactly one target, `envs/dev/`, and **kustomize is not a
recursive directory walker**. `apps/mirror` was referenced by no kustomization,
so it contributed zero objects. `pr-validate` only builds `envs/{dev,prod}`, so
a directory with no kustomization was never even parsed — green CI proved
nothing.

Fix: `apps/mirror/kustomization.yaml` plus a line in both `envs/`. Now
documented in the README conventions and in
[pipeline.md](runbooks/pipeline.md).

Three more faults sat behind that one, each independently fatal:

- **No kustomization.yaml** — pointing a kustomization at the directory would
  have failed outright.
- **Namespace mismatch** — `namespace.yaml` declared `mirror-project` while the
  PVC and Pod declared `mirrors`; neither existed, so apply failed with
  `namespaces "mirrors" not found`.
- **A bare Pod** — the `eks-gitops-deployer` ClusterRole grants `pods`
  `get/list/watch` only, no create. Converted to a Deployment, which is granted.

### A2. The image could never sync

The pushed `debian12-mirror:1.0` used **debmirror** with
`--root=/debian` and `DIST="bookworm,bookworm-updates,bookworm-security"`.

`bookworm-security` is a **separate archive** rooted at
`security.debian.org/debian-security`. Asking for it under
`deb.debian.org/debian` is a 404 that **aborts the entire sync**:

```
** GET https://deb.debian.org/debian/dists/bookworm-security/Release  404 Not Found
Failed to download some Release, Release.gpg or InRelease files!
```

Switched to **apt-mirror**, whose `mirror.list` gives each archive its own root.
Verified the rebuilt image against upstream before deploying: all three dists'
`Release` files fetched and signature-checked, zero 404s, zero GPG failures,
`118.2 GiB will be downloaded`.

Separately, the image had **no signature verification at all** —
`Can't check signature: No public key` on every dist, because apt-mirror falls
back to gpgv against an empty `~/.gnupg`. Fixed with
`signed-by=/usr/share/keyrings/debian-archive-keyring.gpg`.

Also switched from debmirror's forever-loop to **sync-once-then-idle**, because
a Deployment whose entrypoint exits restarts in a tight loop.

### A3. The PVC could never bind

```
Unauthenticated desc = Access Denied
  …AmazonEKSPodIdentityAmazonEFSCSIDriver-efs-csi-controller-sa-Rol…
  is not authorized to perform: elasticfilesystem:DescribeAccessPoints
```

The EFS CSI driver is EKS addon-managed and authenticates through addon-owned
**Pod Identity** associations, which take precedence over the service account's
IRSA annotation. The addon role lacks `DescribeAccessPoints` and
`CreateAccessPoint`, so `provisioningMode: efs-ap` fails on every attempt and
the PVC sits `Pending` forever. A correctly-permissioned IRSA role exists and
is never used.

Not fixable from manifests, so binding moved to a **static PV per access
point** — the pattern `grafana-efs` and `prometheus-efs` already used, and
which never touches the EFS control plane. Recorded as
[ADR-0005](adr/0005-static-pv-per-efs-access-point.md).

Two smaller traps here: `StorageClass.parameters` is `map[string]string`, so
`accessPointId` must be a flat dotted key, never nested YAML; and a
`PersistentVolume` left `Released` after its claim was deleted will not rebind
under `Retain` until `spec.claimRef` is cleared.

### A4. The deploy gate killed itself

```
Error from server (NotFound): rolebindings.rbac.authorization.k8s.io
  "debian12-sync-trigger" not found
##[error]kubectl diff failed with exit code 2
```

`deploy.yml` runs `kubectl diff` **before** applying. Diff dry-run-creates each
object in isolation, and a RoleBinding's `roleRef` must already resolve — so
with neither object present, diff exited 2 and the job died before applying
anything, taking the whole mirror with it.

The gate was right to fire. The trigger RBAC moved to `platform/` and is applied
by hand, which removes the ordering dependency entirely. This is *not* the usual
cluster-scope rule in [ADR-0004](adr/0004-push-gitops-least-privilege.md) —
namespaced Roles are otherwise CI-manageable; it is specifically the bootstrap
cycle.

### A5. A schema error only the server would catch

```
unknown field "spec.template.spec.containers[0].ports[0].containerName"
```

`ContainerPort` has no `containerName`; it is `name`. The API server rejected
the entire Deployment. `kustomize build` and `kubectl apply --dry-run=client`
both passed — only `--dry-run=server` caught it.

### A6. Every package 404'd while `/healthz` returned 200

The serving tier was healthy, the spool was populated, and every apt path 404'd.
The nginx alias pointed at `<mount>/deb.debian.org/debian/` but apt-mirror writes
to `$base_path/mirror/<host>/<root>/`, so the real path has an extra `mirror/`
segment. Remounted at `/srv/apt-mirror` so the config reads the same way
`mirror.list` does.

A second nginx trap was recorded at the same time: **regex locations are
evaluated before prefix locations**, so a `location ~* \.deb$` block added for
cache headers would beat the `alias` and 404 every package. Caching belongs in
the edge proxy, where the URI passes through unchanged.

### A7. First successful sync

118.2 GiB, 67,357 files, **59 minutes**. Verified end to end with a real client:
`apt-get update` with GPG verification on and no `[trusted=yes]`, then
`apt-get install jq`, and a `.deb` whose SHA-256 matched the one in the
mirror's own signed `Packages.xz`.

Prediction corrected twice along the way — the sync was expected to take days
and did not, because EFS throughput was far better than assumed.

### A8. Snapshots

`cp -al` into `snapshots/<name>/`, served at `/snapshots/<name>/…`. Proven to be
genuinely hardlinked rather than a copy by **inode, not by assumption** — a file
in both trees reports the same inode with `links=2`, and EFS usage did not move.

The layout is deliberately flattened to `<name>/{debian,debian-security}` rather
than mirroring the spool's `mirror/<host>/<root>/`, so client URLs are clean and
one nginx `alias` serves the whole tree with no regex.

`flock` serialises snapshots against syncs. It had to be verified on this EFS
NFSv4 mount (acquire, block, release) rather than assumed, and the sync's lock
is scoped to a **subshell** around `apt-mirror` — the idling sync pod would
otherwise hold it for 24 hours and block every snapshot.

First snapshot took **22 minutes** for 67k files, all EFS metadata latency.
Recorded as [ADR-0006](adr/0006-hardlink-snapshots.md).

### A9. Capacity, before Ubuntu

The nodegroup had **1 free pod slot** of 55 and both mirror Deployments plus the
Ubuntu sync all wanted one. Cut Grafana to a single replica — which
[ADR-0003](adr/0003-efs-for-grafana.md) already argued for, since two replicas
share one SQLite over NFS — and set `maxSurge: 0` on the single-replica
monitoring rollouts so a rollout cannot silently eat the remaining margin.

The Grafana change **did nothing at first**: the pod went straight back to 2,
because a KEDA HPA overwrites `spec.replicas` from the cron trigger every
morning. Fixed in the ScaledObject.

### A10. Ubuntu 24.04 noble

Access point `fsap-02586212ea002c468`, its own static PV, ConfigMap, sync
Deployment and 12:30 UTC trigger, sharing the one serving tier — **one new pod,
not two.**

Easier than Debian in the way that mattered: Ubuntu's security suite is under
the **same** `/ubuntu` root, so the 404 trap from A2 does not exist. Scoped to
`main` + `restricted` (~259 GiB) rather than all four components.

Image `wazaglo/ubuntu24-mirror` differs from the Debian one only in base OS and
keyring (`ubuntu-keyring`, hence a different `signed-by` path); the entrypoint
is shared, so both build from one context with two Dockerfiles.

### A11. Repository renamed to `apt-mirror`

The deploy identity chain was rebuilt **additively** and proven before deleting
anything, via CloudTrail rather than inference:

```
before:  repo:wazaglo@…/eks-gitops@…  →  apt-mirror-github-actions
after:   repo:wazaglo@…/apt-mirror@…  →  apt-mirror-github-actions
```

The new OIDC role trusts both repository subjects, so a push works whether it
arrives before or after the rename. IAM roles cannot be renamed, so it was
create-then-delete throughout: new role, new ClusterRole and binding, new access
entry, secret repointed, deploy proven, then the old four objects removed. The
role's inline policy was copied via `get-role-policy | put-role-policy` so it
could not drift.

The SSM prefix `/eks-gitops/monitoring/*` was **not** renamed. SSM paths are
live AWS resources holding the Grafana credentials, independent of the
repository name.

### A12. Manifests made comment-free

507 comment lines moved into `docs/` rather than deleted.

The stripper had to be block-scalar aware. Ten manifests ship real content in
`|` blocks — `mirror.list`, `apt.conf`, `postmirror.sh`, `snapshot.sh`, the
nginx and Prometheus configs — and those lines start with `#` while being
*data*. A naive `sed '/^\s*#/d'` would have removed the `#!/bin/bash` shebangs
and broken both scripts.

The first version of the stripper had a real bug: it treated a **blank line**
inside a block scalar as dedent, so it left payload mode at the first empty line
and stripped the comments after it. Caught by diffing ConfigMap `data` before
and after — every payload is now verified byte-identical, so nothing about what
gets deployed changed.

---

## 6. Observability

Alloy DaemonSet (logs + node metrics) in place of node-exporter, Loki to S3,
Prometheus moved from `emptyDir` to EFS access point `fsap-012a38be930c8a207` so
the TSDB survives node termination. Recorded in
[ADR-0002](adr/0002-alloy-over-node-exporter.md).

## 5. CI pipeline

Two traps still live in the workflow and are documented in
[pipeline.md](runbooks/pipeline.md): `kubectl diff` exits 1 when changes exist
and must not be treated as failure, and diff runs before apply, which is what
made the RoleBinding cycle in A4 fatal.
