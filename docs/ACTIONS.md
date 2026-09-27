# Actions Log

What was done on `eks-lab` (us-west-1, 1.36) and how to repeat it.
No commit history here — just actions and commands.

> **Path note (2026-09-27 restructure).** Commands below are kept as they were
> run, so they reference the old layout. Current paths:
> `manifests/nginx/` → `apps/nginx/base/`,
> `manifests/monitoring/` → `apps/monitoring/base/`,
> `manifests/alb/` → `apps/alb/`,
> `manifests/alb-controller/` → `infra/aws-load-balancer-controller/`,
> `manifests/cluster-rbac/` + `manifests/storage/` → `platform/`,
> `bootstrap/rbac.yaml` → `platform/bootstrap-rbac.yaml`,
> and the CI deploy root is now `envs/dev/` (was `manifests/`).
> Run `kubectl kustomize envs/dev/` instead of `manifests/`.
> `manifests/monitoring/secret.yaml` no longer exists — Grafana's admin
> credentials moved to SSM + External Secrets (see §13).

Sources:
- https://docs.aws.amazon.com/eks/latest/userguide/lbc-helm.html

## 1. Fix NodeGroup `ng-eks` (NodeCreationFailure)

Symptom: `Instances failed to join the kubernetes cluster`.

Root cause: `AmazonEKSNodeRole` had no attached policies.

```bash
aws iam attach-role-policy --role-name AmazonEKSNodeRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy
aws iam attach-role-policy --role-name AmazonEKSNodeRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy
aws iam attach-role-policy --role-name AmazonEKSNodeRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly

aws eks delete-nodegroup --region us-west-1 \
  --cluster-name eks-lab --nodegroup-name ng-eks
aws eks wait nodegroup-deleted --region us-west-1 \
  --cluster-name eks-lab --nodegroup-name ng-eks

aws eks create-nodegroup --region us-west-1 \
  --cluster-name eks-lab --nodegroup-name ng-eks \
  --node-role arn:aws:iam::195675606509:role/AmazonEKSNodeRole \
  --subnets subnet-035bd6840b31e5205 subnet-0f6034326efbaa2ae \
  --instance-types t3.small --ami-type AL2023_x86_64_STANDARD \
  --scaling-config minSize=2,maxSize=2,desiredSize=2 --disk-size 20
```

Result: `ng-eks` is `ACTIVE` (t3.small x2), no health issues.

## 2. ALB IAM (IRSA)

Policy `eks-alb-policy` already existed, verified it is the LB Controller policy.

```bash
# trust for kube-system/aws-load-balancer-controller on
# oidc.eks.us-west-1.amazonaws.com/id/9F997EDF8DCA5769A4464EA85CAD9E1C
aws iam create-role --role-name eks-alb-role \
  --assume-role-policy-document file:///tmp/alb-trust.json \
  --description "IAM role for AWS Load Balancer Controller on eks-lab"

aws iam attach-role-policy --role-name eks-alb-role \
  --policy-arn arn:aws:iam::195675606509:policy/eks-alb-policy
```

Result: `arn:aws:iam::195675606509:role/eks-alb-role`.

## 3. GitOps ServiceAccount (via GitHub)

Files in `eks-gitops`:
- `manifests/alb/serviceaccount.yaml` — `kube-system/aws-load-balancer-controller` with annotation `eks.amazonaws.com/role-arn: arn:aws:iam::195675606509:role/eks-alb-role`
- `manifests/alb/kustomization.yaml`
- `manifests/kustomization.yaml` now includes `nginx` + `alb`

```bash
kubectl kustomize manifests/ > /tmp/rendered.yaml
kubectl apply --dry-run=client -f /tmp/rendered.yaml
git add manifests/alb/serviceaccount.yaml manifests/alb/kustomization.yaml manifests/kustomization.yaml
git commit -m "Add ALB controller ServiceAccount with IRSA"
git push origin main
kubectl -n kube-system get sa aws-load-balancer-controller -o yaml
```

