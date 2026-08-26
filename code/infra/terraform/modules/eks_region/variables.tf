variable "region" {
  type = string
}

variable "cluster_name" {
  type = string
}

variable "cpu_node_instance_type" {
  type = string
}

variable "router_tier_instance_type" {
  type = string
}

variable "generation_tier_instance_type" {
  type = string
}

variable "generation_tier_min_replicas" {
  type = number
}

variable "tags" {
  type    = map(string)
  default = {}
}
