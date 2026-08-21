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

The Terraform deployment creates and manages one single-tenant confidential
client app registration:

1. Expose an API scope named `access_as_user`.
2. Add delegated Microsoft Graph `Mail.ReadWrite` permission and grant
   tenant-wide consent.
3. Create a client secret, rotate it every 180 days, and store it as an encrypted
   Container Apps secret.
4. Configure MCP clients to request the exposed MCP scope, not a Graph scope.

Copy `server/.env.example` to a local environment file or configure the same
values as deployment secrets. Environment files are intentionally ignored by
Git.

The Container App receives the generated client ID and audience and exposes the
generated Container Apps secret to the process as `ENTRA_CLIENT_SECRET`. Run
`terraform output mcp_delegated_scope` after deployment to get the scope MCP
clients must request. Applying the Terraform requires permission to create Entra
applications and grant delegated consent. The generated credential is sensitive
and remains in Terraform state, so use a secured remote backend.

Key Vault public access is restricted to selected networks. Terraform looks up
the deployment host's current public IPv4 address and allows that `/32`, while
the `AzureServices` bypass enables trusted Microsoft services. The deployment
host must be able to reach `https://api.ipify.org` during planning and applying.

## Mail tools

- `list_emails` lists recent messages and returns an opaque
  `next_page_url`. Pass that URL back to retrieve the next Graph page.
- `read_email` retrieves a message and its body.
- `create_email_draft` creates a draft but does not send it.

The server retries transient Graph throttling and service failures, honoring
the `Retry-After` response header.