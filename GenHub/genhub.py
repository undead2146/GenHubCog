import asyncio
import hmac
import json
from hashlib import sha256

import discord
from aiohttp import web
from redbot.core import commands, Config, app_commands
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
            "issues_feed_chat_id": None,
            "prs_feed_chat_id": None,
            "issues_open_tag_id": None,
            "issues_closed_tag_id": None,
            "prs_open_tag_id": None,
            "prs_closed_tag_id": None,
            "prs_merged_tag_id": None,
        }
        self.config.register_global(**default_global)
        self.server = None
        self.runner = None
        self.task = None
        self.thread_cache = {}

    async def cog_load(self):
        # Start webhook server
        self.task = asyncio.create_task(self.start_server())

        # Force sync slash commands to all guilds for instant availability
        try:
            for guild in self.bot.guilds:
                await self.bot.tree.sync(guild=guild)
                print(f"✅ GenHub slash commands synced to guild: {guild.name} ({guild.id})")
        except Exception as e:
            print(f"⚠️ Failed to sync slash commands: {e}")

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
                await self.send_message(log_channel, message)

    async def send_message(self, channel, content: str, prefix: str = ""):
        """Send a message, splitting into chunks if >2000 chars."""
        limit = 2000
        chunks = [content[i:i+limit] for i in range(0, len(content), limit)]
        for i, chunk in enumerate(chunks):
            if i == 0 and prefix:
                await channel.send(prefix + chunk)
            else:
                await channel.send(chunk)

    def resolve_tag(self, forum: discord.ForumChannel, tag_id: int):
        """Resolve a tag ID into a ForumTag object if available."""
        if not tag_id:
            return None
        return discord.utils.get(forum.available_tags, id=tag_id)

    # ---------------------------
    # GitHub Event Handlers
    # ---------------------------

    async def handle_issue(self, data):
        issue_number = data["issue"]["number"]
        issue_title = data["issue"]["title"]
        issue_url = data["issue"]["html_url"]
        issue_author = data["issue"]["user"]["login"]
        action = data["action"]

        forum_id = await self.config.issues_forum_id()
        forum = self.bot.get_channel(forum_id)

        if action == "opened" and forum:
            open_tag_id = await self.config.issues_open_tag_id()
            tag = self.resolve_tag(forum, open_tag_id)
            await forum.create_thread(
                name=f"「#{issue_number}」{issue_title}",
                content=f"[#{issue_number}]({issue_url})",
                applied_tags=[tag] if tag else []
            )

        thread = await self.find_thread(forum_id, issue_number)
        if action == "closed" and thread:
            closed_tag_id = await self.config.issues_closed_tag_id()
            tag = self.resolve_tag(thread.parent, closed_tag_id)
            await thread.edit(applied_tags=[tag] if tag else [])
            await self.send_message(thread, f"❌ Issue closed by {issue_author}")
        elif action == "reopened" and thread:
            open_tag_id = await self.config.issues_open_tag_id()
            tag = self.resolve_tag(thread.parent, open_tag_id)
            await thread.edit(applied_tags=[tag] if tag else [])
            await self.send_message(thread, f"🔄 Issue reopened by {issue_author}")

        # Feed chat announcements
        feed_chat_id = await self.config.issues_feed_chat_id()
        if feed_chat_id:
            feed_chat = self.bot.get_channel(feed_chat_id)
            if feed_chat:
                if action == "opened":
                    await self.send_message(
                        feed_chat,
                        f"<@&1404155973576294400> New issue opened: "
                        f"**[{issue_title}]({issue_url})** by {issue_author}"
                    )
                elif action == "closed":
                    await self.send_message(
                        feed_chat,
                        f"Issue closed: **[{issue_title}]({issue_url})**"
                    )
                elif action == "reopened":
                    await self.send_message(
                        feed_chat,
                        f"Issue reopened: **[{issue_title}]({issue_url})**"
                    )

    async def handle_pull_request(self, data):
        pr_number = data["pull_request"]["number"]
        pr_title = data["pull_request"]["title"]
        pr_url = data["pull_request"]["html_url"]
        pr_author = data["pull_request"]["user"]["login"]
        action = data["action"]

        forum_id = await self.config.prs_forum_id()
        forum = self.bot.get_channel(forum_id)

        if action == "opened" and forum:
            open_tag_id = await self.config.prs_open_tag_id()
            tag = self.resolve_tag(forum, open_tag_id)
            await forum.create_thread(
                name=f"「#{pr_number}」{pr_title}",
                content=f"[#{pr_number}]({pr_url})",
                applied_tags=[tag] if tag else []
            )

        thread = await self.find_thread(forum_id, pr_number)
        if action == "closed" and thread:
            if data["pull_request"].get("merged"):
                merged_tag_id = await self.config.prs_merged_tag_id()
                tag = self.resolve_tag(thread.parent, merged_tag_id)
                await thread.edit(applied_tags=[tag] if tag else [])
                await self.send_message(thread, f"✅ PR merged by {pr_author}")
            else:
                closed_tag_id = await self.config.prs_closed_tag_id()
                tag = self.resolve_tag(thread.parent, closed_tag_id)
                await thread.edit(applied_tags=[tag] if tag else [])
                await self.send_message(thread, f"❌ PR closed by {pr_author}")
        elif action == "reopened" and thread:
            open_tag_id = await self.config.prs_open_tag_id()
            tag = self.resolve_tag(thread.parent, open_tag_id)
            await thread.edit(applied_tags=[tag] if tag else [])
            await self.send_message(thread, f"🔄 PR reopened by {pr_author}")

        # Feed chat announcements
        feed_chat_id = await self.config.prs_feed_chat_id()
        if feed_chat_id:
            feed_chat = self.bot.get_channel(feed_chat_id)
            if feed_chat:
                if action == "opened":
                    await self.send_message(
                        feed_chat,
                        f"<@&1404155973576294400> New pull request opened: "
                        f"**[{pr_title}]({pr_url})** by {pr_author}"
                    )
                elif action == "closed":
                    if data["pull_request"].get("merged"):
                        await self.send_message(
                            feed_chat,
                            f"PR merged: **[{pr_title}]({pr_url})**"
                        )
                    else:
                        await self.send_message(
                            feed_chat,
                            f"PR closed: **[{pr_title}]({pr_url})**"
                        )
                elif action == "reopened":
                    await self.send_message(
                        feed_chat,
                        f"PR reopened: **[{pr_title}]({pr_url})**"
                    )

    async def handle_issue_comment(self, data):
        issue_number = data["issue"]["number"]
        comment_body = data["comment"]["body"]
        comment_author = data["comment"]["user"]["login"]
        comment_url = data["comment"]["html_url"]

        forum_id = await self.config.issues_forum_id()
        thread = await self.find_thread(forum_id, issue_number)
        prefix = f"# **[ New comment from {comment_author} ]({comment_url})**\n"
        if thread:
            await self.send_message(thread, comment_body, prefix=prefix)
        else:
            # Fallback to feed chat
            feed_chat_id = await self.config.issues_feed_chat_id()
            if feed_chat_id:
                feed_chat = self.bot.get_channel(feed_chat_id)
                if feed_chat:
                    await self.send_message(feed_chat, comment_body, prefix=prefix)

    async def handle_pull_request_review(self, data):
        pr_number = data["pull_request"]["number"]
        review_body = data["review"]["body"]
        review_author = data["review"]["user"]["login"]
        review_url = data["review"]["html_url"]

        forum_id = await self.config.prs_forum_id()
        thread = await self.find_thread(forum_id, pr_number)
        prefix = f"# **[ Review from {review_author} ]({review_url})**\n"
        if thread:
            await self.send_message(thread, review_body, prefix=prefix)
        else:
            # Fallback to feed chat
            feed_chat_id = await self.config.prs_feed_chat_id()
            if feed_chat_id:
                feed_chat = self.bot.get_channel(feed_chat_id)
                if feed_chat:
                    await self.send_message(feed_chat, review_body, prefix=prefix)

    async def handle_pull_request_review_comment(self, data):
        pr_number = data["pull_request"]["number"]
        comment_body = data["comment"]["body"]
        comment_author = data["comment"]["user"]["login"]
        comment_url = data["comment"]["html_url"]

        forum_id = await self.config.prs_forum_id()
        thread = await self.find_thread(forum_id, pr_number)
        prefix = f"# **[ New comment from {comment_author} ]({comment_url})**\n"
        if thread:
            await self.send_message(thread, comment_body, prefix=prefix)
        else:
            # Fallback to feed chat
            feed_chat_id = await self.config.prs_feed_chat_id()
            if feed_chat_id:
                feed_chat = self.bot.get_channel(feed_chat_id)
                if feed_chat:
                    await self.send_message(feed_chat, comment_body, prefix=prefix)

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

    # ---------------------------
    # Shared Config Helper
    # ---------------------------
    async def _set_config(self, ctx_or_interaction, key: str, value, is_slash=False):
        """Helper to set config values consistently for both text and slash commands."""
        await getattr(self.config, key).set(value)
        msg = f"✅ {key.replace('_', ' ').title()} set to {value}"
        if is_slash:
            await ctx_or_interaction.response.send_message(msg, ephemeral=True)
        else:
            await ctx_or_interaction.send(msg)

    # ---------------------------
    # Text Commands
    # ---------------------------
    @commands.group()
    @commands.is_owner()
    async def genhub(self, ctx):
        """GenHub configuration commands."""
        pass

    @genhub.command()
    async def host(self, ctx, host: str):
        """Set the webhook host (default: 0.0.0.0)."""
        await self._set_config(ctx, "webhook_host", host)

    @genhub.command()
    async def port(self, ctx, port: int):
        """Set the webhook port (default: 8080)."""
        await self._set_config(ctx, "webhook_port", port)

    @genhub.command()
    async def secret(self, ctx, secret: str):
        """Set the GitHub webhook secret."""
        await self._set_config(ctx, "github_secret", secret)

    @genhub.command()
    async def addrepo(self, ctx, repo: str):
        """Add an allowed repository (e.g., owner/repo)."""
        repo = repo.strip().lstrip("/")
        async with self.config.allowed_repos() as repos:
            if repo not in repos:
                repos.append(repo)
                await ctx.send(f"✅ Added `{repo}` to allowed repositories")
            else:
                await ctx.send(f"⚠️ `{repo}` is already in the allowed repositories")

    @genhub.command()
    async def removerepo(self, ctx, repo: str):
        """Remove an allowed repository."""
        repo = repo.strip().lstrip("/")
        async with self.config.allowed_repos() as repos:
            if repo in repos:
                repos.remove(repo)
                await ctx.send(f"✅ Removed `{repo}` from allowed repositories")
            else:
                await ctx.send(f"⚠️ `{repo}` is not in the allowed repositories")

    @genhub.command()
    async def logchannel(self, ctx, channel_id: int):
        """Set the log channel ID."""
        await self._set_config(ctx, "log_channel_id", channel_id)

    @genhub.command()
    async def issuesforum(self, ctx, forum_id: int):
        """Set the Issues forum channel ID."""
        await self._set_config(ctx, "issues_forum_id", forum_id)

    @genhub.command()
    async def prsforum(self, ctx, forum_id: int):
        """Set the Pull Requests forum channel ID."""
        await self._set_config(ctx, "prs_forum_id", forum_id)

    @genhub.command()
    async def issuesfeedchat(self, ctx, channel_id: int):
        """Set the Issues Feed Chat channel ID."""
        await self._set_config(ctx, "issues_feed_chat_id", channel_id)

    @genhub.command()
    async def prsfeedchat(self, ctx, channel_id: int):
        """Set the PR Feed Chat channel ID."""
        await self._set_config(ctx, "prs_feed_chat_id", channel_id)

    @genhub.command()
    async def issuesopentag(self, ctx, tag_id: int):
        """Set the Issues forum 'Open' tag ID."""
        await self._set_config(ctx, "issues_open_tag_id", tag_id)

    @genhub.command()
    async def issuesclosedtag(self, ctx, tag_id: int):
        """Set the Issues forum 'Closed' tag ID."""
        await self._set_config(ctx, "issues_closed_tag_id", tag_id)

    @genhub.command()
    async def prsopentag(self, ctx, tag_id: int):
        """Set the PR forum 'Open' tag ID."""
        await self._set_config(ctx, "prs_open_tag_id", tag_id)

    @genhub.command()
    async def prsclosedtag(self, ctx, tag_id: int):
        """Set the PR forum 'Closed' tag ID."""
        await self._set_config(ctx, "prs_closed_tag_id", tag_id)

    @genhub.command()
    async def prsmergedtag(self, ctx, tag_id: int):
        """Set the PR forum 'Merged' tag ID."""
        await self._set_config(ctx, "prs_merged_tag_id", tag_id)

    @genhub.command()
    async def showconfig(self, ctx):
        """Show the current GenHub configuration."""
        config = await self.config.all()
        message = (
            "📌 **GenHub Configuration** 📌\n"
            f"**Webhook Host:** {config['webhook_host']}\n"
            f"**Webhook Port:** {config['webhook_port']}\n"
            f"**GitHub Secret:** {config['github_secret']}\n"
            f"**Allowed Repos:** {config['allowed_repos']}\n"
            f"**Log Channel ID:** {config['log_channel_id']}\n"
            f"**Issues Forum ID:** {config['issues_forum_id']}\n"
            f"**PRs Forum ID:** {config['prs_forum_id']}\n"
            f"**Issues Feed Chat ID:** {config['issues_feed_chat_id']}\n"
            f"**PRs Feed Chat ID:** {config['prs_feed_chat_id']}\n"
            f"**Issues Open Tag ID:** {config['issues_open_tag_id']}\n"
            f"**Issues Closed Tag ID:** {config['issues_closed_tag_id']}\n"
            f"**PRs Open Tag ID:** {config['prs_open_tag_id']}\n"
            f"**PRs Closed Tag ID:** {config['prs_closed_tag_id']}\n"
            f"**PRs Merged Tag ID:** {config['prs_merged_tag_id']}\n"
        )
        await ctx.send(message)

    # ---------------------------
    # Slash Command for Config
    # ---------------------------
    @app_commands.command(name="genhubconfig", description="Configure GenHub settings in one go")
    @app_commands.describe(
        webhook_host="Webhook host (default: 0.0.0.0)",
        webhook_port="Webhook port (default: 8080)",
        github_secret="GitHub webhook secret",
        issues_forum_id="Issues forum channel ID",
        prs_forum_id="PRs forum channel ID",
        issues_feed_chat_id="Issues feed chat channel ID",
        prs_feed_chat_id="PRs feed chat channel ID",
        issues_open_tag_id="Issues forum 'Open' tag ID",
        issues_closed_tag_id="Issues forum 'Closed' tag ID",
        prs_open_tag_id="PR forum 'Open' tag ID",
        prs_closed_tag_id="PR forum 'Closed' tag ID",
        prs_merged_tag_id="PR forum 'Merged' tag ID",
    )
    async def config_command(
        self,
        interaction: discord.Interaction,
        webhook_host: str = None,
        webhook_port: int = None,
        github_secret: str = None,
        issues_forum_id: int = None,
        prs_forum_id: int = None,
        issues_feed_chat_id: int = None,
        prs_feed_chat_id: int = None,
        issues_open_tag_id: int = None,
        issues_closed_tag_id: int = None,
        prs_open_tag_id: int = None,
        prs_closed_tag_id: int = None,
        prs_merged_tag_id: int = None,
    ):
        """Slash command to configure GenHub in one go."""
        updates = {
            "webhook_host": webhook_host,
            "webhook_port": webhook_port,
            "github_secret": github_secret,
            "issues_forum_id": issues_forum_id,
            "prs_forum_id": prs_forum_id,
            "issues_feed_chat_id": issues_feed_chat_id,
            "prs_feed_chat_id": prs_feed_chat_id,
            "issues_open_tag_id": issues_open_tag_id,
            "issues_closed_tag_id": issues_closed_tag_id,
            "prs_open_tag_id": prs_open_tag_id,
            "prs_closed_tag_id": prs_closed_tag_id,
            "prs_merged_tag_id": prs_merged_tag_id,
        }
        for key, value in updates.items():
            if value is not None:
                await getattr(self.config, key).set(value)

        await interaction.response.send_message("✅ GenHub configuration updated.", ephemeral=True)
