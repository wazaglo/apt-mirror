# Networking (us-west-1 / eks-lab)

Declarative copy of the live VPC networking. Live IDs are noted in `main.tf`
for import reference — this stack creates NEW resources if applied as-is.

```bash
cd terraform/networking
terraform init
terraform validate
terraform plan -var region=us-west-1 -var cluster_name=eks-lab
```

To adopt the live VPC instead of recreating, use `terraform import` per
resource (VPC, IGW, subnets, EIPs, NATs, route tables) before `apply`.
