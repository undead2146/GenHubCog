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
        app = web.Application()
        app.router.add_post("/github", self.webhook_handler)
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

    async def webhook_handler(self, request: web.Request):
        secret = await self.cog.config.github_secret()
        signature = request.headers.get("X-Hub-Signature-256")
        if not signature:
            return web.Response(status=401, text="Missing signature")

        body = await request.read()
        digest = hmac.new(secret.encode(), body, sha256).hexdigest()
        if not hmac.compare_digest(f"sha256={digest}", signature):
            return web.Response(status=401, text="Invalid signature")

        try:
            data = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            return web.Response(status=400, text="Invalid JSON")

        try:
            await self.cog.handlers.process_payload(request, data)
        except Exception as e:
            await self.cog.handlers.log_error(
                f"Error processing payload: {e}\nPayload: {data}"
            )
            return web.Response(status=500, text="Internal Server Error")

        return web.Response(status=200)
