from redbot.core import commands


class ConfigCommands(commands.Cog):
    """Owner-only text commands for configuring GenHub."""

    def __init__(self, parent_cog):
        self.cog = parent_cog

    async def _set_config(self, ctx, key: str, value):
        await getattr(self.cog.config, key).set(value)
        await ctx.send(f"✅ {key.replace('_', ' ').title()} set to {value}")

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
        async with self.cog.config.allowed_repos() as repos:
            if repo not in repos:
                repos.append(repo)
                await ctx.send(f"✅ Added `{repo}` to allowed repositories")
            else:
                await ctx.send(f"⚠️ `{repo}` is already in the allowed repositories")

    @genhub.command()
    async def removerepo(self, ctx, repo: str):
        """Remove an allowed repository."""
        repo = repo.strip().lstrip("/")
        async with self.cog.config.allowed_repos() as repos:
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
        config = await self.cog.config.all()
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
