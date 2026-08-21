import asyncio
import base64
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from functools import lru_cache
from typing import Any, Literal
from urllib.parse import quote, urlparse

import httpx
import msal
from fastmcp import Context, FastMCP
from fastmcp.server.auth.providers.jwt import JWTVerifier
from fastmcp.server.dependencies import get_access_token
from mcp.types import ImageContent, TextContent
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    entra_tenant_id: str = Field(alias="ENTRA_TENANT_ID")
    entra_client_id: str = Field(alias="ENTRA_CLIENT_ID")
    entra_client_secret: SecretStr = Field(alias="ENTRA_CLIENT_SECRET")
    mcp_audience: str = Field(alias="MCP_AUDIENCE")
    mcp_required_scope: str = Field(
        default="access_as_user",
        alias="MCP_REQUIRED_SCOPE",
    )
    graph_scope: str = Field(
        default="https://graph.microsoft.com/.default",
        alias="GRAPH_SCOPE",
    )


settings = Settings()
entra_authority = (
    f"https://login.microsoftonline.com/{settings.entra_tenant_id}"
)
token_verifier = JWTVerifier(
    jwks_uri=f"{entra_authority}/discovery/v2.0/keys",
    issuer=f"{entra_authority}/v2.0",
    audience=settings.mcp_audience,
    required_scopes=[settings.mcp_required_scope],
)

GRAPH_API_URL = "https://graph.microsoft.com/v1.0"
GRAPH_RETRY_STATUS_CODES = {429, 502, 503, 504}
MAX_GRAPH_ATTEMPTS = 3


@asynccontextmanager
async def app_lifespan(server: FastMCP):
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as graph_client:
        yield {"graph_client": graph_client}


mcp = FastMCP(
    "FastMCP Graph Server",
    auth=token_verifier,
    lifespan=app_lifespan,
)


def _get_mcp_access_token() -> str:
    access_token = get_access_token()
    if access_token is None or not access_token.token:
        raise ValueError("A bearer token issued for this MCP server is required.")
    return access_token.token


@lru_cache(maxsize=1)
def _get_obo_client() -> msal.ConfidentialClientApplication:
    return msal.ConfidentialClientApplication(
        client_id=settings.entra_client_id,
        client_credential=settings.entra_client_secret.get_secret_value(),
        authority=entra_authority,
    )


async def _get_graph_access_token() -> str:
    result = await asyncio.to_thread(
        _get_obo_client().acquire_token_on_behalf_of,
        user_assertion=_get_mcp_access_token(),
        scopes=[settings.graph_scope],
    )
    access_token = result.get("access_token")
    if access_token:
        return access_token

    error = result.get("error", "token_exchange_failed")
    description = result.get(
        "error_description",
        "Microsoft Entra ID did not return a Graph access token.",
    )
    raise RuntimeError(f"Microsoft Graph token exchange failed ({error}): {description}")


def _graph_url(path_or_url: str) -> str:
    if path_or_url.startswith("/"):
        return f"{GRAPH_API_URL}{path_or_url}"

    parsed = urlparse(path_or_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "graph.microsoft.com"
        or parsed.port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
        or not parsed.path.startswith("/v1.0/")
    ):
        raise ValueError("The paging URL must be a Microsoft Graph v1.0 URL.")
    return path_or_url


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(retry_after)
                return max(0.0, (retry_at - datetime.now(UTC)).total_seconds())
            except (TypeError, ValueError):
                pass
    return float(2**attempt)