Result: SA applied by GitHub Actions deploy workflow.

## 4. Install AWS Load Balancer Controller (Helm)

Source: https://docs.aws.amazon.com/eks/latest/userguide/lbc-helm.html

```bash
helm repo add eks https://aws.github.io/eks-charts
helm repo update

helm upgrade --install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=eks-lab \
  --set serviceAccount.create=false \
  --set serviceAccount.name=aws-load-balancer-controller \
  --set region=us-west-1 \
  --set vpcId=vpc-0bab80c57b59d53be

kubectl -n kube-system rollout status deploy/aws-load-balancer-controller --timeout=180s
kubectl -n kube-system get pods -l app.kubernetes.io/name=aws-load-balancer-controller -o wide
kubectl -n kube-system logs deploy/aws-load-balancer-controller --tail=20
```

Result: chart `3.5.0`, 2/2 pods Running.

## 5. Controller as manifest (reference, not GitOps-applied)

Yes — the Helm release is a Deployment plus ClusterRole/Binding, Roles, Service, webhooks and CRDs.

Rendered with the same values and stored as reference:

```bash
helm template aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=eks-lab \
  --set serviceAccount.create=false \
  --set serviceAccount.name=aws-load-balancer-controller \
  --set region=us-west-1 \
  --set vpcId=vpc-0bab80c57b59d53be \
  > manifests/alb-controller/controller.yaml
```

- File: `manifests/alb-controller/controller.yaml` (chart 3.5.0, 10 objects: Deployment, ClusterRole/Binding, Role/Binding, Service, Secret, webhooks, IngressClass)
- `manifests/alb-controller/kustomization.yaml` exists for manual use only — intentionally NOT wired into `manifests/kustomization.yaml`
- Why not in CI: the GitHub deploy role (`bootstrap/rbac.yaml`) can't manage ClusterRoles/Bindings or webhooks, and live objects are Helm-owned — applying via CI would fail/fight Helm. To migrate off Helm: `helm uninstall` first, widen CI RBAC, then `kubectl apply -f manifests/alb-controller/controller.yaml`.

## 6. ALB subnet tags

```bash
aws ec2 create-tags --region us-west-1 \
  --resources subnet-0aa1f2e4e1e684c22 subnet-06a76730006f45c54 \
  --tags Key=kubernetes.io/role/elb,Value=1 Key=kubernetes.io/cluster/eks-lab,Value=shared
aws ec2 create-tags --region us-west-1 \
  --resources subnet-035bd6840b31e5205 subnet-0f6034326efbaa2ae \
  --tags Key=kubernetes.io/role/internal-elb,Value=1 Key=kubernetes.io/cluster/eks-lab,Value=shared
```

Result: public subnets carry `elb=1`, private carry `internal-elb=1`, all four carry `cluster/eks-lab=shared`. See `terraform/networking/` for the declarative copy.

## 7. EFS for Grafana (filesystem, access point, CSI driver)

