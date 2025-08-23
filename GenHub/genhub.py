import asyncio
from redbot.core import commands, Config
from redbot.core.bot import Red

from .webhook import WebhookServer
from .handlers import GitHubEventHandlers
from .config_commands import ConfigCommands
from .slash_commands import SlashCommands


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
            "contributor_role_id": None,
            "github_token": "",
        }
        self.config.register_global(**default_global)

        self.thread_cache = {}
        self.webhook = WebhookServer(self)
        self.handlers = GitHubEventHandlers(self)

    async def cog_load(self):
        # Start webhook server
        self.task = asyncio.create_task(self.webhook.start())

        # Sync slash commands
        try:
            for guild in self.bot.guilds:
                await self.bot.tree.sync(guild=guild)
                print(
                    f"✅ GenHub slash commands synced to guild: "
                    f"{guild.name} ({guild.id})"
                )
        except Exception as e:
            print(f"⚠️ Failed to sync slash commands: {e}")

        # Register text commands cog
        await self.bot.add_cog(ConfigCommands(self))

        # Register slash command
        self.bot.tree.add_command(SlashCommands(self).config_command)

    async def cog_unload(self):
        await self.webhook.stop()
        if hasattr(self, "task"):
            self.task.cancel()
