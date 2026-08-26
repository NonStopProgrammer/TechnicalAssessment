# Skeleton EKS module — see infra/README.md: illustrative shape only
# (provider/VPC/subnet wiring, remote state, and IAM are all omitted).

provider "aws" {
  region = var.region
  alias  = "region"
}

resource "aws_eks_cluster" "this" {
  provider = aws.region
  name     = var.cluster_name
  role_arn = "REPLACE_WITH_REAL_CLUSTER_ROLE_ARN"

  vpc_config {
    subnet_ids = [] # REPLACE: region-local subnets only — SEC-1.1 forbids cross-region networking here
  }

  tags = var.tags
}

# INFRA-1.2(a): CPU pool — API services, Airflow, Qdrant, mesh control plane.
resource "aws_eks_node_group" "cpu_pool" {
  provider        = aws.region
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "${var.cluster_name}-cpu"
  node_role_arn   = "REPLACE_WITH_REAL_NODE_ROLE_ARN"
  subnet_ids      = []
  instance_types  = [var.cpu_node_instance_type]

  scaling_config {
    min_size     = 2
    max_size     = 8
    desired_size = 3
  }
}

# INFRA-1.2(b) + INFRA-2.1: Karpenter provisions GPU capacity on demand in
# real usage; this managed node group is the illustrative floor only.
resource "aws_eks_node_group" "router_tier_gpu_pool" {
  provider        = aws.region
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "${var.cluster_name}-gpu-router"
  node_role_arn   = "REPLACE_WITH_REAL_NODE_ROLE_ARN"
  subnet_ids      = []
  instance_types  = [var.router_tier_instance_type]

  scaling_config {
    min_size     = 0 # INFRA-2.3: router tier can scale toward zero off-hours
    max_size     = 4
    desired_size = 1
  }
}

resource "aws_eks_node_group" "generation_tier_gpu_pool" {
  provider        = aws.region
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "${var.cluster_name}-gpu-generation"
  node_role_arn   = "REPLACE_WITH_REAL_NODE_ROLE_ARN"
  subnet_ids      = []
  instance_types  = [var.generation_tier_instance_type]

  scaling_config {
    min_size     = var.generation_tier_min_replicas # INFRA-2.3: never scale-to-zero, cold start blows the latency SLA
    max_size     = 5
    desired_size = var.generation_tier_min_replicas
  }
}
