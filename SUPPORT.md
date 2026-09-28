# Support

## Getting help

1. **The mirror** — start at [docs/mirror.md](docs/mirror.md). It covers the
   operating commands and the failure modes that are easy to reintroduce.
2. **A symptom** — [docs/runbooks/README.md](docs/runbooks/README.md) maps
   symptom to runbook.
3. **Recent changes** — [CHANGELOG.md](CHANGELOG.md) and
   [docs/ACTIONS.md](docs/ACTIONS.md) record what was done and why.
4. Otherwise open an issue with logs, namespace, `kubectl` output, and the
   commit SHA of `main` you deployed from.

## Operational contacts

| Role | Who |
|---|---|
| Maintainer / cluster admin | @wazaglo |
| Security issues | Private advisory — see [SECURITY.md](SECURITY.md), never a public issue |

## Useful commands

```bash
# Where am I deployed from?
git rev-parse --short HEAD

# Is the mirror actually serving?
curl -sSI https://debian-mirror.azubisuccess.space/debian/dists/bookworm/Release
curl -sSI https://ubuntu-mirror.azubisuccess.space/ubuntu/dists/noble/Release

# Cluster state in one glance
kubectl get nodes
kubectl -n mirrors get deploy,pod,svc,pvc -o wide

# Pod capacity — the number that bites first
kubectl get pods -A --no-headers | grep -vcE 'Completed|Error'   # keep under 55

# Recent pipeline runs
gh run list --repo wazaglo/apt-mirror --limit 5
```

## Before you file

Two things account for most "it is broken" reports, and neither is a fault:

- **A `dists/` 404 during a first sync is normal.** apt-mirror stages indexes in
  `skel/` and only promotes them when the archive finishes. Check for an
  in-flight sync first — do not go changing the nginx alias.
- **Everything returns 502 between 17:58 and 10:00 UTC.** The node group is
  terminated deliberately, to save cost. See
  [cost-scheduler.md](docs/runbooks/cost-scheduler.md).
