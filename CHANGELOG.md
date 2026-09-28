# Changelog

All notable changes to this project are documented here, newest first.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added

- **Ubuntu 24.04 (noble) mirror** at `https://ubuntu-mirror.azubisuccess.space`.
  Separate sync (own access point `fsap-02586212ea002c468` at
  `/mirrors/ubuntu/24.04`, own lock, own 12:30 UTC schedule) sharing the single
  serving tier — one new pod, not two. Scoped to `main` + `restricted`
  (~259 GiB); adding `universe`/`multiverse` roughly doubles that.
  Image `wazaglo/ubuntu24-mirror` needs `ubuntu-keyring`, so the two distro
  images differ only in base OS and keyring and share one entrypoint.
- **Hardlink snapshots** of the Debian spool, servable at
  `/snapshots/<name>/{debian,debian-security}/` and pinned by a client
  `sources.list`. `cp -al` costs no bytes — a 127 GB apparent snapshot added
  0 — but ~22 minutes of EFS metadata work, and each retained snapshot pins
  whatever later syncs replaced. Pruned to the newest 3, and only names matching
  `^[0-9]{8}-[0-9]{6}Z$` are ever deleted.
- **`docs/mirror.md`**, the operating guide, plus
  [ADR-0005](docs/adr/0005-static-pv-per-efs-access-point.md) and
  [ADR-0006](docs/adr/0006-hardlink-snapshots.md).
- `hack/strip-manifest-comments.py`, block-scalar aware, so the
  comment-free-manifest decision stays auditable.

### Changed

- **Repository renamed `eks-gitops` → `apt-mirror`.** The deploy identity chain
  was rebuilt additively and proven via CloudTrail before anything was deleted:
  a new OIDC role trusting both repository subjects, a new ClusterRole and
  access entry, and only then removal of the old four objects. Verified in both
  directions — the new role assumed the old repo subject, then the new one.
  `AWS_DEPLOY_ROLE_ARN`, `platform/bootstrap-rbac.yaml` and terraform updated.
  The SSM prefix `/eks-gitops/monitoring/*` is deliberately **not** renamed: SSM
  paths are live AWS resources holding the Grafana credentials and are
  independent of the repository name.
- **Manifests are comment-free** (507 lines moved into `docs/`). Block scalars
  carry data, not commentary, and were left intact. Data payloads
  in `|` block scalars are untouched — `mirror.list`, `apt.conf`,
  `postmirror.sh`, `snapshot.sh` and the nginx configs all ship their `#` lines,
  because those are read at runtime. Every ConfigMap's `data` was verified
  byte-identical across the change.
- **Grafana 2 → 1 replica**, and the change is made in the ScaledObject rather
  than the Deployment. A KEDA HPA overwrites `spec.replicas` every morning, so
  editing the manifest alone did nothing and the pod went straight back to 2.
  The single-writer reasoning moves to `base` from a prod-only patch, since
  two replicas on one SQLite over EFS NFS is wrong everywhere.
- `prometheus`, `loki` and `blackbox` roll with `maxSurge: 0`. The nodegroup is
  at its pod ceiling, so a default 25% surge would leave a rollout
  unschedulable and consume the margin the mirror depends on.
- `debian12-sync-trigger` → `mirror-sync-trigger`, covering both sync
  Deployments.

### Fixed

- **`apps/mirror` deployed nothing while CI stayed green.** No kustomization
  referenced it, and kustomize is not a recursive walker — an unreferenced
  directory renders as zero objects silently. Now wired into `envs/{dev,prod}`
  with a `kustomization.yaml` of its own.
- **The first mirror image could never complete a sync.** It asked for
  `bookworm-security` under `deb.debian.org/debian`, but that suite is a
  separate `/debian-security` archive. The 404 aborted every run. Replaced with
  apt-mirror, whose per-archive-root config is correct.
- **No signature verification.** apt-mirror fell back to gpgv against an empty
  `~/.gnupg` and failed every dist with `Can't check signature: No public key`.
  Each distro's `apt.conf` now sets `signed-by` explicitly.
- **The PVC could never bind.** Dynamic `efs-ap` provisioning is IAM-blocked —
  the addon-managed EFS CSI driver authenticates via Pod Identity, which lacks
  `DescribeAccessPoints`/`CreateAccessPoint`, so every attempt failed
  `AccessDenied` and the PVC sat `Pending`. Now a static PV per access point.
- **The deploy job died before applying anything.** A RoleBinding whose `roleRef`
  Role does not exist yet makes `kubectl diff` exit 2, because diff dry-run-creates
  each object in isolation. The trigger RBAC moved to `platform/` and is applied
  by hand.
- **`ContainerPort` has no `containerName` field.** The API server rejected the
  whole Deployment on a strict-decode error that `kustomize build` and
  `--dry-run=client` both missed.
- **Every apt path 404'd** while `/healthz` returned 200: the nginx alias
  pointed one directory too high, missing the `mirror/` segment that
  apt-mirror's own layout requires.
- The two snapshot jobs could run concurrently against one spool. A `flock` now
  serialises them, scoped to a subshell so the idling sync container does not
  hold the lock for 24 hours.
- EFS backups disabled on the mirror filesystem only. It is a byte-for-byte copy
  of a public upstream archive, so a restore is just an `apt-mirror` re-run.
  Left enabled on `eks-shared-efs`, which holds the Grafana database and the
  Prometheus TSDB — real state that cannot be regenerated.

### Known limitations

- Snapshots cover Debian only; Ubuntu's spool is a separate filesystem and one
  nginx `alias` cannot span two roots.
- Both distros share `ng-eks` and therefore the nightly scale-to-zero. Endpoints
  answer 502 overnight and an interrupted sync resumes the next morning.
- The mirror filesystem is Standard with 2 mount targets and backups disabled
  (~$59/wk at 360 GiB). One Zone with a single mount target would be ~4x cheaper
  and would avoid cross-AZ egress, at the cost of re-syncing everything.
- No dedicated node group; the mirror inherits the pod ceiling.
- `mirror-nginx-conf` is a plain ConfigMap, so editing it does not roll the
  serving tier — restart the pod. The edge proxy is unaffected because
  `nginx-sites` is generated and its name change forces a rollout.

## [0.5.0] - 2026-09-27

- Nightly cost schedule: KEDA cron ScaledObjects scale every workload to 0
  outside 10:05–17:54 UTC; Lambda + EventBridge (`infra/scheduler/`) terminates
  the node group at 17:58 and relaunches at 10:00.
- Prometheus moved from `emptyDir` to EFS access point
  `fsap-012a38be930c8a207` so the TSDB survives node termination.
- `deploy.yml` off-hours guard: applies manifests at night (keeping git in sync
  with the cluster) but skips the rollout wait, which would hang with no nodes.
- Repository restructure into `apps/` + overlays, `platform/`, `infra/`, `docs/`.
- EventBridge now invokes the node scheduler through a dedicated
  `eks-node-scheduler-invoke` role trusting `events.amazonaws.com`. The previous
  target reused the function's execution role, which only trusts
  `lambda.amazonaws.com`, so **every scheduled run was rejected**.
- External Secrets (SSM), image pinning by digest, `pr-validate` and
  `secret-scan` CI gates.

## [0.1.0] - 2026-09-27

- Initial EKS GitOps repository: cluster, VPC, node group, ALB controller,
  EFS CSI driver, multi-FQDN nginx edge, Grafana/Loki/Prometheus/Alloy/blackbox
  observability.
