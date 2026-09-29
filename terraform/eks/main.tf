# Recreates eks-lab (1.36) as it exists live.
# Live references (for import, not hardcoded):
#   Cluster role  arn:aws:iam::195675606509:role/AmazonEKSClusterRole
#   OIDC issuer   https://oidc.eks.us-west-1.amazonaws.com/id/9F997EDF8DCA5769A4464EA85CAD9E1C
#   Cluster SG    sg-0306e5045f5a22414 (auto-created by EKS)

resource "aws_eks_cluster" "main" {
  name     = var.cluster_name
  version  = var.cluster_version
  role_arn = aws_iam_role.cluster.arn

  vpc_config {
    subnet_ids              = var.private_subnet_ids
    endpoint_private_access = true
    endpoint_public_access  = true
    public_access_cidrs     = ["0.0.0.0/0"]
  }

  access_config {
    authentication_mode = "API"
  }

  kubernetes_network_config {
    service_ipv4_cidr = "172.20.0.0/16"
    ip_family         = "ipv4"
  }

  upgrade_policy {
    support_type = "STANDARD"
  }

  depends_on = [aws_iam_role_policy_attachment.cluster_policy]
}

# OIDC provider for IRSA (eks-alb-role, efs-csi-driver-role trust this)
data "tls_certificate" "cluster" {
  url = aws_eks_cluster.main.identity[0].oidc[0].issuer
}

resource "aws_iam_openid_connect_provider" "cluster" {
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.cluster.certificates[0].sha1_fingerprint]
  url             = aws_eks_cluster.main.identity[0].oidc[0].issuer
}

resource "aws_eks_node_group" "main" {
  node_group_name = "ng-eks"
  cluster_name    = aws_eks_cluster.main.name
  version         = var.cluster_version
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.private_subnet_ids
  instance_types  = var.node_instance_types
  ami_type        = "AL2023_x86_64_STANDARD"
  capacity_type   = "ON_DEMAND"
  disk_size       = 20

  scaling_config {
    min_size     = var.node_scaling.min
    max_size     = var.node_scaling.max
    desired_size = var.node_scaling.desired
  }

  update_config {
    max_unavailable = 1
  }

  depends_on = [aws_iam_role_policy_attachment.node_policies]
}

# Add-ons pinned to live versions.
locals {
  addons = {
    coredns                   = "v1.14.3-eksbuild.23"
    kube-proxy                = "v1.36.0-eksbuild.25"
    vpc-cni                   = "v1.22.4-eksbuild.3"
    eks-pod-identity-agent    = "v1.3.10-eksbuild.3"
    eks-node-monitoring-agent = "v1.7.2-eksbuild.1"
    metrics-server            = "v0.9.0-eksbuild.11"
    external-dns              = "v0.23.0-eksbuild.1"
    # Manage aws-efs-csi-driver as an EKS addon only. A conflicting Helm release
    # would fight this addon over the same workloads.
    aws-efs-csi-driver = "v3.4.2-eksbuild.1"
  }
}

resource "aws_eks_addon" "all" {
  for_each      = local.addons
  cluster_name  = aws_eks_cluster.main.name
  addon_name    = each.key
  addon_version = each.value
}

# Access entries (auth mode API)
resource "aws_eks_access_entry" "node" {
  cluster_name  = aws_eks_cluster.main.name
  principal_arn = aws_iam_role.node.arn
  type          = "EC2_LINUX"
}

resource "aws_eks_access_entry" "deployer" {
  cluster_name      = aws_eks_cluster.main.name
  principal_arn     = var.deployer_role_arn
  type              = "STANDARD"
  kubernetes_groups = ["apt-mirror-deployers"]
}

resource "aws_eks_access_entry" "admin" {
  cluster_name  = aws_eks_cluster.main.name
  principal_arn = var.admin_user_arn
  type          = "STANDARD"
}

resource "aws_eks_access_policy_association" "admin" {
  cluster_name  = aws_eks_cluster.main.name
  principal_arn = var.admin_user_arn
  policy_arn    = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"

  access_scope {
    type = "cluster"
  }
}
