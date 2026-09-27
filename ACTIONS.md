# Actions Log

What was done on `eks-lab` (us-west-1, 1.36) and how to repeat it.
No commit history here — just actions and commands.

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

## Installed

- EKS `eks-lab` 1.36 + Managed NodeGroup `ng-eks` (t3.small x2, AL2023)
- IAM: fixed `AmazonEKSNodeRole`, `eks-alb-role` + `eks-alb-policy` (IRSA)
- GitOps: `nginx-demo` app + ALB ServiceAccount
- Helm: `aws-load-balancer-controller` in `kube-system` reusing the GitOps SA
