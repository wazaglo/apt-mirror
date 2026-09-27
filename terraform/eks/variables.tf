variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-west-1"
}

variable "cluster_name" {
  type    = string
  default = "eks-lab"
}

variable "cluster_version" {
  type    = string
  default = "1.36"
}

variable "vpc_id" {
  description = "VPC hosting the cluster (see ../networking)"
  type        = string
  default     = "vpc-0bab80c57b59d53be"
}

variable "private_subnet_ids" {
  description = "Private subnets for nodes + API endpoint"
  type        = list(string)
  default = [
    "subnet-035bd6840b31e5205", # private1 us-west-1a
    "subnet-0f6034326efbaa2ae", # private2 us-west-1c
  ]
}

variable "node_instance_types" {
  type    = list(string)
  default = ["t3.small"]
}

variable "node_scaling" {
  type    = object({ min = number, max = number, desired = number })
  default = { min = 2, max = 2, desired = 2 }
}

variable "deployer_role_arn" {
  description = "GitHub Actions deploy role mapped to eks-gitops-deployers"
  type        = string
  default     = "arn:aws:iam::195675606509:role/eks-gitops-github-actions"
}

variable "admin_user_arn" {
  description = "IAM user kept as cluster admin"
  type        = string
  default     = "arn:aws:iam::195675606509:user/wazaglo"
}
