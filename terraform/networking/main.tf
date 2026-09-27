# Recreates the live eks-lab VPC networking in us-west-1.
# Live IDs (for import reference only, not hardcoded):
#   VPC  vpc-0bab80c57b59d53be (10.0.0.0/16)
#   IGW  igw-0365d0d37b6211f48
#   Public:  subnet-0aa1f2e4e1e684c22 (10.0.1.0/24, 1a),
#            subnet-06a76730006f45c54 (10.0.2.0/24, 1c)
#   Private: subnet-035bd6840b31e5205 (10.0.11.0/24, 1a),
#            subnet-0f6034326efbaa2ae (10.0.12.0/24, 1c)
#   NATs: nat-00e6923049c667c66 (in public1), nat-09759605f5da6c48b (in public2)

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = var.vpc_name
  }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "eks-lab-vpc-igw"
  }
}

# --- Subnets (with ALB discovery tags) ---

resource "aws_subnet" "public1" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "us-west-1a"
  map_public_ip_on_launch = false

  tags = {
    Name                                        = "eks-lab-vpc-subnet-public1-us-west-1a"
    "kubernetes.io/role/elb"                    = "1"
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
  }
}

resource "aws_subnet" "public2" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.2.0/24"
  availability_zone       = "us-west-1c"
  map_public_ip_on_launch = false

  tags = {
    Name                                        = "eks-lab-vpc-subnet-public2-us-west-1c"
    "kubernetes.io/role/elb"                    = "1"
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
  }
}

resource "aws_subnet" "private1" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.11.0/24"
  availability_zone = "us-west-1a"

  tags = {
    Name                                        = "eks-lab-vpc-subnet-private1-us-west-1a"
    "kubernetes.io/role/internal-elb"           = "1"
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
  }
}

resource "aws_subnet" "private2" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.12.0/24"
  availability_zone = "us-west-1c"

  tags = {
    Name                                        = "eks-lab-vpc-subnet-private2-us-west-1c"
    "kubernetes.io/role/internal-elb"           = "1"
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
  }
}

# --- NAT (one per AZ, matching live layout) ---

resource "aws_eip" "nat1" {
  domain = "vpc"

  tags = {
    Name = "eks-lab-vpc-eip-public1-us-west-1a"
  }
}

resource "aws_eip" "nat2" {
  domain = "vpc"

  tags = {
    Name = "eks-lab-vpc-eip-public2-us-west-1c"
  }
}

resource "aws_nat_gateway" "nat1" {
  allocation_id = aws_eip.nat1.id
  subnet_id     = aws_subnet.public1.id

  tags = {
    Name = "eks-lab-vpc-nat-public1-us-west-1a"
  }
}

resource "aws_nat_gateway" "nat2" {
  allocation_id = aws_eip.nat2.id
  subnet_id     = aws_subnet.public2.id

  tags = {
    Name = "eks-lab-vpc-nat-public2-us-west-1c"
  }
}

# --- Route tables ---

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "10.0.0.0/16"
    gateway_id = "local"
  }

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "eks-lab-vpc-rt-public"
  }
}

resource "aws_route_table" "private1" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "10.0.0.0/16"
    gateway_id = "local"
  }

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.nat1.id
  }

  tags = {
    Name = "eks-lab-vpc-rt-private1-us-west-1a"
  }
}

resource "aws_route_table" "private2" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "10.0.0.0/16"
    gateway_id = "local"
  }

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.nat2.id
  }

  tags = {
    Name = "eks-lab-vpc-rt-private2-us-west-1c"
  }
}

resource "aws_route_table_association" "public1" {
  subnet_id      = aws_subnet.public1.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "public2" {
  subnet_id      = aws_subnet.public2.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private1" {
  subnet_id      = aws_subnet.private1.id
  route_table_id = aws_route_table.private1.id
}

resource "aws_route_table_association" "private2" {
  subnet_id      = aws_subnet.private2.id
  route_table_id = aws_route_table.private2.id
}
