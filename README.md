# eks-gitops

Nginx on EKS via GitHub Actions + Kustomize. This repo contains only the nginx manifests.

## Layout

```
eks-gitops/
├── bootstrap/
│   └── rbac.yaml           # one-time: lets the CI role deploy
├── manifests/
│   ├── kustomization.yaml  # points at nginx only
│   └── nginx/              # namespace, deployment, service (ClusterIP)
└── .github/
    └── workflows/
        └── deploy.yml
```

## Prerequisites

- EKS cluster with GitHub OIDC (IRSA) configured.
- GitHub Actions secrets / variables:
  - Secret `AWS_DEPLOY_ROLE_ARN` — IAM role the workflow assumes.
  - Variable `AWS_REGION` — e.g. `eu-central-1`.
  - Variable `EKS_CLUSTER_NAME` — your cluster name.
- The IAM role must be mapped to the `eks-gitops-deployers` group
  (EKS access entry), which `bootstrap/rbac.yaml` binds to the deployer ClusterRole.

## Bootstrap (once per cluster)

The pipeline never applies `bootstrap/` itself, so a compromised workflow
cannot widen its own permissions:

```bash
kubectl apply -f bootstrap/rbac.yaml
```

## Deploy

Push to `main` (or run the workflow manually). The workflow assumes the AWS role,
updates kubeconfig, renders `manifests/` with kustomize, applies it, then waits on
`deployment/nginx` in `nginx-demo`. Pull requests only run the
validate job (kustomize build + client-side dry run) and never touch the cluster.

## Access

The `nginx` Service is type `ClusterIP` — internal only, no external load balancer:

```bash
kubectl -n nginx-demo get svc nginx
kubectl -n nginx-demo port-forward svc/nginx 8080:80
# then open http://localhost:8080
```

## Images

Public Docker Hub `nginx` image, no registry credentials needed.
