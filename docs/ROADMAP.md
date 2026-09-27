# Roadmap — rebuild everything step by step from the console

Follow top to bottom to reproduce the whole `eks-lab` setup.
Region: `us-west-1`. Cluster: `eks-lab` (1.36). Account: `195675606509`.

Prerequisites on your machine:

```bash
aws --version; kubectl version --client; helm version
aws sts get-caller-identity
```

Sources:
- https://docs.aws.amazon.com/eks/latest/userguide/lbc-helm.html (ALB controller)

---

## Step 0 — Node IAM role + node group ✅ done

Create the node role first, attach its policies, then create the node group
using it. Use `t3.small` or larger — `t3.micro` (1 GB RAM) is too small for
modern EKS and fails with `NodeCreationFailure`.

```bash
# 1. Create the node role (trusted by EC2)
aws iam create-role --role-name AmazonEKSNodeRole \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
  --description "Node IAM role for eks-lab"

# 2. Attach the 3 mandatory node policies
aws iam attach-role-policy --role-name AmazonEKSNodeRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy
aws iam attach-role-policy --role-name AmazonEKSNodeRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy
aws iam attach-role-policy --role-name AmazonEKSNodeRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly
aws iam list-attached-role-policies --role-name AmazonEKSNodeRole

# 3. Create the node group with that role
aws eks create-nodegroup --region us-west-1 \
  --cluster-name eks-lab --nodegroup-name ng-eks \
  --node-role arn:aws:iam::195675606509:role/AmazonEKSNodeRole \
  --subnets subnet-035bd6840b31e5205 subnet-0f6034326efbaa2ae \
  --instance-types t3.small --ami-type AL2023_x86_64_STANDARD \
  --scaling-config minSize=2,maxSize=2,desiredSize=2 --disk-size 20
aws eks wait nodegroup-active --region us-west-1 \
  --cluster-name eks-lab --nodegroup-name ng-eks
```

Verify: `aws eks describe-nodegroup --region us-west-1 --cluster-name eks-lab
--nodegroup-name ng-eks` shows `ACTIVE` with no health issues.

---

## Step 1 — IAM for the AWS Load Balancer Controller ✅ done

`eks-alb-policy` already existed (the LB Controller policy). Create the IRSA role:

```bash
# Trust policy (/tmp/alb-trust.json): OIDC provider
# oidc.eks.us-west-1.amazonaws.com/id/9F997EDF8DCA5769A4464EA85CAD9E1C
# limited to system:serviceaccount:kube-system:aws-load-balancer-controller
aws iam create-role --role-name eks-alb-role \
  --assume-role-policy-document file:///tmp/alb-trust.json \
  --description "IAM role for AWS Load Balancer Controller on eks-lab"
aws iam attach-role-policy --role-name eks-alb-role \
  --policy-arn arn:aws:iam::195675606509:policy/eks-alb-policy
```

Result: `arn:aws:iam::195675606509:role/eks-alb-role`.

---

## Step 2 — ServiceAccount via GitOps ✅ done

In repo `eks-gitops`, file `manifests/alb/serviceaccount.yaml`:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: aws-load-balancer-controller
  namespace: kube-system
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::195675606509:role/eks-alb-role
automountServiceAccountToken: true
```

Plus `manifests/alb/kustomization.yaml`, wired into `manifests/kustomization.yaml`.
Validate, commit, push — GitHub Actions applies it:

```bash
kubectl kustomize manifests/ > /tmp/rendered.yaml
kubectl apply --dry-run=client -f /tmp/rendered.yaml
git add manifests/alb manifests/kustomization.yaml
git commit -m "Add ALB controller ServiceAccount with IRSA"
git push origin main
kubectl -n kube-system get sa aws-load-balancer-controller -o yaml
```

---

## Step 3 — Install the ALB controller with Helm ✅ done

Reuses the GitOps SA (`create=false`):

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
```

