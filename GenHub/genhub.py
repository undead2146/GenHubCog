import asyncio
import hmac
import json
from hashlib import sha256

from aiohttp import web
from redbot.core import commands, Config
from redbot.core.bot import Red


class GenHub(commands.Cog):
    """GitHub to Discord Forum Router"""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        default_global = {
            "webhook_host": "0.0.0.0",
            "webhook_port": 8080,
            "github_secret": "",
            "allowed_repos": [],
            "log_channel_id": None,
            "issues_forum_id": None,
            "prs_forum_id": None,
            "issues_feed_chat_id": None,  # NEW
            "prs_feed_chat_id": None,     # NEW
        }
        self.config.register_global(**default_global)
        self.server = None
        self.runner = None
        self.task = None
        self.thread_cache = {}

    async def cog_load(self):
        self.task = asyncio.create_task(self.start_server())

    async def cog_unload(self):
        if self.runner:
            await self.runner.cleanup()
        if self.task:
            self.task.cancel()

    async def start_server(self):
        host = await self.config.webhook_host()
        port = await self.config.webhook_port()
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

    async def webhook_handler(self, request: web.Request):
        secret = await self.config.github_secret()
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
            await self.process_payload(request, data)
        except Exception as e:
            await self.log_error(f"Error processing payload: {e}\nPayload: {data}")
            return web.Response(status=500, text="Internal Server Error")

        return web.Response(status=200)

    async def process_payload(self, request: web.Request, data):
        repo_full_name = data.get("repository", {}).get("full_name")
        allowed_repos = await self.config.allowed_repos()
        if repo_full_name not in allowed_repos:
            return

        event_type = request.headers.get("X-GitHub-Event")
        if event_type == "issues":
            await self.handle_issue(data)
        elif event_type == "pull_request":
            await self.handle_pull_request(data)
        elif event_type == "issue_comment":
            await self.handle_issue_comment(data)
        elif event_type == "pull_request_review":
            await self.handle_pull_request_review(data)
        elif event_type == "pull_request_review_comment":
            await self.handle_pull_request_review_comment(data)

    async def log_error(self, message):
        log_channel_id = await self.config.log_channel_id()
        if log_channel_id:
            log_channel = self.bot.get_channel(log_channel_id)
            if log_channel:
                await log_channel.send(message)

    async def handle_issue(self, data):
        if data["action"] == "opened":
            issue_number = data["issue"]["number"]
            issue_title = data["issue"]["title"]
            issue_url = data["issue"]["html_url"]
            issue_author = data["issue"]["user"]["login"]

            forum_id = await self.config.issues_forum_id()
            forum = self.bot.get_channel(forum_id)
            if forum:
                thread_name = f"「#{issue_number}」{issue_title}"
                message_content = f"[#{issue_number}]({issue_url})"
                await forum.create_thread(name=thread_name, content=message_content)

            # Announce in Issues Feed Chat if configured
            feed_chat_id = await self.config.issues_feed_chat_id()
            if feed_chat_id:
                feed_chat = self.bot.get_channel(feed_chat_id)
                if feed_chat:
                    await feed_chat.send(
                        f"<@&1404155973576294400> New issue opened: "
                        f"**[{issue_title}]({issue_url})** by {issue_author}"
                    )

    async def handle_pull_request(self, data):
        if data["action"] == "opened":
            pr_number = data["pull_request"]["number"]
            pr_title = data["pull_request"]["title"]
            pr_url = data["pull_request"]["html_url"]
            pr_author = data["pull_request"]["user"]["login"]

            forum_id = await self.config.prs_forum_id()
            forum = self.bot.get_channel(forum_id)
            if forum:
                thread_name = f"「#{pr_number}」{pr_title}"
                message_content = f"[#{pr_number}]({pr_url})"
                await forum.create_thread(name=thread_name, content=message_content)

            # Announce in PR Feed Chat if configured
            feed_chat_id = await self.config.prs_feed_chat_id()
            if feed_chat_id:
                feed_chat = self.bot.get_channel(feed_chat_id)
                if feed_chat:
                    await feed_chat.send(
                        f"<@&1404155973576294400> New pull request opened: "
                        f"**[{pr_title}]({pr_url})** by {pr_author}"
                    )

    async def handle_issue_comment(self, data):
        issue_number = data["issue"]["number"]
        comment_body = data["comment"]["body"]
        comment_author = data["comment"]["user"]["login"]
        comment_url = data["comment"]["html_url"]

        forum_id = await self.config.issues_forum_id()
        thread = await self.find_thread(forum_id, issue_number)
        if thread:
            message = (
                f"# **[ New comment from {comment_author} ]({comment_url})**\n"
                f"{comment_body}"
            )
            await thread.send(message)

    async def handle_pull_request_review(self, data):
        pr_number = data["pull_request"]["number"]
        review_body = data["review"]["body"]
        review_author = data["review"]["user"]["login"]
        review_url = data["review"]["html_url"]

        forum_id = await self.config.prs_forum_id()
        thread = await self.find_thread(forum_id, pr_number)
        if thread:
            message = (
                f"# **[ Review from {review_author} ]({review_url})**\n"
                f"{review_body}"
            )
            await thread.send(message)

    async def handle_pull_request_review_comment(self, data):
        pr_number = data["pull_request"]["number"]
        comment_body = data["comment"]["body"]
        comment_author = data["comment"]["user"]["login"]
        comment_url = data["comment"]["html_url"]

        forum_id = await self.config.prs_forum_id()
        thread = await self.find_thread(forum_id, pr_number)
        if thread:
            message = (
                f"# **[ New comment from {comment_author} ]({comment_url})**\n"
                f"{comment_body}"
            )
            await thread.send(message)

    async def find_thread(self, forum_id, topic_number):
        if topic_number in self.thread_cache:
            thread_id = self.thread_cache[topic_number]
            thread = self.bot.get_channel(thread_id)
            if thread:
                return thread

        forum = self.bot.get_channel(forum_id)
        if not forum:
            return None

        for thread in forum.threads:
            if f"「#{topic_number}」" in thread.name:
                self.thread_cache[topic_number] = thread.id
                return thread

        async for thread in forum.archived_threads(limit=None):
            if f"「#{topic_number}」" in thread.name:
                self.thread_cache[topic_number] = thread.id
                return thread

        return None

    @commands.group()
    @commands.is_owner()
    async def genhub(self, ctx):
        """GenHub configuration"""
        pass

    @genhub.command()
    async def host(self, ctx, host: str):
        await self.config.webhook_host.set(host)
        await ctx.send(f"Webhook host set to {host}")

    @genhub.command()
    async def port(self, ctx, port: int):
        await self.config.webhook_port.set(port)
        await ctx.send(f"Webhook port set to {port}")

    @genhub.command()
    async def secret(self, ctx, secret: str):
        await self.config.github_secret.set(secret)
        await ctx.send("GitHub webhook secret set")

    @genhub.command()
    async def addrepo(self, ctx, repo: str):
        async with self.config.allowed_repos() as repos:
            if repo not in repos:
                repos.append(repo)
                await ctx.send(f"Added {repo} to allowed repositories")
            else:
                await ctx.send(f"{repo} is already in the allowed repositories")

    @genhub.command()
    async def removerepo(self, ctx, repo: str):
        async with self.config.allowed_repos() as repos:
            if repo in repos:
                repos.remove(repo)
                await ctx.send(f"Removed {repo} from allowed repositories")
            else:
                await ctx.send(f"{repo} is not in the allowed repositories")

    @genhub.command()
    async def logchannel(self, ctx, channel_id: int):
        await self.config.log_channel_id.set(channel_id)
        await ctx.send(f"Log channel set to {channel_id}")

    @genhub.command()
    async def issuesforum(self, ctx, forum_id: int):
        await self.config.issues_forum_id.set(forum_id)
        await ctx.send(f"Issues forum channel set to {forum_id}")

    @genhub.command()
    async def prsforum(self, ctx, forum_id: int):
        await self.config.prs_forum_id.set(forum_id)
        await ctx.send(f"Pull requests forum channel set to {forum_id}")

    @genhub.command()
    async def issuesfeedchat(self, ctx, channel_id: int):
        """Set the Issues Feed Chat channel ID"""
        await self.config.issues_feed_chat_id.set(channel_id)
        await ctx.send(f"Issues feed chat set to {channel_id}")

    @genhub.command()
    async def prsfeedchat(self, ctx, channel_id: int):
        """Set the PR Feed Chat channel ID"""
        await self.config.prs_feed_chat_id.set(channel_id)
        await ctx.send(f"PR feed chat set to {channel_id}")

    @genhub.command()
    async def showconfig(self, ctx):
        config = await self.config.all()
        message = "GenHub Configuration:\n"
        for key, value in config.items():
            message += f"{key}: {value}\n"
        await ctx.send(message)
