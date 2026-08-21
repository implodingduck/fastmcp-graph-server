data "azuread_service_principal" "microsoft_graph" {
  client_id = "00000003-0000-0000-c000-000000000000"
}

resource "random_uuid" "access_as_user_scope" {}

resource "azuread_application" "obo" {
  display_name     = "app-${local.func_name}-obo"
  owners           = [data.azurerm_client_config.current.object_id]
  sign_in_audience = "AzureADMyOrg"

  api {
    requested_access_token_version = 2

    oauth2_permission_scope {
      admin_consent_description  = "Allow the application to access Microsoft Graph on behalf of the signed-in user."
      admin_consent_display_name = "Access Microsoft Graph on behalf of the signed-in user"
      enabled                    = true
      id                         = random_uuid.access_as_user_scope.result
      type                       = "User"
      user_consent_description   = "Allow this application to access Microsoft Graph on your behalf."
      user_consent_display_name  = "Access Microsoft Graph on your behalf"
      value                      = "access_as_user"
    }
  }

  required_resource_access {
    resource_app_id = data.azuread_service_principal.microsoft_graph.client_id

    resource_access {
      id   = data.azuread_service_principal.microsoft_graph.oauth2_permission_scope_ids["Mail.ReadWrite"]
      type = "Scope"
    }
  }

  lifecycle {
    ignore_changes = [web]
  }
}

resource "azuread_application_identifier_uri" "obo" {
  application_id = azuread_application.obo.id
  identifier_uri = "api://${azuread_application.obo.client_id}"
}

resource "azuread_service_principal" "obo" {
  client_id = azuread_application.obo.client_id
  owners    = [data.azurerm_client_config.current.object_id]
}

resource "azuread_service_principal_delegated_permission_grant" "microsoft_graph" {
  service_principal_object_id          = azuread_service_principal.obo.object_id
  resource_service_principal_object_id = data.azuread_service_principal.microsoft_graph.object_id
  claim_values                         = ["Mail.ReadWrite"]
}

resource "time_rotating" "obo_client_secret" {
  rotation_days = 180
}

resource "azuread_application_password" "obo" {
  application_object_id = azuread_application.obo.object_id
  display_name          = "Terraform-managed OBO credential"
  end_date_relative     = "8760h"

  rotate_when_changed = {
    rotation = time_rotating.obo_client_secret.id
  }
}
