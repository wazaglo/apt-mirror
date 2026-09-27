# eks-gitops

Kubernetes manifests for an EKS cluster, applied by GitHub Actions.

## Layout

```
eks-gitops/
├── manifests/
│   ├── kustomization.yaml   # lists every app in this cluster
│   └── nginx/               # namespace, deployment, service
└── .github/
    └── workflows/
        └── deploy.yml
```

## Deploy

Push to `main` (or run the workflow manually). The workflow assumes the AWS role,
updates the kubeconfig, renders `manifests/` with kustomize, then applies it.

The `nginx` Service is type `LoadBalancer`, so EKS provisions an external IP:

```bash
kubectl -n nginx-demo get svc nginx -w
```

## Add another app

1. Create `manifests/<app>/` with the manifest files and a `kustomization.yaml` listing them.
2. Add `- <app>` to `resources` in `manifests/kustomization.yaml`.
3. Push.

Nothing in `deploy.yml` needs to change — the workflow picks up every directory
listed in the root kustomization and waits on each namespace it finds.
