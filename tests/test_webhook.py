import pytest
from unittest.mock import AsyncMock, Mock
from GenHub.webhook import WebhookServer
import hmac, hashlib


@pytest.mark.asyncio
async def test_webhook_signature_valid():
    cog = Mock()
    cog.config = Mock()
    cog.config.github_secret = AsyncMock(return_value="secret")
    cog.handlers = Mock()
    cog.handlers.process_payload = AsyncMock()
    server = WebhookServer(cog)

    body = b'{"repository": {"full_name": "test/repo"}}'
    sig = hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    headers = {"X-Hub-Signature-256": f"sha256={sig}"}

    req = Mock()
    req.headers = headers
    req.read = AsyncMock(return_value=body)

    resp = await server.webhook_handler(req)
    assert resp.status == 200
    cog.handlers.process_payload.assert_awaited_once()


@pytest.mark.asyncio
async def test_webhook_signature_invalid():
    cog = Mock()
    cog.config = Mock()
    cog.config.github_secret = AsyncMock(return_value="secret")
    cog.handlers = Mock()
    server = WebhookServer(cog)

    req = Mock()
    req.headers = {"X-Hub-Signature-256": "sha256=bad"}
    req.read = AsyncMock(return_value=b"{}")

    resp = await server.webhook_handler(req)
    assert resp.status == 401
