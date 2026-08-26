# INFRA-1.1: one cluster per region — SEC-1.1 region pinning means these
# three are deployed independently, never sharing a VPC or peering by default.

variable "regions" {
  description = "One EKS cluster per operating market region (SEC-1.1)."
  type        = list(string)
  default     = ["ap-south-1", "eu-central-1", "us-east-1"]
}

variable "cluster_name_prefix" {
  type    = string
  default = "finserv-compliance"
}

variable "router_tier_instance_type" {
  description = "INFRA-1.2 GPU pool A: 8B router/classifier + embedding/rerank inference."
  type        = string
  default     = "g5.2xlarge"
}

variable "generation_tier_instance_type" {
  description = "INFRA-1.2 GPU pool B: 70B generation model, AWQ-quantized, tensor-parallel."
  type        = string
  default     = "g5.12xlarge"
}

variable "generation_tier_min_replicas" {
  description = "INFRA-2.3: scale-to-floor (never zero) — cold-starting a multi-GPU tensor-parallel model takes minutes."
  type        = number
  default     = 1
}

variable "cost_alert_threshold_usd" {
  description = "INFRA-3: hard alarm at 120% of the reserved-optimized estimate (~$18,000)."
  type        = number
  default     = 21600
}
