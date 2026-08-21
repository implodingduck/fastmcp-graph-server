# FastMCP Graph Server
Sample FastMCP server implementation to expose the Microsoft Graph API.

## Authentication

The HTTP endpoint is an OAuth resource protected by Microsoft Entra ID. Clients
must send an Entra access token whose audience is this MCP server and whose
delegated scopes include `access_as_user`. The server validates that token's
signature, issuer, audience, expiry, and scope before invoking a tool.

For Graph operations, the server exchanges the validated MCP token through the
Microsoft identity platform On-Behalf-Of flow. Graph tokens are never accepted
from MCP clients or passed through the server.

Configure one confidential-client app registration:

1. Expose an API scope named `access_as_user`.
2. Add delegated Microsoft Graph `Mail.ReadWrite` permission and grant the
   consent required by your tenant.
3. Create a client credential for the server. Prefer a certificate or workload
   identity in production; the current implementation accepts a client secret.
4. Configure MCP clients to request the exposed MCP scope, not a Graph scope.

Copy `server/.env.example` to a local environment file or configure the same
values as deployment secrets. Environment files are intentionally ignored by
Git.

For the Terraform deployment, store the client secret in Key Vault and set
`TF_VAR_entra_client_secret_key_vault_secret_uri` to that secret's URI. The
Container App resolves it with its user-assigned managed identity, so the
credential is not supplied as a Terraform variable.

## Mail tools

- `list_emails` lists recent messages and returns an opaque
  `next_page_url`. Pass that URL back to retrieve the next Graph page.
- `read_email` retrieves a message and its body.
- `create_email_draft` creates a draft but does not send it.

The server retries transient Graph throttling and service failures, honoring
the `Retry-After` response header.