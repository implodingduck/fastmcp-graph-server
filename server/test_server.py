import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("ENTRA_TENANT_ID", "test-tenant")
os.environ.setdefault("ENTRA_CLIENT_ID", "test-client")
os.environ.setdefault("ENTRA_CLIENT_SECRET", "test-secret")
os.environ.setdefault("MCP_AUDIENCE", "api://test-client")

import server


class MailToolHelpersTest(unittest.IsolatedAsyncioTestCase):
    @patch("server.get_http_headers")
    def test_get_mcp_access_token(self, headers):
        headers.return_value = {"authorization": "Bearer mcp-token"}

        self.assertEqual(server._get_mcp_access_token(), "mcp-token")

    @patch("server.get_http_headers")
    def test_get_mcp_access_token_requires_bearer_token(self, headers):
        headers.return_value = {}

        with self.assertRaisesRegex(ValueError, "bearer token"):
            server._get_mcp_access_token()

    @patch("server._get_obo_client")
    @patch("server.get_http_headers")
    async def test_graph_token_uses_obo(self, headers, get_obo_client):
        headers.return_value = {"authorization": "Bearer mcp-token"}
        acquire_token = get_obo_client.return_value.acquire_token_on_behalf_of
        acquire_token.return_value = {"access_token": "graph-token"}

        token = await server._get_graph_access_token()

        self.assertEqual(token, "graph-token")
        acquire_token.assert_called_once_with(
            user_assertion="mcp-token",
            scopes=["https://graph.microsoft.com/.default"],
        )

    @patch("server._get_obo_client")
    @patch("server.get_http_headers")
    async def test_graph_token_surfaces_obo_failure(self, headers, get_obo_client):
        headers.return_value = {"authorization": "Bearer mcp-token"}
        acquire_token = get_obo_client.return_value.acquire_token_on_behalf_of
        acquire_token.return_value = {
            "error": "invalid_grant",
            "error_description": "Consent is required.",
        }

        with self.assertRaisesRegex(RuntimeError, "Consent is required"):
            await server._get_graph_access_token()

    def test_graph_url_rejects_non_graph_paging_url(self):
        with self.assertRaisesRegex(ValueError, "Microsoft Graph"):
            server._graph_url("https://example.com/v1.0/me/messages")

    def test_recipients_uses_graph_shape(self):
        self.assertEqual(
            server._recipients(["person@example.com"]),
            [{"emailAddress": {"address": "person@example.com"}}],
        )

    @patch("server._graph_request", new_callable=AsyncMock)
    async def test_unread_email_query_uses_graph_compatible_filter(
        self,
        graph_request,
    ):
        graph_request.return_value = {
            "value": [{"id": "message-id"}],
            "@odata.nextLink": "https://graph.microsoft.com/v1.0/next",
        }
        ctx = SimpleNamespace()

        result = await server.list_emails(ctx, unread_only=True)

        params = graph_request.await_args.kwargs["params"]
        self.assertEqual(params["$orderby"], "receivedDateTime desc")
        self.assertEqual(
            params["$filter"],
            "receivedDateTime ge 1900-01-01T00:00:00Z and isRead eq false",
        )
        self.assertEqual(result["messages"], [{"id": "message-id"}])
        self.assertEqual(
            result["next_page_url"],
            "https://graph.microsoft.com/v1.0/next",
        )

    @patch("server._get_graph_access_token", new_callable=AsyncMock)
    async def test_graph_request_surfaces_graph_error(self, graph_token):
        graph_token.return_value = "graph-token"
        response = MagicMock()
        response.is_error = True
        response.status_code = 403
        response.json.return_value = {
            "error": {"message": "Insufficient privileges"}
        }
        graph_client = AsyncMock()
        graph_client.request.return_value = response
        ctx = SimpleNamespace(
            lifespan_context={"graph_client": graph_client},
        )

        with self.assertRaisesRegex(RuntimeError, "Insufficient privileges"):
            await server._graph_request(ctx, "GET", "/me/messages")

    @patch("server.asyncio.sleep", new_callable=AsyncMock)
    @patch("server._get_graph_access_token", new_callable=AsyncMock)
    async def test_graph_request_retries_throttling(self, graph_token, sleep):
        graph_token.return_value = "graph-token"
        throttled = MagicMock(
            status_code=429,
            headers={"Retry-After": "2"},
            is_error=True,
        )
        success = MagicMock(status_code=200, headers={}, is_error=False)
        success.json.return_value = {"value": []}
        graph_client = AsyncMock()
        graph_client.request.side_effect = [throttled, success]
        ctx = SimpleNamespace(
            lifespan_context={"graph_client": graph_client},
        )

        result = await server._graph_request(ctx, "GET", "/me/messages")

        self.assertEqual(result, {"value": []})
        self.assertEqual(graph_client.request.await_count, 2)
        sleep.assert_awaited_once_with(2.0)


if __name__ == "__main__":
    unittest.main()
