# EKS cluster (eks-lab, 1.36, us-west-1)

Declarative copy of the live cluster: IAM roles, cluster (public+private
endpoint, API auth mode), OIDC provider for IRSA, managed node group
`ng-eks` (t3.small x2, AL2023), 8 add-ons pinned to live versions, and the
3 access entries (node role, GitHub deploy role, admin user).

```bash
cd terraform/eks
terraform init
terraform validate
terraform plan -var region=us-west-1
```

To adopt live resources instead of recreating, use the `import` blocks in
`apt-mirror.tf` for the mirror filesystem, backup policy, access points, mount
targets, and NFS security group before `apply`. For older resources, `terraform
import` each one (cluster, roles, node group, OIDC provider, add-ons, access
entries) before `apply`. Applying as-is creates a SECOND set of roles with the
same names — it will fail on name clashes until imports are done.

⚠️ `aws-efs-csi-driver` exists live BOTH as an EKS addon (v3.4.2) and a Helm
release (3.5.0). Pick one manager before applying: either drop the addon from
`local.addons` (keep Helm) or `helm uninstall` it (keep the addon).