async def _graph_request(
    ctx: Context,
    method: str,
    path_or_url: str,
    *,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    graph_client: httpx.AsyncClient = ctx.lifespan_context["graph_client"]
    headers = {
        "Authorization": f"Bearer {await _get_graph_access_token()}",
        "Accept": "application/json",
    }

    response: httpx.Response | None = None
    for attempt in range(MAX_GRAPH_ATTEMPTS):
        try:
            response = await graph_client.request(
                method,
                _graph_url(path_or_url),
                headers=headers,
                params=params,
                json=json,
            )
        except (httpx.ConnectError, httpx.ReadTimeout):
            if attempt == MAX_GRAPH_ATTEMPTS - 1:
                raise
            await asyncio.sleep(2**attempt)
            continue

        if (
            response.status_code not in GRAPH_RETRY_STATUS_CODES
            or attempt == MAX_GRAPH_ATTEMPTS - 1
        ):
            break
        await asyncio.sleep(_retry_delay(response, attempt))

    if response is None:
        raise RuntimeError("Microsoft Graph request did not produce a response.")

    if response.is_error:
        try:
            graph_error = response.json().get("error", {})
            detail = graph_error.get("message", response.text)
        except ValueError:
            detail = response.text
        raise RuntimeError(
            f"Microsoft Graph request failed ({response.status_code}): {detail}"
        )

    return response.json()


def _recipients(addresses: list[str] | None) -> list[dict[str, dict[str, str]]]:
    return [
        {"emailAddress": {"address": address}}
        for address in addresses or []
        if address.strip()
    ]


@mcp.tool
def greet(name: str) -> str:
    return f"Hello, {name}!"


@mcp.tool
async def me(ctx: Context):
    with open("app/sample_profile.png", "rb") as img_file:
        image_data = img_file.read()

    base64_image = base64.b64encode(image_data).decode("utf-8")
    image = ImageContent(
        type="image",
        data=base64_image,
        mimeType="image/png",
    )
    return [
        TextContent(type="text", text="You have just called the 'me' tool."),
        TextContent(
            type="text",
            text="Hello current user! Here is your profile picture:",
        ),
        image,
        TextContent(type="text", text="Thank you!"),
    ]


@mcp.tool
async def list_emails(
    ctx: Context,
    folder: str = "inbox",
    limit: int = 25,
    unread_only: bool = False,
    next_page_url: str | None = None,
) -> dict[str, Any]:
    """List a page of the current user's newest messages from a mail folder."""
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100.")

    if next_page_url:
        result = await _graph_request(ctx, "GET", next_page_url)
    else:
        params: dict[str, Any] = {
            "$select": (
                "id,subject,from,toRecipients,receivedDateTime,isRead,"
                "importance,hasAttachments,bodyPreview,webLink"
            ),
            "$orderby": "receivedDateTime desc",
            "$top": limit,
        }
        if unread_only:
            params["$filter"] = (
                "receivedDateTime ge 1900-01-01T00:00:00Z and isRead eq false"
            )

        result = await _graph_request(
            ctx,
            "GET",
            f"/me/mailFolders/{quote(folder, safe='')}/messages",
            params=params,
        )

    return {
        "messages": result.get("value", []),
        "next_page_url": result.get("@odata.nextLink"),
    }


@mcp.tool
async def read_email(ctx: Context, message_id: str) -> dict[str, Any]:
    """Read one email message, including its body, by Graph message ID."""
    if not message_id.strip():
        raise ValueError("message_id is required.")

    return await _graph_request(
        ctx,
        "GET",
        f"/me/messages/{quote(message_id, safe='')}",
        params={
            "$select": (
                "id,subject,from,toRecipients,ccRecipients,bccRecipients,"
                "receivedDateTime,sentDateTime,isRead,importance,"
                "hasAttachments,body,webLink"
            )
        },
    )


@mcp.tool
async def create_email_draft(
    ctx: Context,
    to: list[str],
    subject: str,
    body: str,
    body_type: Literal["Text", "HTML"] = "Text",
    cc: list[str] | None = None,
    bcc: list[str] | None = None,
) -> dict[str, Any]:
    """Create an email draft for the current user without sending it."""
    to_recipients = _recipients(to)
    if not to_recipients:
        raise ValueError("At least one recipient is required.")

    message = {
        "subject": subject,
        "body": {"contentType": body_type, "content": body},
        "toRecipients": to_recipients,
        "ccRecipients": _recipients(cc),
        "bccRecipients": _recipients(bcc),
    }
    draft = await _graph_request(ctx, "POST", "/me/messages", json=message)
    return {
        "id": draft["id"],
        "subject": draft.get("subject", subject),
        "isDraft": draft.get("isDraft", True),
        "webLink": draft.get("webLink"),
    }


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
