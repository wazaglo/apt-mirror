# Runbooks

Symptom → first command → fix. Historical detail for each incident is in
[ACTIONS.md](../ACTIONS.md).

| Symptom | Runbook |
|---|---|
| Pods stuck `Pending`, "Too many pods" | [node-pressure.md](node-pressure.md) |
| `NodeCreationFailure` on a node group | [node-creation-failure.md](node-creation-failure.md) |
| Grafana won't start / "database is locked" | [grafana.md](grafana.md) |
| Loki crash-looping | [loki.md](loki.md) |
| 502 / 404 on a site FQDN | [ingress-routing.md](ingress-routing.md) |
| CI pipeline red | [pipeline.md](pipeline.md) |
| Rotating a secret | [secrets.md](secrets.md) |
| EFS pod won't mount | [efs.md](efs.md) |

## Universal first steps

```bash
kubectl get pods -A -o wide | grep -v Running     # what is actually broken
kubectl -n <ns> describe pod <pod> | tail -20     # events tell the story
kubectl -n <ns> logs <pod> --tail=50
gh run list --repo wazaglo/eks-gitops --limit 3   # did CI even apply my change?
```
