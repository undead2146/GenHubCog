import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
from GenHub.webhook import WebhookServer
import hmac, hashlib, json


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


@pytest.mark.asyncio
async def test_webhook_handler_missing_signature():
    cog = Mock()
    cog.config = Mock()
    cog.config.github_secret = AsyncMock(return_value="secret")
    cog.handlers = Mock()
    server = WebhookServer(cog)

    req = Mock()
    req.headers = {}
    req.read = AsyncMock(return_value=b"{}")

    resp = await server.webhook_handler(req)
    assert resp.status == 401


@pytest.mark.asyncio
async def test_webhook_handler_invalid_json():
    cog = Mock()
    cog.config = Mock()
    cog.config.github_secret = AsyncMock(return_value="secret")
    cog.handlers = Mock()
    server = WebhookServer(cog)

    body = b"not-json"
    sig = hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    headers = {"X-Hub-Signature-256": f"sha256={sig}"}

    req = Mock()
    req.headers = headers
    req.read = AsyncMock(return_value=body)

    resp = await server.webhook_handler(req)
    assert resp.status == 400


@pytest.mark.asyncio
async def test_webhook_handler_processing_error_logs_and_500():
    cog = Mock()
    cog.config = Mock()
    cog.config.github_secret = AsyncMock(return_value="secret")
    cog.handlers = Mock()
    async def bad_process(req, data):
        raise RuntimeError("boom")
    cog.handlers.process_payload = bad_process
    cog.handlers.log_error = AsyncMock()

    server = WebhookServer(cog)

    body = json.dumps({"repository": {"full_name": "x/y"}}).encode()
    sig = hmac.new(b"secret", body, hashlib.sha256).hexdigest()
    headers = {"X-Hub-Signature-256": f"sha256={sig}"}

    req = Mock()
    req.headers = headers
    req.read = AsyncMock(return_value=body)

    resp = await server.webhook_handler(req)
    assert resp.status == 500
    cog.handlers.log_error.assert_awaited()


@pytest.mark.asyncio
async def test_webhook_start_and_stop(monkeypatch):
    cog = AsyncMock()
    cog.config = AsyncMock()
    cog.config.webhook_host = AsyncMock(return_value="127.0.0.1")
    cog.config.webhook_port = AsyncMock(return_value=8080)

    server = WebhookServer(cog)

    with patch("GenHub.webhook.web.AppRunner") as MockRunner, \
         patch("GenHub.webhook.web.TCPSite") as MockSite:
        runner = AsyncMock()
        MockRunner.return_value = runner
        site = AsyncMock()
        MockSite.return_value = site

        await server.start()
        site.start.assert_awaited()
        await server.stop()
        runner.cleanup.assert_awaited()


@pytest.mark.asyncio
async def test_webhook_start_failure(capsys):
    cog = AsyncMock()
    cog.config = AsyncMock()
    cog.config.webhook_host = AsyncMock(return_value="127.0.0.1")
    cog.config.webhook_port = AsyncMock(return_value=8080)
    server = WebhookServer(cog)

    with patch("GenHub.webhook.web.TCPSite.start", side_effect=RuntimeError("boom")):
        await server.start()
    out = capsys.readouterr().out
    assert "Failed to start webhook server" in out
