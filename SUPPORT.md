# Support

## Getting help

1. Check `docs/runbooks/` for your symptom (start with the index there).
2. Check `docs/ROADMAP.md` and `CHANGELOG.md` for known issues and recent changes.
3. Open a GitHub issue with the bug/feature template (logs, namespace,
   `kubectl` output, and the commit SHA of `main` you deployed from).

## Operational contacts

| Role | Who |
|---|---|
| Maintainer / cluster admin | @wazaglo (see CODEOWNERS) |
| Security issues | Direct message only — see SECURITY.md, never a public issue |

## Useful commands

```bash
# Where am I deployed from?
git -C eks-gitops rev-parse --short HEAD

# Cluster state in one glance
kubectl get nodes
kubectl -n nginx-demo get ingress nginx -o wide
kubectl -n monitoring get deploy,pod,svc,pvc -o wide

# Recent pipeline runs
gh run list --repo wazaglo/eks-gitops --limit 5
```