Reference copy of the chart as plain YAML (manual use only, NOT applied by CI
because the CI role can't manage ClusterRoles/webhooks and objects are Helm-owned):

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

---

## Step 4 — Tag subnets for ALB discovery ✅ done

Without these tags the controller can't pick subnets for load balancers.

```bash
aws ec2 create-tags --region us-west-1 \
  --resources subnet-0aa1f2e4e1e684c22 subnet-06a76730006f45c54 \
  --tags Key=kubernetes.io/role/elb,Value=1 Key=kubernetes.io/cluster/eks-lab,Value=shared
aws ec2 create-tags --region us-west-1 \
  --resources subnet-035bd6840b31e5205 subnet-0f6034326efbaa2ae \
  --tags Key=kubernetes.io/role/internal-elb,Value=1 Key=kubernetes.io/cluster/eks-lab,Value=shared
```

Public subnets → `elb=1` (internet-facing ALBs), private → `internal-elb=1`.

---

## Step 5 — Expose nginx through the ALB ✅ done

`manifests/nginx/ingress.yml` (internet-facing, class `alb`, target-type `ip`,
`/` → `nginx:80`) wired into `manifests/nginx/kustomization.yaml`,
plus Service flipped `LoadBalancer` → `ClusterIP`. Commit, push, verify:

```bash
git add manifests/nginx/ingress.yml manifests/nginx/kustomization.yaml manifests/nginx/service.yaml
git commit -m "Add nginx ALB Ingress, Service to ClusterIP"
git push origin main
kubectl -n nginx-demo get svc nginx -o wide            # TYPE=ClusterIP
kubectl -n nginx-demo describe ingress nginx           # backend nginx:80 with pod IPs
curl http://<ALB-hostname>/                            # Welcome to nginx!
```

Live ALB: `k8s-nginxdem-nginx-98f1f39520-324967465.us-west-1.elb.amazonaws.com`.

---

## Step 6 — Reverse proxy to many services (multi-FQDN) 🔜 next

One ALB → nginx picks backend by `Host` header (`server_name` blocks).
Plan (placeholders first, HTTP first):
1. Demo backends `manifests/demos/api` (`demo-api` ns, :8080) and
   `manifests/demos/shop` (`demo-shop` ns, :3000).
2. `manifests/nginx/proxy-config.yaml` ConfigMap: `api.example.com` → demo-api,
   `shop.example.com` → demo-shop, default → welcome page; mount over
   `/etc/nginx/conf.d/default.conf` in the nginx Deployment.
3. Push via GitOps; test without DNS: `curl -H "Host: api.example.com" http://<ALB>/`.
4. Later: real FQDNs (DNS → ALB), ACM certs + `listen-ports 443` on the Ingress.

---

## Step 7 — EFS filesystem + access point ✅ done (filesystem provisioned)

You will never get an "IP to mount" — EFS mounts by **DNS name**:

```
fs-0ddb254be08c6267a.efs.us-west-1.amazonaws.com:/
```

Live filesystem: `fs-0ddb254be08c6267a` (available, encrypted, elastic
throughput), mount targets in both AZs. Requirements: mount targets in the
private subnets, SG open for TCP 2049 from the node/cluster SG.

Grafana runs as uid/gid `472`, so its access point must enforce that
(the console-made `fsap-0a2d1fcce9bf35497` has no POSIX user — don't use it):

```bash
aws efs create-access-point --region us-west-1 \
  --file-system-id fs-0ddb254be08c6267a \
  --posix-user '{"Uid":472,"Gid":472}' \
  --root-directory '{"Path":"/grafana","CreationInfo":{"OwnerUid":472,"OwnerGid":472,"Permissions":"700"}}' \
  --tags Key=Name,Value=grafana-472
```

Result: `fsap-088c8c16707025698` (`available`, 472:472).
Why not S3: Grafana's SQLite database needs POSIX file locking — S3 can't host it.

---

## Step 8 — EFS CSI driver ✅ done

```bash
# IRSA role for the controller SA
aws iam create-role --role-name efs-csi-driver-role \
  --assume-role-policy-document file:///tmp/efs-csi-trust.json \
  --description "IRSA role for EFS CSI driver on eks-lab"
aws iam attach-role-policy --role-name efs-csi-driver-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonEFSCSIDriverPolicy

helm repo add aws-efs-csi-driver https://kubernetes-sigs.github.io/aws-efs-csi-driver/
helm repo update
helm upgrade --install aws-efs-csi-driver aws-efs-csi-driver/aws-efs-csi-driver \
  -n kube-system \
  --set controller.serviceAccount.annotations."eks\.amazonaws\.com/role-arn"=arn:aws:iam::195675606509:role/efs-csi-driver-role
kubectl -n kube-system get pods -l app.kubernetes.io/name=aws-efs-csi-driver
```

Gotcha we hit: leftover RBAC/SAs from a partial install blocked Helm
("exists and cannot be imported"). Fix: label
`app.kubernetes.io/managed-by=Helm` + annotate
`meta.helm.sh/release-name/aws-efs-csi-driver`,
`meta.helm.sh/release-namespace/kube-system` on each leftover, retry.

---

## Step 9 — Grafana on EFS in `monitoring` 🔜 next (in progress)

1. Manual once (cluster-scoped, CI role can't create these): StorageClass
   `efs-sc` (provisioner `efs.csi.aws.com`) + static PV
   (`volumeHandle: fs-0ddb254be08c6267a::fsap-088c8c16707025698`).
2. Via GitOps (`manifests/grafana/`, namespace `monitoring`): PVC on the PV,
   admin Secret, Deployment **2 replicas** sharing the EFS volume at
   `/var/lib/grafana`, ClusterIP Service :3000.
3. Nginx URL block (placeholder FQDN, you edit later): `server_name
   grafana.example.com` → `proxy_pass http://grafana.monitoring.svc:3000`.
4. Verify: PVC `Bound`, both pods `Running`, write test file visible from both
   pods, `curl -H "Host: grafana.example.com" http://<ALB>/login` → 200.
5. ⚠️ Heads-up: 2 replicas share one SQLite db over NFS — fine for the lab,
   but concurrent writes can hit "database is locked". If that bites, drop to
   1 replica or move Grafana to an external DB (RDS Postgres).

---

## Installed

- EKS 1.36 + Managed NodeGroup `ng-eks` (t3.small x2)
- AWS LB Controller Helm `3.5.0` + EFS CSI driver (both in `kube-system`)
- IAM: fixed `AmazonEKSNodeRole`, `eks-alb-role` + `eks-alb-policy`, `efs-csi-driver-role`
- Subnet tags for ALB discovery; networking as code: `terraform/networking/`
- GitOps: nginx + ALB Ingress (live, HTTP 200), controller manifest reference
- EFS `fs-0ddb254be08c6267a` + access point `fsap-088c8c16707025698` (472:472)

## TODO

- [x] Install ALB controller, tag subnets, expose nginx
- [x] Provision EFS + access point, install CSI driver
- [ ] Grafana manifests (`monitoring`, PVC, 2 replicas, Service, nginx URL block)
- [ ] Multi-FQDN nginx proxy (demo backends, placeholder FQDNs)
- [ ] Real FQDNs: DNS → ALB, ACM certs + HTTPS on Ingress
