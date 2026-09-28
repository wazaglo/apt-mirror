# As-built: the mirror on EKS

Historical design record. For current state see [mirror.md](docs/mirror.md) and
topology see [architecture.md](docs/architecture.md).

> This file previously held a forward-looking plan dated 2026-09-27. It
> described a design that was **not** the one built, and it has been rewritten
> to record what actually shipped and why. The original's cost analysis and
> rejected alternatives are preserved below, because the reasoning still holds.

## What we set out to do

Move the APT mirror's data off standalone mirror servers and into EKS:
containerise the sync, store the archive on EFS, serve it through the existing
ALB + nginx edge, and give internal clients an internal endpoint instead of
reaching the public archives.

## What shipped

Two distros, one EFS filesystem, one access point each, one serving tier.

| | Debian 12 | Ubuntu 24.04 |
|---|---|---|
| endpoint | `debian-mirror.azubisuccess.space` | `ubuntu-mirror.azubisuccess.space` |
| access point | `fsap-020b79f4588c2d482` `/mirrors/debian/12` | `fsap-02586212ea002c468` `/mirrors/ubuntu/24.04` |
| image | `wazaglo/debian12-mirror` | `wazaglo/ubuntu24-mirror` |
| sync tool | apt-mirror | apt-mirror |
| components | main, contrib, non-free, non-free-firmware | main, restricted |
| archive | ~118 GiB, 67k files | ~259 GiB, 24k files |
| schedule | 10:00 UTC | 12:30 UTC |

Plus hardlink snapshots of the Debian spool at `/snapshots/<name>/`.

## Where the plan diverged, and why

| planned | shipped | reason |
|---|---|---|
| `debmirror` | **apt-mirror** | debmirror could not express Debian's two archive roots; `bookworm-security` under `/debian` is a 404 that aborts the sync |
| namespace `apt-mirror` | **`mirrors`** | fits both distros |
| `apps/apt-mirror/{base,overlays}` | **flat `apps/mirror/`** | one distro at first; overlays add nothing until a second environment exists |
| new nodegroup `ng-apt-mirror` (t3.medium) | **shared `ng-eks`** | not created — see ROADMAP |
| new `terraform/eks/apt-mirror.tf` | **not written** | the filesystem was made in the console; IaC is still open |
| EFS **One Zone**, 1 mount target, backups off | **Standard, 2 mount targets, backups now off** | created before the plan was costed; One Zone is the next step |
| `initContainer` to create the spool skeleton | **in the image entrypoint** | same effect, and it also serves the sync-then-idle pattern |
| nginx `runAsUser: 0` | **uid 101** | the access point is POSIX `1000:1000` with 0755, so a non-root nginx can read. The `runAsUser: 0` warning was specific to a 0700/0:0 access point |
| static PV per access point | **shipped as planned** | and turned out to be the only option — see ADR-0005 |
| EFS ~$22/week | **~$59/week** | 360 GiB on Standard/2MT rather than One Zone/1MT |

## Storage decisions that still stand

EFS was chosen over the alternatives for properties the snapshots depend on,
not for price.

**Rejected: Infrequent Access / Archive.** Storage is cheap; the per-GB retrieval
fee across tens of thousands of small files on every `apt-get` is not, and
neither class supports hardlinks.

**Rejected: S3 via mountpoint-s3 / rclone / s3fs.** No hardlinks, no reliable
`flock`, no atomic rename. That breaks both the snapshot design and
apt-mirror's own pool updates.

**Rejected: EBS gp3.** Not shareable between two writers, so it breaks the
single-writer-with-shared-POSIX model.

**No backups, deliberately.** The spool is a byte-for-byte copy of a public
upstream archive, so a restore is an `apt-mirror` re-run costing hours and free
upstream bandwidth. Backups bill per GB-month at a premium over storage and buy
zero recovery value. Now actually disabled on the mirror filesystem.

The observability filesystem is the opposite case and keeps its backups: the
Grafana database and Prometheus TSDB are real state.

## Cost, as it stands

| | |
|---|---|
| EFS Standard, 2 mount targets, 360 GiB | ~$59/week |
| EFS One Zone, 1 mount target, 360 GiB | ~$16/week |
| node group | terminated nightly, ~8h/day |

The One Zone option is the obvious win and is deliberately deferred rather than
forgotten — it requires re-syncing ~360 GiB.

## Gotchas that were real, not hypothetical

Every one of these cost time during the build. All are written up in
[mirror.md](docs/mirror.md); the durable ones have their own ADR.

1. **Debian's security suite is a separate archive root.** Ubuntu's is not.
   Getting this wrong is a 404 that kills the whole sync.
2. **apt-mirror needs an explicit `signed-by`.** Otherwise it verifies against
   an empty `~/.gnupg` and every dist fails.
3. **Dynamic EFS provisioning is IAM-blocked here** (addon Pod Identity).
4. **The spool is single-writer.** `Recreate`, never RollingUpdate, plus a
   `flock` for snapshots.
5. **A `flock` around a container that then idles holds the lock all day.**
6. **nginx evaluates regex locations before prefix ones.** A cache-header regex
   404s every package.
7. **KEDA overwrites `Deployment.replicas` every morning.**
8. **A new RoleBinding whose Role does not exist yet kills the deploy**, because
   `kubectl diff` runs before apply.
9. **`/dists/` 404s until a sync completes.**
