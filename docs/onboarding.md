# Onboarding

Goal: from a fresh clone to a verified deploy in under 30 minutes.

## 1. Prerequisites

```bash
aws --version          # v2.x
kubectl version --client
helm version
terraform version      # only if touching terraform/
gh auth status         # optional, for run logs
```

AWS identity used in this repo (account `195675606509`, region `us-west-1`):
an IAM user with EKS + IAM read/write. Confirm:

```bash
aws sts get-caller-identity
```

## 2. Clone and validate (no cluster needed)

```bash
git clone https://github.com/wazaglo/apt-mirror.git && cd apt-mirror
kubectl kustomize envs/dev/ > /dev/null && echo "manifests OK"
```

## 3. Point kubectl at the cluster

```bash
aws eks update-kubeconfig --region us-west-1 --name eks-lab
kubectl get nodes
```

## 4. Know what CI does and does not do

| Object | Who applies |
|---|---|
| Everything under `apps/` (deployments, services, configmaps, ingress, PVCs) | CI on push to `main` |
| Everything under `platform/` (ClusterRoles, StorageClass, PV, ClusterSecretStore) | **You**, manually |
| Helm releases (`infra/`) | **You**, manually |
| Secrets | External Secrets Operator, from SSM |

If a change under `platform/` or `infra/` lands, the PR description must carry
the manual apply command.

## 5. Deploy

```bash
git checkout -b feat/my-change
# edit under apps/
kubectl kustomize envs/dev/ > /dev/null          # always check locally first
git commit -am "feat: my change"
git push -u origin feat/my-change                 # open PR, CI validates
# after review + merge to main, CI deploys envs/dev
```

## 6. Verify

```bash
kubectl -n nginx-demo get ingress nginx -o wide
kubectl -n monitoring get deploy,pod -o wide
curl -s -o /dev/null -w '%{http_code}\n' https://grafana.azubisuccess.space/login
gh run list --repo wazaglo/apt-mirror --limit 3
```

## 7. Grafana login

Credentials come from SSM via External Secrets. Read them with:

```bash
aws ssm get-parameter --region us-west-1 \
  --name /eks-gitops/monitoring/grafana-admin-password --with-decryption
```

Rotate by writing a new value (`--type SecureString --overwrite`) and running
`kubectl -n monitoring rollout restart deploy/grafana`.

## 8. When something breaks

Go to [runbooks/](runbooks/README.md) — it maps symptoms to fixes. The
operations log of what was actually done lives in [ACTIONS.md](ACTIONS.md).