```bash
# Filesystem fs-0ddb254be08c6267a (encrypted, elastic) already provisioned with
# mount targets in both AZs + TCP 2049 open from the node SG (sg-0306e5045f5a22414
# into sg-0598a68f03d5d2a39 — without this rule mounts time out):
aws ec2 authorize-security-group-ingress --region us-west-1 \
  --group-id sg-0598a68f03d5d2a39 --protocol tcp --port 2049 \
  --source-group sg-0306e5045f5a22414

# Access point enforcing Grafana's uid/gid 472 (the console-made AP had no POSIX
# user — unusable). Returns fsap-088c8c16707025698:
aws efs create-access-point --region us-west-1 \
  --file-system-id fs-0ddb254be08c6267a \
  --posix-user '{"Uid":472,"Gid":472}' \
  --root-directory '{"Path":"/grafana","CreationInfo":{"OwnerUid":472,"OwnerGid":472,"Permissions":"700"}}' \
  --tags Key=Name,Value=grafana-472

# CSI driver + IRSA role (adopt pre-existing RBAC/SAs into the release if Helm
# complains "exists and cannot be imported": label managed-by=Helm + annotate
# release-name/namespace, then retry):
aws iam create-role --role-name efs-csi-driver-role \
  --assume-role-policy-document file:///tmp/efs-csi-trust.json \
  --description "IRSA role for EFS CSI driver on eks-lab"
aws iam attach-role-policy --role-name efs-csi-driver-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonEFSCSIDriverPolicy
helm repo add aws-efs-csi-driver https://kubernetes-sigs.github.io/aws-efs-csi-driver/
helm upgrade --install aws-efs-csi-driver aws-efs-csi-driver/aws-efs-csi-driver \
  -n kube-system \
  --set controller.serviceAccount.annotations."eks\.amazonaws\.com/role-arn"=arn:aws:iam::195675606509:role/efs-csi-driver-role
```

