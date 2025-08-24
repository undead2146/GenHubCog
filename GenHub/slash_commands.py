import discord
from redbot.core import app_commands


class SlashCommands:
    def __init__(self, parent_cog):
        self.cog = parent_cog

    async def _do_config_update(
        self,
        interaction: discord.Interaction,
        webhook_host: str = None,
        webhook_port: int = None,
        github_secret: str = None,
        issues_forum_id: int = None,
        prs_forum_id: int = None,
        issues_feed_chat_id: int = None,
        prs_feed_chat_id: int = None,
        contributor_role_id: int = None,
    ):
        updates = {
            "webhook_host": webhook_host,
            "webhook_port": webhook_port,
            "github_secret": github_secret,
            "issues_forum_id": issues_forum_id,
            "prs_forum_id": prs_forum_id,
            "issues_feed_chat_id": issues_feed_chat_id,
            "prs_feed_chat_id": prs_feed_chat_id,
            "contributor_role_id": contributor_role_id,
        }
        for key, value in updates.items():
            if value is not None:
                await getattr(self.cog.config, key).set(value)

        await interaction.response.send_message(
            "✅ GenHub configuration updated.",
            ephemeral=True,
        )

    @app_commands.command(
        name="genhubconfig", description="Configure GenHub settings in one go"
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
        contributor_role_id: int = None,
    ):
        await self._do_config_update(
            interaction,
            webhook_host=webhook_host,
            webhook_port=webhook_port,
            github_secret=github_secret,
            issues_forum_id=issues_forum_id,
            prs_forum_id=prs_forum_id,
            issues_feed_chat_id=issues_feed_chat_id,
            prs_feed_chat_id=prs_feed_chat_id,
            contributor_role_id=contributor_role_id,
        )
