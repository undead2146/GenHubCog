import asyncio
from redbot.core import commands, Config
from redbot.core.bot import Red

import discord
from .webhook import WebhookServer
from .handlers import GitHubEventHandlers
from .config_commands import ConfigCommands
from .slash_commands import SlashCommands
from .utils import safe_discord_call


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
            "log_level": "info",
            "issues_forum_id": None,
            "prs_forum_id": None,
            "issues_feed_chat_id": None,
            "prs_feed_chat_id": None,
            "updates_channel_id": None,
            "contributor_role_id": None,
            "github_token": "",
            "whitelisted_users": [135370180913004544],
            "thread_cache": {},
        }
        self.config.register_global(**default_global)

        self.thread_cache = {}
        self.webhook = WebhookServer(self)
        self.handlers = GitHubEventHandlers(self)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """handle bot joining a new server: sync slash commands and initialize safely."""
        print(f"🎉 GenHub joined new guild: {getattr(guild, 'name', 'unknown')} ({getattr(guild, 'id', 'unknown')})")
        try:
            if hasattr(self.bot, "tree") and hasattr(self.bot.tree, "sync"):
                await safe_discord_call(
                    self.bot.tree.sync,
                    guild=guild,
                    max_retries=3,
                    operation_name=f"Sync Slash Commands on Guild Join for {getattr(guild, 'name', 'unknown')}",
                )
                print(f"✅ GenHub slash commands synced to new guild: {getattr(guild, 'name', 'unknown')} ({getattr(guild, 'id', 'unknown')})")
        except Exception as e:
            print(f"⚠️ Failed to sync slash commands on guild join for {getattr(guild, 'name', 'unknown')}: {e}")

    async def cog_load(self):
        # Start webhook server
        self.task = asyncio.create_task(self.webhook.start())

        # Load thread cache
        self.thread_cache = await self.config.thread_cache()

        # Sync slash commands with pacing to avoid Discord 429 rate limits
        if hasattr(self.bot, "guilds") and hasattr(self.bot, "tree"):
            for guild in self.bot.guilds:
                try:
                    await safe_discord_call(
                        self.bot.tree.sync,
                        guild=guild,
                        max_retries=3,
                        operation_name=f"Sync Slash Commands on Startup for {getattr(guild, 'name', 'unknown')}",
                    )
                    print(
                        f"✅ GenHub slash commands synced to guild: "
                        f"{getattr(guild, 'name', 'unknown')} ({getattr(guild, 'id', 'unknown')})"
                    )
                except Exception as e:
                    print(f"⚠️ Failed to sync slash commands for {getattr(guild, 'name', 'unknown')}: {e}")
                await asyncio.sleep(0.3)

        # Register text commands cog
        try:
            await self.bot.add_cog(ConfigCommands(self))
        except (discord.ClientException, Exception):
            pass

        # Register slash commands
        slash_handler = SlashCommands(self)
        self.bot.tree.add_command(
            discord.app_commands.Command(
                name="genhubconfig",
                description="Configure GenHub settings in one go",
                callback=slash_handler.config_command,
            )
        )
        self.bot.tree.add_command(
            discord.app_commands.Command(
                name="genhubsetup",
                description="Visual all-in-one setup wizard with channel dropdowns",
                callback=slash_handler.setup_slash_command,
            )
        )

    async def cog_unload(self):
        await self.webhook.stop()
        try:
            await self.bot.remove_cog("ConfigCommands")
        except Exception:
            pass
        # Save thread cache safely (extract thread IDs if stored as Thread objects)
        try:
            serialized_cache = {}
            for k, v in self.thread_cache.items():
                str_key = str(k)
                thread_id = getattr(v, "id", v)
                if isinstance(thread_id, int):
                    serialized_cache[str_key] = thread_id
            await self.config.thread_cache.set(serialized_cache)
        except Exception:
            pass
        if hasattr(self, "task"):
            self.task.cancel()