Storage manifests: `platform/` (StorageClass `efs-sc` + static PV
`fs-0ddb254be08c6267a::fsap-088c8c16707025698) — applied MANUALLY, never via CI
(CI role can't manage cluster-scoped storage):
```bash
kubectl apply -f platform/
```

## 8. Grafana x2 on EFS + nginx URL block (namespace `monitoring`)

GitOps files: `manifests/monitoring/` (namespace, PVC bound to `grafana-efs`,
admin Secret, Deployment **2 replicas** sharing `/var/lib/grafana`, ClusterIP
:3000) + `manifests/nginx/proxy-config.yaml` (`grafana.azubisuccess.space` →
`grafana.monitoring.svc:3000`, default keeps welcome page), mounted into the
nginx Deployment. Pushed via `main` like everything else.

Capacity lesson: both t3.small nodes sat at 11/11 pods (their ENI max), so new
pods stayed Pending. t3.medium is NOT launchable on this account (Free Tier
restriction — ASG kept failing "not eligible for Free Tier"), so we scaled the
t3.small group 2 → 3 nodes instead:
```bash
aws eks update-nodegroup-config --region us-west-1 --cluster-name eks-lab \
  --nodegroup-name ng-eks --scaling-config minSize=2,maxSize=3,desiredSize=3
```
(The stuck `ng-eks-medium` group was deleted.) Verified: PVC Bound, 2/2 Running,
same `grafana.db` visible from both pods, `https://grafana.azubisuccess.space/login` → 200.

## 9. DNS + HTTPS (Hostinger + ACM)

- ACM wildcard `*.azubisuccess.space`:
  `arn:aws:acm:us-west-1:195675606509:certificate/cbf8d3ed-0f1f-4eeb-bba1-7093cdaf4fc6`
  (DNS-validated, ISSUED).
- Hostinger (`azubisuccess.space`, API `developers.hostinger.com/api/dns/v1`):
  CNAME `grafana` → ALB hostname, TTL 600. (First token was rejected 401 —
  needed a fresh hPanel API token. Token used in-memory only, never stored.)
- `manifests/nginx/ingress.yml`: `listen-ports` 80+443, `certificate-arn`,
  `ssl-redirect: 443`. Verified: HTTP → 301 to HTTPS, HTTPS serves Amazon-issued
  `CN=*.azubisuccess.space`, Grafana login page 200.

## 10. Observability: Alloy, Prometheus, node metrics, blackbox

All in `manifests/monitoring/` (app objects via GitOps) + `platform/cluster-rbac.yaml`
(ClusterRoles — applied MANUALLY, CI can't):
```bash
kubectl apply -f platform/cluster-rbac.yaml
```

- **Alloy DaemonSet** (all containers, all namespaces → Loki): `discovery.kubernetes`
  + `loki.source.kubernetes` + `loki.write http://loki...:3100`. Needs `pods/log`
  in its ClusterRole (without it: tailers retry with `forbidden`).
- **node-exporter REMOVED** — Alloy's `prometheus.exporter.unix` (same collectors)
  + `prometheus.scrape` → `prometheus.remote_write` to Prometheus
  (`--web.enable-remote-write-receiver`). Node metrics (`node_uname_info`=5)
  confirm it. Deleted the DaemonSet manifest + live object.
- **Prometheus** (1 replica, 6h retention on emptyDir) scrapes itself +
  blackbox probes (`https://grafana.azubisuccess.space/login`,
  `http://nginx.nginx-demo...` — both `probe_success=1`).
- **blackbox** (http_2xx, follows redirects).
- Grafana gets both datasources automatically (`grafana-datasources` ConfigMap,
  needs a Grafana restart after changes): Loki + Prometheus (default).
- Loki fixes along the way: removed `compactor.shared_store` (gone in 3.x),
  added `delete_request_store: s3`, and dropped the custom S3 `endpoint`
  (dskit routed even STS calls through it → S3 405). Verified: `/ready`, S3
  objects landing in `azubi-logs`, log queries returning entries.
- Grafana admin password: env is only honored on a FRESH database — ours kept
  the default `admin/admin` (likely first-boot race on shared SQLite). Reset live:
  `kubectl -n monitoring exec <pod> -- grafana cli --homepath /usr/share/grafana admin reset-admin-password <pw>`.
  Working password is the one in `manifests/monitoring/secret.yaml`; rotate it.

## 11. CI pipeline fixes (workflows went red — now green)

- Old workflow died on `kubectl wait deployment --all` in namespaces with no
  deployments (exit 1). New `deploy.yml`: validate job (offline) + deploy job
  that only waits on `deployment/nginx`.
- `kubectl apply --dry-run=client` needs an apiserver even with
  `--validate=false` → validate job now does `kustomize build` + a Python YAML
  sanity check; real dry-run stays in the deploy job (has cluster).
- `kubectl diff` exits 1 when changes exist; the runner's `bash -e` killed the
  step before reading `$?` → added `set +e` in that step.
- Generated `nginx-sites` ConfigMap landed in `default` (generators carry no
  namespace) → JSON patch in `manifests/nginx/kustomization.yaml` pins it to
  `nginx-demo`. Also cleaned the stray copy from `default`.
- Image tags: Docker Hub API was unusable from here, so new images use
  `:latest` (alloy, prometheus, blackbox) — pin exact versions from running
  pods when locking down.

## 12. Capacity: nodes 3 → 5 (t3.small, Free Tier limit)

t3.small allows 11 pods/node. DaemonSets (Alloy, EFS-CSI) + apps outgrew 3×11,
and t3.medium can't launch on this account (Free Tier restriction), so:
```bash
aws eks update-nodegroup-config --region us-west-1 --cluster-name eks-lab \
  --nodegroup-name ng-eks --scaling-config minSize=2,maxSize=5,desiredSize=5
```
Tip learned: a DaemonSet pod pinned to a full node stays Pending forever —
bounce one movable replica (we moved a coredns) to free its slot.

## Installed

- EKS `eks-lab` 1.36 + Managed NodeGroup `ng-eks` (t3.small x3, AL2023)
- IAM: fixed `AmazonEKSNodeRole`, `eks-alb-role` + `eks-alb-policy` (IRSA), `efs-csi-driver-role`
- GitOps: `nginx-demo` app + ALB Ingress (HTTP→HTTPS, ACM wildcard) + ALB ServiceAccount
- Helm: `aws-load-balancer-controller` + `aws-efs-csi-driver` in `kube-system`
- Storage: `efs-sc` + PV `grafana-efs` (EFS `fs-0ddb254be08c6267a` via AP 472:472)
- Grafana x2 in `monitoring` on shared EFS, live at `https://grafana.azubisuccess.space`
- Terraform: `terraform/networking/` + `terraform/eks/` declarative copies
