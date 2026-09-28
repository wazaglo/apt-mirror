# Roadmap

What is built, what is deliberately not, and what is next. Current as of
2026-09-28.

## Done

| | |
|---|---|
| Debian 12 bookworm mirror | live at `debian-mirror.azubisuccess.space`, ~118 GiB, 67k files |
| Ubuntu 24.04 noble mirror | live at `ubuntu-mirror.azubisuccess.space`, ~259 GiB |
| Hardlink snapshots | one taken, served at `/snapshots/<name>/`, retention 3 |
| Signed indexes | both distros verify via `signed-by`; clients get GPG-verified `apt-get` |
| EFS per-distro access points | one PV each, static binding |
| Cost schedule | node group 17:58→10:00 UTC; endpoints 502 overnight by design |
| Repo focus | renamed `apt-mirror`; deploy identity rebuilt and proven |
| Docs | mirror guide, ADRs, comment-free manifests |

## Next, in the order I would do them

### 1. Terraform for the mirror's EFS

The mirror's storage exists **only as string literals** in Kubernetes YAML.
There is no `aws_efs_file_system`, no `aws_efs_access_point`, no
`aws_eks_node_group` for the mirror. The repo cannot rebuild what it depends
on most.

Needed in `terraform/eks/`:

- `aws_efs_file_system` — `fs-0b0491ead2bac1c8c`, backups `DISABLED`
- `aws_efs_access_point` ×2 — `fsap-020b79f4588c2d482`, `fsap-02586212ea002c468`
- `aws_eks_node_group` for a dedicated mirror node group

Requires import blocks and careful scoping: both terraform READMEs warn that
the stacks mirror live infrastructure and were never imported, so a plain apply
creates duplicates.

### 2. Snapshots for Ubuntu

Debian snapshots work. Ubuntu's spool is a separate filesystem, so one nginx
`alias` cannot span both roots. The open question is the URL scheme, and it
should be decided before any code:

- `/snapshots/<name>/debian/…` and `/snapshots/<name>/ubuntu/…` under one
  prefix — needs a regex location, which is the trap that 404'd every package
- separate prefixes, e.g. `/debian-snapshots/` and `/ubuntu-snapshots/`
- one snapshot spanning both, which needs a shared volume

Also: the snapshot CronJob is still `suspend: true`. It has been run once by
hand. Un-suspend when daily snapshots are wanted.

### 3. A dedicated node group

The mirror shares `ng-eks` with everything else, which is why it inherits the
nightly scale-to-zero and the pod ceiling. A mirror that consumers depend on
probably should not 502 every night.

A `t3.medium` group in a single AZ avoids cross-AZ EFS egress and the t3 CPU
credit throttling that makes a 259 GiB sync far slower than it should be. Note
`docs/runbooks/node-creation-failure.md`: larger instances have not always
launched on this account.

### 4. Re-EFS as One Zone

Standard with 2 mount targets, backups now disabled, is roughly $59/wk at
360 GiB. One Zone with a single mount target is about a quarter of that and
removes cross-AZ egress. Cost: re-sync ~360 GiB and a maintenance window.

Also means either migrating the spool or running both during a cutover.

### 5. Monitoring coverage

The blackbox exporter currently probes Grafana and the edge Service. The mirror
endpoints should be probed directly so a broken cert, a 404 on `dists/`, or a
serving-tier crash raises an alert instead of being found by a client.

## Deliberately not doing

- **ArgoCD.** Push-based CI is the accepted trade;
  [ADR-0004](adr/0004-push-gitops-least-privilege.md) records why. It costs
  a manual step for cluster-scoped objects, which is tolerable for the handful
  here.
- **Backups of the mirror spool.** A restore is an `apt-mirror` re-run. Backup
  cost on a public-upstream copy buys nothing.
- **Infrequent Access or Archive EFS classes.** Storage is cheap; the per-GB
  retrieval fee across tens of thousands of small files is not, and neither
  class supports the hardlinks the snapshots depend on.
- **S3 for the mirror.** No hardlinks, no reliable `flock`, no atomic rename —
  which is the whole basis of the snapshot design.
- **More distros until there is demand.** The architecture is ready for it (add
  an access point, a PV, a ConfigMap, a sync Deployment, an alias and a vhost),
  but each one costs a sync pod against a nodegroup at its ceiling.
