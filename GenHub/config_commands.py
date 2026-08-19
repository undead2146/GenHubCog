import discord
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

        from .utils import find_associated_chat_channel

        if issues_fid:
            await self.cog.config.issues_forum_id.set(issues_fid)
            summary.append(f"• **Issues Forum:** <#{issues_fid}> (`{issues_fid}`)")
            if ctx.guild:
                forum_ch = ctx.guild.get_channel(issues_fid)
                auto_chat = find_associated_chat_channel(ctx.guild, forum_ch, is_pr=False)
                if auto_chat:
                    await self.cog.config.issues_feed_chat_id.set(auto_chat.id)
                    summary.append(f"  ↳ 🔗 *Auto-linked Issues Chat:* {auto_chat.mention} (`{auto_chat.id}`)")
        else:
            summary.append(f"• **Issues Forum:** ⚠️ Could not resolve `{issues_forum}`")

        if prs_fid:
            await self.cog.config.prs_forum_id.set(prs_fid)
            summary.append(f"• **PRs Forum:** <#{prs_fid}> (`{prs_fid}`)")
            if ctx.guild:
                forum_ch = ctx.guild.get_channel(prs_fid)
                auto_chat = find_associated_chat_channel(ctx.guild, forum_ch, is_pr=True)
                if auto_chat:
                    await self.cog.config.prs_feed_chat_id.set(auto_chat.id)
                    summary.append(f"  ↳ 🔗 *Auto-linked PRs Chat:* {auto_chat.mention} (`{auto_chat.id}`)")
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
        """Set the Issues forum channel ID (and auto-detect associated chat)."""
        await self._set_config(ctx, "issues_forum_id", forum_id)
        guild = getattr(ctx, "guild", None)
        if guild and hasattr(guild, "get_channel"):
            forum_ch = guild.get_channel(forum_id)
            from .utils import find_associated_chat_channel
            auto_chat = find_associated_chat_channel(guild, forum_ch, is_pr=False)
            if auto_chat:
                await self.cog.config.issues_feed_chat_id.set(auto_chat.id)
                await ctx.send(f"🔗 Auto-detected Issues Chat Channel: {auto_chat.mention} (`{auto_chat.id}`)")

    @genhub.command()
    async def prsforum(self, ctx, forum_id: int):
        """Set the Pull Requests forum channel ID (and auto-detect associated chat)."""
        await self._set_config(ctx, "prs_forum_id", forum_id)
        guild = getattr(ctx, "guild", None)
        if guild and hasattr(guild, "get_channel"):
            forum_ch = guild.get_channel(forum_id)
            from .utils import find_associated_chat_channel
            auto_chat = find_associated_chat_channel(guild, forum_ch, is_pr=True)
            if auto_chat:
                await self.cog.config.prs_feed_chat_id.set(auto_chat.id)
                await ctx.send(f"🔗 Auto-detected PRs Chat Channel: {auto_chat.mention} (`{auto_chat.id}`)")

    @genhub.command()
    async def issuesfeedchat(self, ctx, channel_id: int):
        """Set the Issues Feed Chat channel ID."""
        await self._set_config(ctx, "issues_feed_chat_id", channel_id)

    @genhub.command()
    async def prsfeedchat(self, ctx, channel_id: int):
        """Set the PR Feed Chat channel ID."""
        await self._set_config(ctx, "prs_feed_chat_id", channel_id)

    @genhub.command(aliases=["updateschannel", "updatesforum", "updatesfeed", "pinnedupdates"])
    async def updates(self, ctx, channel_id: int):
        """Set the Pinned Updates channel / forum post ID for development and release announcements."""
        await self._set_config(ctx, "updates_channel_id", channel_id)

    @genhub.command(aliases=["openprs", "pulls", "prs"])
    async def openpullrequests(self, ctx, repo: str = None):
        """Display all open Pull Requests in an interactive paginated embed."""
        import aiohttp
        from .views import PaginatedEmbedView

        allowed_repos = await self.cog.config.allowed_repos()
        if not repo:
            if not allowed_repos:
                await ctx.send("❌ No repository configured. Use `!genhub addrepo <owner/repo>` first.")
                return
            repo = allowed_repos[0]

        token = await self.cog.config.github_token()
        headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            headers["Authorization"] = f"token {token}"

        loading = await ctx.send(f"🔍 Fetching open pull requests for `{repo}`...")

        prs = []
        page = 1
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                while page <= 10:
                    url = f"https://api.github.com/repos/{repo}/pulls?state=open&per_page=100&page={page}"
                    async with session.get(url, timeout=10) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if not data:
                                break
                            prs.extend(data)
                            if len(data) < 100:
                                break
                            page += 1
                        elif resp.status == 404:
                            await loading.edit(content=f"❌ Repository `{repo}` not found.")
                            return
                        else:
                            await loading.edit(content=f"⚠️ GitHub API returned HTTP {resp.status}")
                            return
        except Exception as e:
            await loading.edit(content=f"❌ Failed to fetch pull requests: {e}")
            return

        if not prs:
            await loading.edit(content=f"🎉 No open pull requests found for `{repo}`!")
            return

        page_size = 8
        pages = []
        total_prs = len(prs)
        total_pages = (total_prs + page_size - 1) // page_size
        prs_forum_id = await self.cog.config.prs_forum_id()

        for page_idx in range(total_pages):
            chunk = prs[page_idx * page_size : (page_idx + 1) * page_size]
            embed = discord.Embed(
                title=f"🔀 Open Pull Requests for {repo} ({total_prs})",
                color=0x23A55A,
                description=f"Showing page **{page_idx + 1}** of **{total_pages}** • Total Open PRs: **{total_prs}**\n\n",
            )
            for pr in chunk:
                num = pr["number"]
                title = pr["title"][:70]
                pr_url = pr["html_url"]
                author = pr.get("user", {}).get("login", "unknown")
                thread_key = (prs_forum_id, repo, num)
                thread = self.cog.thread_cache.get(thread_key)
                thread_link = f" • <#{thread.id}>" if thread else ""
                embed.description += f"• [**#{num}**]({pr_url}) {title}{thread_link}\n  ↳ By **{author}**\n"

            embed.set_footer(text=f"GenHub PR Browser • Page {page_idx + 1}/{total_pages}")
            pages.append(embed)

        view = PaginatedEmbedView(pages, ctx.author.id) if len(pages) > 1 else None
        await loading.delete()
        await ctx.send(embed=pages[0], view=view)

    @genhub.command(aliases=["openissues", "issues"])
    async def openissues_cmd(self, ctx, repo: str = None):
        """Display all open Issues in an interactive paginated embed."""
        import aiohttp
        from .views import PaginatedEmbedView

        allowed_repos = await self.cog.config.allowed_repos()
        if not repo:
            if not allowed_repos:
                await ctx.send("❌ No repository configured. Use `!genhub addrepo <owner/repo>` first.")
                return
            repo = allowed_repos[0]

        token = await self.cog.config.github_token()
        headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            headers["Authorization"] = f"token {token}"

        loading = await ctx.send(f"🔍 Fetching open issues for `{repo}`...")

        issues = []
        page = 1
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                while page <= 10:
                    url = f"https://api.github.com/repos/{repo}/issues?state=open&per_page=100&page={page}"
                    async with session.get(url, timeout=10) as resp:
                        if resp.status == 200:
                            raw_items = await resp.json()
                            if not raw_items:
                                break
                            pure_items = [it for it in raw_items if "pull_request" not in it]
                            issues.extend(pure_items)
                            if len(raw_items) < 100:
                                break
                            page += 1
                        elif resp.status == 404:
                            await loading.edit(content=f"❌ Repository `{repo}` not found.")
                            return
                        else:
                            await loading.edit(content=f"⚠️ GitHub API returned HTTP {resp.status}")
                            return
        except Exception as e:
            await loading.edit(content=f"❌ Failed to fetch issues: {e}")
            return

        if not issues:
            await loading.edit(content=f"🎉 No open issues found for `{repo}`!")
            return

        page_size = 10
        pages = []
        total_issues = len(issues)
        total_pages = (total_issues + page_size - 1) // page_size
        issues_forum_id = await self.cog.config.issues_forum_id()

        for page_idx in range(total_pages):
            chunk = issues[page_idx * page_size : (page_idx + 1) * page_size]
            embed = discord.Embed(
                title=f"🐛 Open Issues for {repo} ({total_issues})",
                color=0x5865F2,
                description=f"Showing page **{page_idx + 1}** of **{total_pages}** • Total Open Issues: **{total_issues}**\n\n",
            )
            for issue in chunk:
                num = issue["number"]
                title = issue["title"][:70]
                issue_url = issue["html_url"]
                author = issue.get("user", {}).get("login", "unknown")
                thread_key = (issues_forum_id, repo, num)
                thread = self.cog.thread_cache.get(thread_key)
                thread_link = f" • <#{thread.id}>" if thread else ""
                embed.description += f"• [**#{num}**]({issue_url}) {title}{thread_link}\n  ↳ By **{author}**\n"

            embed.set_footer(text=f"GenHub Issue Browser • Page {page_idx + 1}/{total_pages}")
            pages.append(embed)

        view = PaginatedEmbedView(pages, ctx.author.id) if len(pages) > 1 else None
        await loading.delete()
        await ctx.send(embed=pages[0], view=view)

    @genhub.command(aliases=["overview", "digest"])
    async def summary(self, ctx, repo: str = None):
        """Display an executive compact summary embed of open PRs and issues."""
        import aiohttp

        allowed_repos = await self.cog.config.allowed_repos()
        if not repo:
            if not allowed_repos:
                await ctx.send("❌ No repository configured. Use `!genhub addrepo <owner/repo>` first.")
                return
            repo = allowed_repos[0]

        token = await self.cog.config.github_token()
        headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            headers["Authorization"] = f"token {token}"

        loading = await ctx.send(f"📊 Generating summary for `{repo}`...")

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                # 1. Fetch PRs across pages
                prs = []
                p_page = 1
                while p_page <= 10:
                    prs_resp = await session.get(f"https://api.github.com/repos/{repo}/pulls?state=open&per_page=100&page={p_page}")
                    if prs_resp.status == 200:
                        p_data = await prs_resp.json()
                        if not p_data:
                            break
                        prs.extend(p_data)
                        if len(p_data) < 100:
                            break
                        p_page += 1
                    else:
                        break

                # 2. Fetch Issues across pages
                issues = []
                i_page = 1
                while i_page <= 10:
                    issues_resp = await session.get(f"https://api.github.com/repos/{repo}/issues?state=open&per_page=100&page={i_page}")
                    if issues_resp.status == 200:
                        raw_data = await issues_resp.json()
                        if not raw_data:
                            break
                        pure_data = [it for it in raw_data if "pull_request" not in it]
                        issues.extend(pure_data)
                        if len(raw_data) < 100:
                            break
                        i_page += 1
                    else:
                        break

                # 3. Fetch Repo Info
                repo_resp = await session.get(f"https://api.github.com/repos/{repo}")
                repo_info = await repo_resp.json() if repo_resp.status == 200 else {}
        except Exception as e:
            await loading.edit(content=f"❌ Failed to fetch summary: {e}")
            return

        embed = discord.Embed(
            title=f"📊 {repo} • Activity & Backlog Summary",
            url=f"https://github.com/{repo}",
            color=0x5865F2,
            description=repo_info.get("description", "GitHub Repository Integration")[:200] if repo_info else "Repository Overview",
        )

        issues_forum_id = await self.cog.config.issues_forum_id()
        prs_forum_id = await self.cog.config.prs_forum_id()

        # PRs Field
        prs_text = f"**Total Open:** `{len(prs)}`\n"
        if prs_forum_id:
            prs_text += f"**Forum Feed:** <#{prs_forum_id}>\n"
        prs_text += "\n**Recent Open PRs:**\n"
        if prs:
            for p in prs[:4]:
                prs_text += f"• [#{p['number']}]({p['html_url']}) {p['title'][:35]} (by {p['user']['login']})\n"
        else:
            prs_text += "• *No open pull requests*\n"

        embed.add_field(name=f"🔀 Pull Requests ({len(prs)})", value=prs_text, inline=True)

        # Issues Field
        issues_text = f"**Total Open:** `{len(issues)}`\n"
        if issues_forum_id:
            issues_text += f"**Forum Feed:** <#{issues_forum_id}>\n"
        issues_text += "\n**Recent Issues:**\n"
        if issues:
            for it in issues[:4]:
                issues_text += f"• [#{it['number']}]({it['html_url']}) {it['title'][:35]} (by {it['user']['login']})\n"
        else:
            issues_text += "• *No open issues*\n"

        embed.add_field(name=f"🐛 Issues ({len(issues)})", value=issues_text, inline=True)

        embed.set_footer(text="Use !genhub openprs or !genhub openissues to browse all items")
        await loading.delete()
        await ctx.send(embed=embed)

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

    @genhub.command(aliases=["stopreconcile", "cancelsync"])
    @commands.is_owner()
    async def cancelreconcile(self, ctx):
        """Cancel an ongoing reconciliation process immediately."""
        if not getattr(self.cog.handlers, "is_reconciling", False):
            await ctx.send("ℹ️ No reconciliation is currently running.")
            return
        self.cog.handlers.reconcile_cancelled = True
        await ctx.send("🛑 Cancelling ongoing reconciliation... it will stop after current operation.")

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
            f"**Updates Channel ID:** {config.get('updates_channel_id')}\n"
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

        # Check Updates Channel
        updates_id = config.get("updates_channel_id")
        if updates_id:
            ch = self.cog.bot.get_channel(updates_id)
            if ch:
                lines.append(f"• Updates Feed: `{ch.name}` ({updates_id}) → ✅ Active")
            else:
                lines.append(f"• Updates Feed: ❌ Channel ID `{updates_id}` not found")
        else:
            lines.append("• Updates Feed: ℹ️ Not configured (optional: `!genhub updates <id>`)")

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
