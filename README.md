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

## Required secrets / variables

| Name | Kind | Value |
| --- | --- | --- |
| `AWS_DEPLOY_ROLE_ARN` | secret | IAM role assumable by the GitHub Actions OIDC provider |
| `EKS_CLUSTER_NAME` | variable | EKS cluster name |
| `AWS_REGION` | variable | AWS region (default `us-east-1`) |

## Deploy

Push to `main` (or run the workflow manually). The workflow assumes the AWS role,
updates the kubeconfig, and runs `kubectl apply -f manifests/`.

The `nginx` Service is type `LoadBalancer`, so EKS provisions an external IP:

```bash
kubectl -n nginx-demo get svc nginx -w
```

### Trusting GitHub OIDC

Add the repo to the IAM role's trust policy:

```json
{
  "Effect": "Allow",
  "Principal": {
    "Federated": "arn:aws:iam::<account-id>:oidc-provider/token.actions.githubusercontent.com"
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
