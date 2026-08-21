output "entra_application_client_id" {
  description = "Client ID of the Terraform-managed OBO app registration."
  value       = azuread_application.obo.client_id
}

output "entra_tenant_id" {
  description = "Tenant containing the Terraform-managed OBO app registration."
  value       = data.azurerm_client_config.current.tenant_id
}

output "mcp_audience" {
  description = "Expected aud claim in Entra v2 access tokens sent to the MCP server."
  value       = azuread_application.obo.client_id
}

output "mcp_delegated_scope" {
  description = "Delegated OAuth scope clients must request."
  value       = "${azuread_application_identifier_uri.obo.identifier_uri}/access_as_user"
}
