# Roadmap / Operations Log

Single place tracking what is installed and what was done on `eks-lab` (us-west-1).
Update this file with every change.

## Cluster

- Name: `eks-lab`, region `us-west-1`, version `1.36`, status `ACTIVE`
- VPC `vpc-0bab80c57b59d53be`, private subnets with NAT (networking verified OK)
- OIDC provider: `oidc.eks.us-west-1.amazonaws.com/id/9F997EDF8DCA5769A4464EA85CAD9E1C`

## Done

### 2026-09-27 — Fix NodeGroup `ng-eks` (NodeCreationFailure)
- Symptom: `Instances failed to join` (`i-0c6e29d50078a545d`, `i-0d59ea52d33db6bfc`)
- Root cause: `AmazonEKSNodeRole` had 0 attached policies
- Fixed: attached `AmazonEKSWorkerNodePolicy`, `AmazonEKS_CNI_Policy`, `AmazonEC2ContainerRegistryReadOnly`
- Deleted failed `ng-eks` (t3.micro) and recreated with `t3.small`, AL2023, 2x nodes
- Status now: `ACTIVE`, no health issues

### 2026-09-27 — ALB IAM (IRSA)
- Policy `eks-alb-policy` (`arn:aws:iam::195675606509:policy/eks-alb-policy`) — AWS LB Controller policy
- Role `eks-alb-role` (`arn:aws:iam::195675606509:role/eks-alb-role`)
- Trust: OIDC `us-west-1` limited to `system:serviceaccount:kube-system:aws-load-balancer-controller`

### 2026-09-27 — GitOps ServiceAccount
- Added `manifests/alb/serviceaccount.yaml` (`kube-system/aws-load-balancer-controller` + `eks.amazonaws.com/role-arn`)
- Added `manifests/alb/kustomization.yaml`, wired `alb` into `manifests/kustomization.yaml`
- Validated: `kubectl kustomize` + `dry-run=client` pass
- Pushed in `64cf55e`

### Earlier — GitOps baseline
- `bootstrap/rbac.yaml`: `eks-gitops-deployer` ClusterRole + Binding to group `eks-gitops-deployers`
- `manifests/nginx/`: namespace `nginx-demo`, deployment (2x nginx), ClusterIP service
- `.github/workflows/deploy.yml`: validate (PR) + deploy to EKS via OIDC role `AWS_DEPLOY_ROLE_ARN`

## Installed

- EKS 1.36 + Managed NodeGroup `ng-eks` (t3.small x2)
- AWS LB Controller Helm chart `3.5.0` in `kube-system` (reuses GitOps SA, IRSA `eks-alb-role`)
- Controller manifest reference: `manifests/alb-controller/controller.yaml` (manual use only)
- Subnet tags for ALB discovery: public `elb=1`, private `internal-elb=1`, all `cluster/eks-lab=shared`
- Networking as code: `terraform/networking/` (VPC, IGW, subnets, NAT, route tables)
- nginx-demo app via GitOps

## Next / TODO

- [x] Install AWS Load Balancer Controller Helm chart using existing SA (`createServiceAccount: false`)
- [x] Tag subnets for ALB discovery (`kubernetes.io/role/elb`, `kubernetes.io/role/internal-elb`)
- [ ] Add test Ingress for nginx + verify ALB provisioning + tags
- [ ] Add ClusterIP -> Ingress migration notes
- [ ] Consider `t3.medium` if pods get CPU/memory pressure
