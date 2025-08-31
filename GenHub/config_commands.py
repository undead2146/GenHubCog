from redbot.core import commands
import os


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
    async def token(self, ctx, token: str):
        """Set the GitHub token for API access."""
        await self._set_config(ctx, "github_token", token)

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
    async def contributorrole(self, ctx, role_id: int):
        """Set the Contributor role ID for mentions in feed messages."""
        await self._set_config(ctx, "contributor_role_id", role_id)

    @genhub.command()
    @commands.is_owner()
    async def reconcile(self, ctx, repo: str = None):
        """Reconcile all forum posts to ensure correct tags are applied.
        Optionally filter by repo name."""
        await ctx.send("🔄 Starting reconciliation... this may take a while.")
        await self.cog.handlers.reconcile_forum_tags(ctx, repo_filter=repo)
        await ctx.send("✅ Reconciliation complete.")

    @genhub.command()
    async def clearcache(self, ctx):
        """Clear the thread cache to force fresh thread lookups."""
        self.cog.thread_cache.clear()
        await ctx.send("✅ Thread cache cleared. Next reconcile will do fresh lookups.")

    @genhub.command()
    async def testrepo(self, ctx, repo: str):
        """Test access to a GitHub repository."""
        import aiohttp
        import os

        repo = repo.strip().lstrip("/")
        token = os.environ.get("GENHUB_GITHUB_TOKEN") or await self.cog.config.github_token()

        if not token:
            await ctx.send("❌ No GitHub token configured. Use `!genhub token <token>` to set one.")
            return

        headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}"}

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                url = f"https://api.github.com/repos/{repo}"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        await ctx.send(f"✅ Repository '{repo}' is accessible!\n"
                                     f"**Owner:** {data.get('owner', {}).get('login', 'Unknown')}\n"
                                     f"**Private:** {data.get('private', 'Unknown')}\n"
                                     f"**Description:** {data.get('description', 'No description')[:100]}")
                    elif resp.status == 404:
                        await ctx.send(f"❌ Repository '{repo}' not found. Check the repository name.")
                    elif resp.status == 403:
                        await ctx.send(f"🚫 Cannot access '{repo}'. This could be because:\n"
                                     f"• The repository is private and your token lacks access\n"
                                     f"• Your GitHub token doesn't have the required permissions\n"
                                     f"• Check your token at: https://github.com/settings/tokens")
                    elif resp.status == 401:
                        await ctx.send(f"🚫 GitHub authentication failed. Your token may be invalid or expired.\n"
                                     f"• Use `!genhub token <your_token>` to set a new token\n"
                                     f"• Generate a token at: https://github.com/settings/tokens")
                    else:
                        await ctx.send(f"⚠️ Unexpected response ({resp.status}) when testing '{repo}'")
        except Exception as e:
            await ctx.send(f"❌ Error testing repository access: {e}")

    @genhub.command()
    async def showconfig(self, ctx):
        """Show the current GenHub configuration."""
        config = await self.cog.config.all()
        token_status = "✅ Set via GENHUB_GITHUB_TOKEN environment variable" if os.environ.get("GENHUB_GITHUB_TOKEN") else ("✅ Set in config" if config['github_token'] else "❌ Not set")
        message = (
            "📌 **GenHub Configuration** 📌\n"
            f"**Webhook Host:** {config['webhook_host']}\n"
            f"**Webhook Port:** {config['webhook_port']}\n"
            f"**GitHub Secret:** {config['github_secret']}\n"
            f"**GitHub Token:** {token_status}\n"
            f"**Allowed Repos:** {config['allowed_repos']}\n"
            f"**Log Channel ID:** {config['log_channel_id']}\n"
            f"**Issues Forum ID:** {config['issues_forum_id']}\n"
            f"**PRs Forum ID:** {config['prs_forum_id']}\n"
            f"**Issues Feed Chat ID:** {config['issues_feed_chat_id']}\n"
            f"**PRs Feed Chat ID:** {config['prs_feed_chat_id']}\n"
            f"**Contributor Role ID:** {config['contributor_role_id']}\n"
        )
        await ctx.send(message)
