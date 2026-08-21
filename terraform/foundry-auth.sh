#!/usr/bin/env bash

set -euo pipefail

terraform_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

tenant_id="$(terraform -chdir="$terraform_dir" output -raw entra_tenant_id)"
client_id="$(terraform -chdir="$terraform_dir" output -raw entra_application_client_id)"
scope="$(terraform -chdir="$terraform_dir" output -raw mcp_delegated_scope)"
oauth_base_url="https://login.microsoftonline.com/${tenant_id}/oauth2/v2.0"

cat <<EOF
Microsoft Foundry custom OAuth configuration

Authentication mode: OAuth identity passthrough (Custom OAuth)
Client ID:           ${client_id}
Authorization URL:   ${oauth_base_url}/authorize
Token URL:           ${oauth_base_url}/token
Refresh URL:         ${oauth_base_url}/token
Scopes:              ${scope} offline_access
Expected audience:   ${client_id}

After Foundry creates the connection, add its callback URL as a Web redirect
URI on the Entra app registration.
EOF
