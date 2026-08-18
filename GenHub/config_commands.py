from redbot.core import commands
import os


class ConfigCommands(commands.Cog):
    """Owner-only text commands for configuring GenHub."""

    def __init__(self, parent_cog):
        super().__init__()
        self.cog = parent_cog
        self.genhub.cog = self
        for c in getattr(self.genhub, "commands", []):
            c.cog = self

    async def _set_config(self, ctx, key: str, value):
        await getattr(self.cog.config, key).set(value)
        await ctx.send(f"✅ {key.replace('_', ' ').title()} set to {value}")

    def _resolve_channel_id(self, guild, text: str):
        if not text:
            return None
        text = str(text).strip()
        if text.lower() in ("skip", "none"):
            return None
        if text.startswith("<#") and text.endswith(">"):
            text = text[2:-1]
        if text.isdigit():
            return int(text)
        if guild:
            for ch in guild.channels:
                if ch.name.lower() == text.lower().lstrip("#"):
                    return ch.id
        return None

    def _resolve_role_id(self, guild, text: str):
        if not text:
            return None
        text = str(text).strip()
        if text.lower() in ("skip", "none"):
            return None
        if text.startswith("<@&") and text.endswith(">"):
            text = text[3:-1]
        if text.isdigit():
            return int(text)
        if guild:
            for r in guild.roles:
                if r.name.lower() == text.lower().lstrip("@"):
                    return r.id
        return None

    @commands.group()
    @commands.is_owner()
    async def genhub(self, ctx):
        """GenHub configuration commands."""
        pass

    @genhub.command(name="setup", aliases=["quicksetup", "configure"])
    async def setup_command(
        self,
        ctx,
        issues_forum: str = None,
        prs_forum: str = None,
        log_channel: str = None,
        contributor_role: str = None,
        repo: str = None,
    ):
        """Configure all GenHub channels & repos in ONE single command.
        
        Usage:
          !genhub setup <#issues_forum> <#prs_forum> [<#log_channel>] [@role] [<owner/repo>]
        Or run `!genhub setup` with no arguments for the interactive step-by-step wizard!
        """
        import asyncio

        # If no arguments provided, run interactive wizard
        if not issues_forum:
            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel

            await ctx.send("🚀 **Starting GenHub All-In-One Setup Wizard**\n"
                           "*(You can mention channels `#channel`, paste IDs `141...`, or type `skip` at any step)*\n\n"
                           "**Step 1/5:** Mention or paste the channel ID for the **GitHub Issues Forum** (`github-issues-feed`):")
            try:
                msg = await ctx.bot.wait_for("message", check=check, timeout=60)
                issues_forum = msg.content.strip()
            except asyncio.TimeoutError:
                await ctx.send("⏱️ Setup wizard timed out.")
                return

            await ctx.send("**Step 2/5:** Mention or paste the channel ID for the **Pull Requests Forum** (`pull-requests-feed`):")
            try:
                msg = await ctx.bot.wait_for("message", check=check, timeout=60)
                prs_forum = msg.content.strip()
            except asyncio.TimeoutError:
                await ctx.send("⏱️ Setup wizard timed out.")
                return

            await ctx.send("**Step 3/5:** Mention or paste the **Log / Bot Chat Channel** (`genhub-chat`), or type `skip`:")
            try:
                msg = await ctx.bot.wait_for("message", check=check, timeout=60)
                log_channel = msg.content.strip()
            except asyncio.TimeoutError:
                await ctx.send("⏱️ Setup wizard timed out.")
                return

            await ctx.send("**Step 4/5:** Mention the **Contributor Role** to tag on PR open/merge (e.g. `@Contributor`), or type `skip`:")
            try:
                msg = await ctx.bot.wait_for("message", check=check, timeout=60)
                contributor_role = msg.content.strip()
            except asyncio.TimeoutError:
                await ctx.send("⏱️ Setup wizard timed out.")
                return

            await ctx.send("**Step 5/5:** Enter the **GitHub Repository** to track (e.g. `community-outpost/GenHub`), or type `skip`:")
            try:
                msg = await ctx.bot.wait_for("message", check=check, timeout=60)
                repo = msg.content.strip()
            except asyncio.TimeoutError:
                await ctx.send("⏱️ Setup wizard timed out.")
                return

        # Resolve IDs
        issues_fid = self._resolve_channel_id(ctx.guild, issues_forum)
        prs_fid = self._resolve_channel_id(ctx.guild, prs_forum)
        log_cid = self._resolve_channel_id(ctx.guild, log_channel)
        role_id = self._resolve_role_id(ctx.guild, contributor_role)

        summary = ["✅ **GenHub All-In-One Setup Complete!**", ""]

        if issues_fid:
            await self.cog.config.issues_forum_id.set(issues_fid)
            summary.append(f"• **Issues Forum:** <#{issues_fid}> (`{issues_fid}`)")
        else:
            summary.append(f"• **Issues Forum:** ⚠️ Could not resolve `{issues_forum}`")

        if prs_fid:
            await self.cog.config.prs_forum_id.set(prs_fid)
            summary.append(f"• **PRs Forum:** <#{prs_fid}> (`{prs_fid}`)")
        else:
            summary.append(f"• **PRs Forum:** ⚠️ Could not resolve `{prs_forum}`")

        if log_cid:
            await self.cog.config.log_channel_id.set(log_cid)
            summary.append(f"• **Log Channel:** <#{log_cid}> (`{log_cid}`)")

        if role_id:
            await self.cog.config.contributor_role_id.set(role_id)
            summary.append(f"• **Contributor Role:** <@&{role_id}> (`{role_id}`)")

        if repo and repo.lower() not in ("skip", "none"):
            clean_repo = repo.strip().lstrip("/")
            async with self.cog.config.allowed_repos() as repos:
                if clean_repo not in repos:
                    repos.append(clean_repo)
            summary.append(f"• **Tracked Repo:** `{clean_repo}`")

        summary.append("")
        summary.append("👉 *Next steps:* Set your GitHub Token via `!genhub token <token>` (if needed) and run `!genhub diag` to verify your setup!")
        await ctx.send("\n".join(summary))

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
        """Set the Contributor role ID for mentions."""
        await self._set_config(ctx, "contributor_role_id", role_id)

    @genhub.command()
    @commands.is_owner()
    async def reconcile(self, ctx, repo: str = None):
        """Reconcile all forum posts to ensure correct tags.
        Optionally filter by repo name."""
        await ctx.send("🔄 Starting reconciliation... this may take a while.")
        await self.cog.handlers.reconcile_forum_tags(ctx, repo_filter=repo)
        await ctx.send("✅ Reconciliation complete.")

    @genhub.command()
    async def clearcache(self, ctx):
        """Clear the thread cache for fresh lookups."""
        self.cog.thread_cache.clear()
        await ctx.send("✅ Thread cache cleared. Next reconcile will do fresh lookups.")

    @genhub.command()
    async def testrepo(self, ctx, repo: str):
        """Test access to a GitHub repository."""
        import aiohttp
        import os

        repo = repo.strip().lstrip("/")
        token = await self.cog.config.github_token()

        if not token:
            await ctx.send("❌ No GitHub token configured. Use `!genhub token <token>` to set one.")
            return

        headers = {"Accept": "application/vnd.github.v3+json", "Authorization": f"token {token}"}

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
        token_status = "✅ Set in config" if config.get('github_token') else "❌ Not set"
        message = (
            "📌 **GenHub Configuration** 📌\n"
            f"**Webhook Host:** {config.get('webhook_host')}\n"
            f"**Webhook Port:** {config.get('webhook_port')}\n"
            f"**GitHub Secret:** {config.get('github_secret')}\n"
            f"**GitHub Token:** {token_status}\n"
            f"**Allowed Repos:** {config.get('allowed_repos')}\n"
            f"**Log Channel ID:** {config.get('log_channel_id')}\n"
            f"**Issues Forum ID:** {config.get('issues_forum_id')}\n"
            f"**PRs Forum ID:** {config.get('prs_forum_id')}\n"
            f"**Issues Feed Chat ID:** {config.get('issues_feed_chat_id')}\n"
            f"**PRs Feed Chat ID:** {config.get('prs_feed_chat_id')}\n"
            f"**Contributor Role ID:** {config.get('contributor_role_id')}\n"
        )
        await ctx.send(message)

    @genhub.command(aliases=["status", "diag", "version"])
    async def diagnostics(self, ctx):
        """Run full diagnostics on GenHub Cog, Webhook Server, Discord channels, and GitHub API."""
        import aiohttp
        import datetime

        loading_msg = await ctx.send("🔍 Running GenHub diagnostics...")
        config = await self.cog.config.all()

        lines = ["📊 **GenHub Cog System Diagnostics** 📊", ""]

        # 1. Version & Bot info
        lines.append("**1. System & Version:**")
        lines.append("• Cog Version: `1.2.0` (Open-PR Reconcile, Selective Role Mentions)")
        lines.append(f"• Thread Cache: `{len(self.cog.thread_cache)}` cached items")
        lines.append("")

        # 2. Webhook Server
        lines.append("**2. Webhook Server:**")
        host = config.get("webhook_host", "0.0.0.0")
        port = config.get("webhook_port", 8080)
        lines.append(f"• Listening Address: `{host}:{port}`")
        lines.append("• Endpoints: `/github`, `/webhook`, `/health`")
        lines.append("")

        # 3. Channel & Forum Verification
        lines.append("**3. Discord Channels & Permissions:**")
        
        # Check Issues Forum
        issues_id = config.get("issues_forum_id")
        if issues_id:
            ch = self.cog.bot.get_channel(issues_id)
            if ch:
                perms = ch.permissions_for(ctx.guild.me if ctx.guild else ch.guild.me)
                can_post = perms.send_messages and perms.create_public_threads
                status = "✅ Active & Permitted" if can_post else "⚠️ Missing Thread Permissions"
                lines.append(f"• Issues Forum: `{ch.name}` ({issues_id}) → {status}")
            else:
                lines.append(f"• Issues Forum: ❌ Channel ID `{issues_id}` not found")
        else:
            lines.append("• Issues Forum: ⚠️ Not configured (`!genhub issuesforum <id>`)")

        # Check PRs Forum
        prs_id = config.get("prs_forum_id")
        if prs_id:
            ch = self.cog.bot.get_channel(prs_id)
            if ch:
                perms = ch.permissions_for(ctx.guild.me if ctx.guild else ch.guild.me)
                can_post = perms.send_messages and perms.create_public_threads
                status = "✅ Active & Permitted" if can_post else "⚠️ Missing Thread Permissions"
                lines.append(f"• PRs Forum: `{ch.name}` ({prs_id}) → {status}")
            else:
                lines.append(f"• PRs Forum: ❌ Channel ID `{prs_id}` not found")
        else:
            lines.append("• PRs Forum: ⚠️ Not configured (`!genhub prsforum <id>`)")

        # Check Log Channel
        log_id = config.get("log_channel_id")
        if log_id:
            ch = self.cog.bot.get_channel(log_id)
            if ch:
                lines.append(f"• Log Channel: `{ch.name}` ({log_id}) → ✅ Active")
            else:
                lines.append(f"• Log Channel: ❌ Channel ID `{log_id}` not found")
        else:
            lines.append("• Log Channel: ℹ️ Not configured (optional)")
        lines.append("")

        # 4. GitHub API & Rate Limits
        lines.append("**4. GitHub API & Rate Limits:**")
        token = config.get("github_token")
        if token:
            headers = {"Accept": "application/vnd.github.v3+json", "Authorization": f"token {token}"}
            try:
                async with aiohttp.ClientSession(headers=headers) as session:
                    async with session.get("https://api.github.com/rate_limit", timeout=5) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            core = data.get("resources", {}).get("core", {})
                            rem = core.get("remaining", 0)
                            limit = core.get("limit", 0)
                            reset_ts = core.get("reset", 0)
                            reset_time = datetime.datetime.fromtimestamp(reset_ts).strftime("%H:%M:%S UTC")
                            lines.append(f"• Token Status: ✅ Valid & Authenticated")
                            lines.append(f"• Rate Limit: `{rem}/{limit}` remaining (Resets at `{reset_time}`)")
                        else:
                            lines.append(f"• Token Status: ❌ API Error (HTTP {resp.status})")
            except Exception as e:
                lines.append(f"• GitHub Connection: ❌ Failed ({e})")
        else:
            lines.append("• GitHub Token: ❌ Not set (`!genhub token <token>`)")
        lines.append("")

        # 5. Tracked Repositories
        repos = config.get("allowed_repos", [])
        lines.append(f"**5. Tracked Repositories ({len(repos)}):**")
        if repos:
            for r in repos:
                lines.append(f"• `{r}`")
        else:
            lines.append("• ⚠️ No repositories configured (`!genhub addrepo <owner/repo>`)")

        await loading_msg.edit(content="\n".join(lines))
