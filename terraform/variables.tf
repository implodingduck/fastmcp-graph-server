variable "subscription_id" {
  type      = string
  sensitive = true
}

variable "location" {
  type    = string
  default = "East US"
}

variable "gh_repo" {
  type = string
}

variable "entra_tenant_id" {
  type = string
}

variable "entra_client_id" {
  type = string
}

variable "mcp_audience" {
  type = string
}

variable "entra_client_secret_key_vault_secret_uri" {
  type        = string
  description = "Versioned or versionless Key Vault secret URI containing the Entra client secret."
}
