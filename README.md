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

## Deploy

Push to `main` (or run the workflow manually). The workflow assumes the AWS role,
updates the kubeconfig, and runs `kubectl apply -f manifests/`.

The `nginx` Service is type `LoadBalancer`, so EKS provisions an external IP:

```bash
kubectl -n nginx-demo get svc nginx -w
```
