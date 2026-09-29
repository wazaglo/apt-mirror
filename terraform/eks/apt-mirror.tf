locals {
  apt_mirror = {
    file_system_id = "fs-0b0491ead2bac1c8c"
    creation_token = "console-b5153c85-cbe5-4165-bc10-910e314ca69a"
    kms_key_id     = "arn:aws:kms:us-west-1:195675606509:key/ac7337e1-aaa7-497d-bbff-58eac5315b84"

    backup_status = "DISABLED"

    access_points = {
      debian = {
        id   = "fsap-020b79f4588c2d482"
        name = "debian12-mirror"
        path = "/mirrors/debian/12"
      }
      ubuntu = {
        id   = "fsap-02586212ea002c468"
        name = "ubuntu24-mirror"
        path = "/mirrors/ubuntu/24.04"
      }
    }

    mount_targets = {
      "us-west-1a" = {
        id        = "fsmt-0a81dbd033aa90f9a"
        subnet_id = var.private_subnet_ids[0]
        ip        = "10.0.11.96"
      }
      "us-west-1c" = {
        id        = "fsmt-039348036c509e7ba"
        subnet_id = var.private_subnet_ids[1]
        ip        = "10.0.12.214"
      }
    }

    # Live cluster security group attached to the mount targets by AWS. The
    # mount targets themselves use the NFS group below; that group restricts
    # TCP/2049 to the cluster group rather than the whole VPC CIDR.
    eks_cluster_security_group_id = "sg-0306e5045f5a22414"

    nfs_security_group = {
      id          = "sg-05b0abc4fd877cd14"
      name        = "eks-mirror-efs-sg"
      description = "Allow EKS nodes to access the efs "
    }
  }
}

import {
  to = aws_efs_file_system.apt_mirror
  id = "fs-0b0491ead2bac1c8c"
}

import {
  to = aws_efs_backup_policy.apt_mirror
  id = "fs-0b0491ead2bac1c8c"
}

import {
  to = aws_efs_access_point.apt_mirror["debian"]
  id = "fsap-020b79f4588c2d482"
}

import {
  to = aws_efs_access_point.apt_mirror["ubuntu"]
  id = "fsap-02586212ea002c468"
}

import {
  to = aws_efs_mount_target.apt_mirror["us-west-1a"]
  id = "fsmt-0a81dbd033aa90f9a"
}

import {
  to = aws_efs_mount_target.apt_mirror["us-west-1c"]
  id = "fsmt-039348036c509e7ba"
}

import {
  to = aws_security_group.apt_mirror_nfs
  id = "sg-05b0abc4fd877cd14"
}

resource "aws_efs_file_system" "apt_mirror" {
  creation_token   = local.apt_mirror.creation_token
  encrypted        = true
  kms_key_id       = local.apt_mirror.kms_key_id
  performance_mode = "generalPurpose"
  throughput_mode  = "elastic"

  protection {
    replication_overwrite = "ENABLED"
  }

  tags = {
    Name = "archcloud-mirror-efs"
  }
}

resource "aws_efs_backup_policy" "apt_mirror" {
  file_system_id = aws_efs_file_system.apt_mirror.id

  backup_policy {
    status = local.apt_mirror.backup_status
  }
}

resource "aws_efs_access_point" "apt_mirror" {
  for_each       = local.apt_mirror.access_points
  file_system_id = aws_efs_file_system.apt_mirror.id

  posix_user {
    uid = 1000
    gid = 1000
  }

  root_directory {
    path = each.value.path

    creation_info {
      owner_uid   = 1000
      owner_gid   = 1000
      permissions = "0755"
    }
  }

  tags = {
    Name = each.value.name
  }
}

resource "aws_efs_mount_target" "apt_mirror" {
  for_each       = local.apt_mirror.mount_targets
  file_system_id = aws_efs_file_system.apt_mirror.id
  subnet_id      = each.value.subnet_id
  ip_address     = each.value.ip
  security_groups = [
    aws_security_group.apt_mirror_nfs.id,
  ]
}

resource "aws_security_group" "apt_mirror_nfs" {
  name        = local.apt_mirror.nfs_security_group.name
  description = local.apt_mirror.nfs_security_group.description
  vpc_id      = var.vpc_id

  tags = {}
}

resource "aws_vpc_security_group_ingress_rule" "apt_mirror_nfs" {
  security_group_id            = aws_security_group.apt_mirror_nfs.id
  referenced_security_group_id = local.apt_mirror.eks_cluster_security_group_id
  ip_protocol                  = "tcp"
  from_port                    = 2049
  to_port                      = 2049
}

resource "aws_vpc_security_group_egress_rule" "apt_mirror_all_outbound" {
  security_group_id = aws_security_group.apt_mirror_nfs.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

output "apt_mirror_file_system_id" {
  value = aws_efs_file_system.apt_mirror.id
}

output "apt_mirror_access_point_ids" {
  value = {
    for name, access_point in aws_efs_access_point.apt_mirror : name => access_point.id
  }
}

output "apt_mirror_mount_target_ids" {
  value = {
    for zone, mount_target in aws_efs_mount_target.apt_mirror : zone => mount_target.id
  }
}
