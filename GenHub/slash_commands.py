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
        updates_channel_id: int = None,
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
            "updates_channel_id": updates_channel_id,
            "contributor_role_id": contributor_role_id,
        }
        for key, value in updates.items():
            if value is not None:
                await getattr(self.cog.config, key).set(value)

        await interaction.response.send_message(
            "✅ GenHub configuration updated.",
            ephemeral=True,
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
        updates_channel_id: int = None,
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
            updates_channel_id=updates_channel_id,
            contributor_role_id=contributor_role_id,
        )

    async def setup_slash_command(
        self,
        interaction: discord.Interaction,
        issues_forum: discord.ForumChannel = None,
        prs_forum: discord.ForumChannel = None,
        log_channel: discord.TextChannel = None,
        contributor_role: discord.Role = None,
        tracked_repo: str = None,
        updates_channel: discord.abc.GuildChannel = None,
        issues_chat: discord.abc.GuildChannel = None,
        prs_chat: discord.abc.GuildChannel = None,
    ):
        """Configure GenHub using Discord native dropdown selectors."""
        summary = ["✅ **GenHub Configuration Updated via Slash UI:**", ""]

        if issues_forum:
            await self.cog.config.issues_forum_id.set(issues_forum.id)
            summary.append(f"• **Issues Forum:** {issues_forum.mention} (`{issues_forum.id}`)")

        if issues_chat:
            await self.cog.config.issues_feed_chat_id.set(issues_chat.id)
            summary.append(f"• **Issues Feed Chat / Post:** {issues_chat.mention} (`{issues_chat.id}`)")

        if prs_forum:
            await self.cog.config.prs_forum_id.set(prs_forum.id)
            summary.append(f"• **PRs Forum:** {prs_forum.mention} (`{prs_forum.id}`)")

        if prs_chat:
            await self.cog.config.prs_feed_chat_id.set(prs_chat.id)
            summary.append(f"• **PRs Feed Chat / Post:** {prs_chat.mention} (`{prs_chat.id}`)")

        if updates_channel:
            await self.cog.config.updates_channel_id.set(updates_channel.id)
            summary.append(f"• **Pinned Updates Feed:** {updates_channel.mention} (`{updates_channel.id}`)")

        if log_channel:
            await self.cog.config.log_channel_id.set(log_channel.id)
            summary.append(f"• **Log Channel:** {log_channel.mention} (`{log_channel.id}`)")

        if contributor_role:
            await self.cog.config.contributor_role_id.set(contributor_role.id)
            summary.append(f"• **Contributor Role:** {contributor_role.mention} (`{contributor_role.id}`)")

        if tracked_repo:
            clean_repo = tracked_repo.strip().lstrip("/")
            async with self.cog.config.allowed_repos() as repos:
                if clean_repo not in repos:
                    repos.append(clean_repo)
            summary.append(f"• **Tracked Repo:** `{clean_repo}`")

        await interaction.response.send_message("\n".join(summary), ephemeral=True)
