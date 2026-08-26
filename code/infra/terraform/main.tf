# Reference skeleton only — see infra/README.md. Not a working root module
# (no backend block, no provider version lock, no VPC/subnet resources).

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# INFRA-1.1: one cluster per region, not one global cluster.
module "eks_cluster" {
  source   = "./modules/eks_region"
  for_each = toset(var.regions)

  region       = each.value
  cluster_name = "${var.cluster_name_prefix}-${each.value}"

  # INFRA-1.2: CPU pool (API/Airflow/Qdrant/mesh) sized separately from GPU pools.
  cpu_node_instance_type = "m6i.xlarge"

  router_tier_instance_type     = var.router_tier_instance_type
  generation_tier_instance_type = var.generation_tier_instance_type
  generation_tier_min_replicas  = var.generation_tier_min_replicas

  tags = {
    Project     = "finserv-compliance-assistant"
    DataResidency = each.value # SEC-1.1: tags the cluster with the jurisdiction it may hold data for
  }
}

# INFRA-3: cost-guardrail budget alert.
resource "aws_budgets_budget" "gpu_spend_alert" {
  for_each     = toset(var.regions)
  name         = "finserv-compliance-${each.value}-gpu-budget"
  budget_type  = "COST"
  limit_amount = tostring(var.cost_alert_threshold_usd / length(var.regions))
  limit_unit   = "USD"
  time_unit    = "MONTHLY"
}
