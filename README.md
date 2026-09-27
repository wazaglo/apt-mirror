# eks-gitops

Kubernetes manifests for an EKS cluster, applied by GitHub Actions.

## Layout

```
eks-gitops/
├── manifests/
│   ├── nginx/      # namespace, deployment, service
│   └── app2/       # deployment, service
└── .github/
    └── workflows/
        └── deploy.yml
```

## GitHub OIDC trust (already created in AWS)

Account: `195675606509`

| Resource | ARN / value |
| --- | --- |
| OIDC provider | `arn:aws:iam::195675606509:oidc-provider/token.actions.githubusercontent.com` |
| IAM role | `arn:aws:iam::195675606509:role/eks-gitops-github-actions` |
| Attached policy | `AmazonEKSClusterPolicy` |

Trust policy on the role:

```json
{
  "Effect": "Allow",
  "Principal": {
    "Federated": "arn:aws:iam::195675606509:oidc-provider/token.actions.githubusercontent.com"
  },
  "Action": "sts:AssumeRoleWithWebIdentity",
  "Condition": {
    "StringEquals": {
      "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
    },
    "StringLike": {
      "token.actions.githubusercontent.com:sub": "repo:wazaglo/eks-gitops:*"
    }
  }
}
```

The `sub` condition is scoped to this repo only, so no other workflow can assume the role.

## Remaining setup

```bash
# repo secret + variables
echo -n 'arn:aws:iam::195675606509:role/eks-gitops-github-actions' \
  | gh secret set AWS_DEPLOY_ROLE_ARN --repo wazaglo/eks-gitops
gh variable set EKS_CLUSTER_NAME --repo wazaglo/eks-gitops
gh variable set AWS_REGION --repo wazaglo/eks-gitops

# grant the role access to the cluster (one time, per cluster)
aws eks update-access-entry --region <region> --cluster-name <cluster> \
  --principal arn:aws:iam::195675606509:role/eks-gitops-github-actions \
  --type IAM_ROLE --access-scope-type cluster
```

## Required secrets / variables

| Name | Kind | Value |
| --- | --- | --- |
| `AWS_DEPLOY_ROLE_ARN` | secret | `arn:aws:iam::195675606509:role/eks-gitops-github-actions` |
| `EKS_CLUSTER_NAME` | variable | EKS cluster name |
| `AWS_REGION` | variable | AWS region (default `us-east-1`) |

## Deploy

Push to `main` (or run the workflow manually). The workflow assumes the AWS role,
updates the kubeconfig, and runs `kubectl apply -f manifests/`.

The `nginx` Service is type `LoadBalancer`, so EKS provisions an external IP:

```bash
kubectl -n nginx-demo get svc nginx -w
```
