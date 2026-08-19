import hmac
import json
from hashlib import sha256
from aiohttp import web


class WebhookServer:
    def __init__(self, cog):
        self.cog = cog
        self.runner = None
        self.server = None

    async def start(self):
        host = await self.cog.config.webhook_host()
        port = await self.cog.config.webhook_port()
        async def handle_root(request: web.Request):
            return web.Response(text="GenHub Webhook Server OK")

        async def handle_health(request: web.Request):
            return web.Response(text="OK")

        app = web.Application()
        app.router.add_post("/github", self.webhook_handler)
        app.router.add_post("/webhook", self.webhook_handler)
        app.router.add_post("/", self.webhook_handler)
        app.router.add_get("/", handle_root)
        app.router.add_get("/health", handle_health)
        app.router.add_get("/webhook", handle_root)
        app.router.add_get("/github", handle_root)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        self.server = web.TCPSite(self.runner, host, port)
        try:
            await self.server.start()
            print(f"Webhook server started on {host}:{port}")
        except Exception as e:
            print(f"Failed to start webhook server: {e}")

    async def stop(self):
        if self.runner:
            await self.runner.cleanup()

    async def _safe_log_error(self, msg: str):
        import asyncio
        if hasattr(self.cog, "handlers") and hasattr(self.cog.handlers, "log_error"):
            try:
                res = self.cog.handlers.log_error(msg)
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass

    async def webhook_handler(self, request: web.Request):
        event_type = request.headers.get("X-GitHub-Event", "unknown")
        delivery_id = request.headers.get("X-GitHub-Delivery", "N/A")
        client_ip = getattr(request, "remote", "Unknown IP")
        print(f"📥 [Webhook] Received HTTP POST {getattr(request, 'path', '/')} | Event: {event_type} | Delivery: {delivery_id} | Client: {client_ip}")

        secret = await self.cog.config.github_secret()
        body = await request.read()

        if secret:
            signature = request.headers.get("X-Hub-Signature-256")
            if not signature:
                msg = f"⚠️ [Webhook] 401 Unauthorized: Missing X-Hub-Signature-256 header (Delivery: {delivery_id})"
                print(msg)
                await self._safe_log_error(msg)
                return web.Response(status=401, text="Missing signature")

            digest = hmac.new(secret.encode(), body, sha256).hexdigest()
            if not hmac.compare_digest(f"sha256={digest}", signature):
                msg = f"⚠️ [Webhook] 401 Unauthorized: Invalid HMAC signature for delivery {delivery_id}. Check that !genhub secret matches GitHub webhook secret."
                print(msg)
                await self._safe_log_error(msg)
                return web.Response(status=401, text="Invalid signature")

        try:
            data = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as e:
            msg = f"⚠️ [Webhook] 400 Bad Request: Failed to parse JSON payload ({e})"
            print(msg)
            await self._safe_log_error(msg)
            return web.Response(status=400, text="Invalid JSON")

        try:
            await self.cog.handlers.process_payload(request, data)
        except Exception as e:
            await self._safe_log_error(
                f"Error processing {event_type} payload: {e}\nPayload: {data}"
            )
            return web.Response(status=500, text="Internal Server Error")

        return web.Response(status=200)
