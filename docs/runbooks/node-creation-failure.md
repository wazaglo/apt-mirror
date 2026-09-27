# Runbook: NodeCreationFailure

**Symptom**

EKS console or `describe-nodegroup`:

```json
{"code": "NodeCreationFailure", "message": "Instances failed to join the kubernetes cluster"}
```

**Cause (99% of the time):** the node IAM role has no policies, or lacks
`AmazonEKSWorkerNodePolicy`. Instances boot, `kubelet` can't authenticate to
the API server, and EKS terminates them. It also fires when nodes can't
reach the API endpoint (no NAT, no VPC endpoint) or the launch template /
userdata is malformed.

**Diagnose**

```bash
aws iam list-attached-role-policies --role-name AmazonEKSNodeRole
# expected: AmazonEKSWorkerNodePolicy, AmazonEKS_CNI_Policy, AmazonEC2ContainerRegistryReadOnly

# can the nodes reach the cluster + internet?
aws ec2 describe-route-tables --region us-west-1 --filters Name=vpc-id,Values=<vpc-id>
# private subnets need 0.0.0.0/0 -> nat-*
```

**Fix**

Policies are the usual cause:

```bash
aws iam attach-role-policy --role-name AmazonEKSNodeRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy
aws iam attach-role-policy --role-name AmazonEKSNodeRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy
aws iam attach-role-policy --role-name AmazonEKSNodeRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly
```

A node group in `CREATE_FAILED` cannot be repaired in place — recreate it:

```bash
aws eks delete-nodegroup --region us-west-1 --cluster-name eks-lab --nodegroup-name ng-eks
aws eks wait nodegroup-deleted --region us-west-1 --cluster-name eks-lab --nodegroup-name ng-eks
aws eks create-nodegroup --region us-west-1 --cluster-name eks-lab --nodegroup-name ng-eks \
  --node-role arn:aws:iam::195675606509:role/AmazonEKSNodeRole \
  --subnets subnet-035bd6840b31e5205 subnet-0f6034326efbaa2ae \
  --instance-types t3.small --ami-type AL2023_x86_64_STANDARD \
  --scaling-config minSize=2,maxSize=5,desiredSize=5 --disk-size 20
```

**Confirm**

```bash
aws eks describe-nodegroup --region us-west-1 --cluster-name eks-lab \
  --nodegroup-name ng-eks --query 'nodegroup.{status:status,health:health.issues}'
kubectl get nodes
```

Also inspect the instance before EKS reclaims it: SSM in, then
`journalctl -u kubelet` and `cat /var/log/cloud-init-output.log`.
