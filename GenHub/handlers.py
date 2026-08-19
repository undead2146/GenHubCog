import discord
import asyncio
import aiohttp
import re
import time
from .utils import (
    send_message,
    get_role_mention,
    format_message,
    get_issue_tags,
    get_pr_tags,
    update_status_tag,
    get_or_create_thread,
    get_or_create_tag,
    is_bot_author,
    clean_github_markdown,
    create_comment_embed,
    create_review_link_view,
)

GITHUB_ISSUE_RE = re.compile(
    r"https://github\.com/([^/]+)/([^/]+)/(issues|pull)/(\d+)"
)


class RateLimiter:
    """GitHub API rate limiter with exponential backoff."""
    
    def __init__(self):
        self.last_request_time = 0
        self.min_interval = 0.75  # Minimum seconds between requests
        self.remaining = 5000
        self.reset_time = 0
        
    async def wait(self):
        """Wait if necessary to respect rate limits."""
        # Wait for minimum interval
        now = time.time()
        elapsed = now - self.last_request_time
        if elapsed < self.min_interval:
            await asyncio.sleep(self.min_interval - elapsed)
        
        # Check if we're approaching rate limit
        if self.remaining < 100:
            wait_time = max(0, self.reset_time - time.time())
            if wait_time > 0:
                print(f"⏳ Rate limit low ({self.remaining} remaining), waiting {wait_time:.0f}s...")
                await asyncio.sleep(wait_time + 1)
        
        self.last_request_time = time.time()
    
    def update_from_headers(self, headers):
        """Update rate limit info from response headers."""
        try:
            self.remaining = int(headers.get('X-RateLimit-Remaining', 5000))
            self.reset_time = int(headers.get('X-RateLimit-Reset', 0))
            print(f"📊 Rate limit: {self.remaining} requests remaining")
        except (ValueError, TypeError):
            pass


LOG_LEVEL_HIERARCHY = {
    "error": 1,
    "errors": 1,
    "info": 2,
    "audit": 2,
    "verbose": 3,
    "debug": 3,
    "all": 3,
}


class GitHubEventHandlers:
    def __init__(self, cog):
        self.cog = cog
        self.pending_reviews = {}
        self.rate_limiter = RateLimiter()
        self.is_reconciling = False
        self.reconcile_cancelled = False

    async def _get_config_id(self, key):
        """Safely fetch a channel/role ID from cog config without crashing on Mock objects."""
        import inspect
        if not hasattr(self.cog, "config") or not hasattr(self.cog.config, key):
            return None
        attr = getattr(self.cog.config, key)
        try:
            val = attr()
            if inspect.isawaitable(val):
                val = await val
            if isinstance(val, int):
                return val
            return None
        except Exception:
            return None

    async def _should_log(self, level: str) -> bool:
        """Determine if a log message should be dispatched to Discord based on configured log level."""
        import inspect
        current_level_str = "info"
        if hasattr(self.cog, "config") and hasattr(self.cog.config, "log_level"):
            try:
                val = self.cog.config.log_level()
                if inspect.isawaitable(val):
                    val = await val
                if isinstance(val, str) and val.strip():
                    current_level_str = val.strip().lower()
            except Exception:
                pass
        current_threshold = LOG_LEVEL_HIERARCHY.get(current_level_str, 2)
        required_level = LOG_LEVEL_HIERARCHY.get(level.lower(), 2)
        return current_threshold >= required_level

    async def _resolve_target_channel(self, channel_id: int):
        """Retrieve a Discord TextChannel, ForumChannel, or Thread (Forum Post) reliably."""
        if not channel_id:
            return None
        ch = self.cog.bot.get_channel(channel_id)
        if ch:
            return ch
        if hasattr(self.cog.bot, "fetch_channel"):
            try:
                return await self.cog.bot.fetch_channel(channel_id)
            except Exception:
                pass
        return None

    async def _get_or_discover_feed_chat(self, forum_id: int, config_key: str):
        """Retrieve the configured chat channel/post, or automatically discover a chat/discussion post inside the forum."""
        chat_id = await self._get_config_id(config_key)
        if chat_id:
            ch = await self._resolve_target_channel(chat_id)
            if ch:
                return ch

        # If not explicitly configured, discover within the forum
        if not forum_id:
            return None
        forum = await self._resolve_target_channel(forum_id)
        if not forum:
            return None

        # If forum itself is a TextChannel (not ForumChannel), return it
        if isinstance(forum, discord.TextChannel):
            return forum

        # Collect candidate threads from forum and guild
        candidates = []
        if hasattr(forum, "threads"):
            try:
                for t in forum.threads:
                    if t not in candidates:
                        candidates.append(t)
            except Exception:
                pass

        guild = getattr(forum, "guild", None)
        if guild:
            # Check cached guild threads
            if hasattr(guild, "threads"):
                try:
                    for t in guild.threads:
                        if getattr(t, "parent_id", None) == forum_id or getattr(t, "parent", None) == forum:
                            if t not in candidates:
                                candidates.append(t)
                except Exception:
                    pass
            # Fetch active threads via API if candidates empty or to ensure complete list
            if hasattr(guild, "active_threads") and callable(guild.active_threads):
                try:
                    active = await guild.active_threads()
                    for t in active:
                        if getattr(t, "parent_id", None) == forum_id or getattr(t, "parent", None) == forum:
                            if t not in candidates:
                                candidates.append(t)
                except Exception:
                    pass

        # Also check archived threads in forum if needed
        if not candidates and hasattr(forum, "archived_threads") and callable(forum.archived_threads):
            try:
                async for t in forum.archived_threads(limit=25):
                    if t not in candidates:
                        candidates.append(t)
            except Exception:
                pass

        if not candidates:
            return None

        # Prefer pinned threads first
        pinned = [t for t in candidates if getattr(getattr(t, "flags", None), "pinned", False)]
        search_pool = pinned + [t for t in candidates if t not in pinned]

        keywords = ("chat", "feed", "issue", "pr", "pull", "general", "discuss", "talk", "overview", "updates", "hub")
        for t in search_pool:
            name = getattr(t, "name", "")
            if isinstance(name, str):
                name_clean = name.lower().strip()
                if any(kw in name_clean for kw in keywords):
                    return t

        # If a pinned thread exists even without keyword, use it
        if pinned:
            return pinned[0]

        # If candidates exist, return first non-issue/non-PR numbered thread or first candidate
        for t in candidates:
            name = getattr(t, "name", "")
            if isinstance(name, str) and not re.search(r"\[GH\]\s*\[#\d+\]", name, re.IGNORECASE):
                return t

        return candidates[0] if candidates else None

    async def _send_to_log_channel(self, formatted_message: str):
        """Helper to send a formatted message to the configured log channel."""
        log_channel_id = await self._get_config_id("log_channel_id")
        if log_channel_id:
            channel = await self._resolve_target_channel(log_channel_id)
            if channel:
                try:
                    await channel.send(formatted_message[:1950])
                except Exception as e:
                    print(f"⚠️ Failed to send log to channel: {e}")

    async def log_error(self, message: str):
        """Log errors to console and Discord log channel (Level: errors)."""
        print(f"❌ GenHub Error: {message}")
        if await self._should_log("error"):
            await self._send_to_log_channel(f"❌ **GenHub Error:**\n```{message[:1900]}```")

    async def log_info(self, message: str):
        """Log operational notices to console and Discord log channel (Level: info)."""
        print(f"ℹ️ {message}")
        if await self._should_log("info"):
            await self._send_to_log_channel(f"ℹ️ {message}")

    async def log_audit(self, message: str):
        """Log audit notices to console and Discord log channel (Level: info/audit)."""
        print(f"📋 {message}")
        if await self._should_log("audit"):
            await self._send_to_log_channel(f"📋 **GenHub Log:** {message}")

    async def log_debug(self, message: str):
        """Log verbose debugging info to console and Discord log channel (Level: verbose/debug/all)."""
        print(f"🔍 {message}")
        if await self._should_log("debug"):
            await self._send_to_log_channel(f"🔍 {message}")

    async def _make_github_request(self, session, url, method='GET'):
        """Make a GitHub API request with rate limiting and error handling."""
        await self.rate_limiter.wait()
        
        try:
            async with session.request(method, url) as resp:
                self.rate_limiter.update_from_headers(resp.headers)
                
                # Handle rate limit exceeded
                if resp.status == 403 and 'rate limit' in (await resp.text()).lower():
                    reset_time = int(resp.headers.get('X-RateLimit-Reset', 0))
                    wait_time = max(0, reset_time - time.time()) + 5
                    print(f"⏳ Rate limit exceeded, waiting {wait_time:.0f}s...")
                    await asyncio.sleep(wait_time)
                    # Retry once
                    return await self._make_github_request(session, url, method)
                
                return resp.status, await resp.json() if resp.status == 200 else None
        except Exception as e:
            print(f"❌ Request failed for {url}: {e}")
            return None, None

    async def _fetch_comments(self, session, repo, number, is_pr):
        """Fetch all comments for an issue or PR."""
        comments = []
        page = 1
        
        # Fetch issue/PR comments
        while page <= 10:  # Limit pages to avoid excessive requests
            url = f"https://api.github.com/repos/{repo}/issues/{number}/comments?per_page=100&page={page}"
            status, data = await self._make_github_request(session, url)
            
            if status != 200 or not data:
                break
            
            comments.extend(data)
            
            if len(data) < 100:
                break
            
            page += 1
        
        # Fetch PR review comments and top-level reviews if it's a PR
        if is_pr:
            # 1. PR inline diff review comments
            page = 1
            while page <= 10:
                url = f"https://api.github.com/repos/{repo}/pulls/{number}/comments?per_page=100&page={page}"
                status, data = await self._make_github_request(session, url)

                if status != 200 or not data:
                    break

                for comment in data:
                    comment['is_review_comment'] = True
                comments.extend(data)

                if len(data) < 100:
                    break
                page += 1

            # 2. PR top-level review submissions (e.g. CodeRabbit summary / approval bodies)
            page = 1
            while page <= 5:
                url = f"https://api.github.com/repos/{repo}/pulls/{number}/reviews?per_page=100&page={page}"
                status, data = await self._make_github_request(session, url)

                if status != 200 or not data:
                    break

                for rev in data:
                    body = rev.get("body")
                    if body and body.strip():
                        rev["is_review_comment"] = True
                        rev["created_at"] = rev.get("submitted_at") or rev.get("created_at")
                        comments.append(rev)

                if len(data) < 100:
                    break
                page += 1

        # Sort by creation date
        comments.sort(key=lambda c: c.get('created_at', ''))
        return comments

    async def _post_comment_to_thread(self, thread, comment, role_mention, extra_count: int = 0, repo: str = None):
        """Post a single comment to a Discord thread formatted as a sleek Discord embed."""
        body = comment.get("body", "")
        if not body or body.strip() == "":
            return

        author = comment.get("user", {}).get("login", "Unknown") if comment.get("user") else "Unknown"
        author_icon = comment.get("user", {}).get("avatar_url") if comment.get("user") else None
        url = comment.get("html_url", "")
        created_at = comment.get("created_at")
        is_bot = is_bot_author(author, comment.get("user"))
        is_review = comment.get("is_review_comment", False)

        embed = create_comment_embed(
            author=author,
            body=body,
            url=url,
            author_icon=author_icon,
            is_bot=is_bot,
            is_review=is_review,
            extra_count=extra_count,
            created_at=created_at,
            repo=repo,
        )

        view = create_review_link_view(url, max(extra_count, 1)) if is_bot else None
        try:
            await send_message(thread, embed=embed, view=view)
        except Exception as e:
            print(f"⚠️ Failed to post comment embed to thread: {e}")

    # ---------------------------
    # Entry Point
    # ---------------------------

    async def process_payload(self, request, data):
        event_type = request.headers.get("X-GitHub-Event", "unknown")
        action = data.get("action", "")
        action_suffix = f".{action}" if action else ""

        if event_type == "ping":
            zen = data.get("zen", "No zen")
            hook_id = data.get("hook_id", "N/A")
            print(f"🏓 [Webhook] Ping received from GitHub (Hook ID: {hook_id}) | Zen: {zen}")
            await self.log_audit(f"🏓 **GitHub Webhook Ping Received!** (Hook ID: `{hook_id}` • Zen: *{zen}*)")
            return

        repo_full_name = data.get("repository", {}).get("full_name")
        allowed_repos = await self.cog.config.allowed_repos()
        normalized_allowed = [r.lower().strip().lstrip("/") for r in allowed_repos]

        if not repo_full_name or repo_full_name.lower().strip().lstrip("/") not in normalized_allowed:
            warn_msg = f"⚠️ [Webhook] Ignored '{event_type}{action_suffix}' for '{repo_full_name}': not in allowed_repos list (Configured: {allowed_repos}). Run '!genhub addrepo {repo_full_name}' to allow."
            print(warn_msg)
            await self.log_error(warn_msg)
            return

        print(f"📦 [Webhook] Dispatching '{event_type}{action_suffix}' for '{repo_full_name}'")
        await self.log_info(f"📦 **[Webhook]** Received `{event_type}{action_suffix}` for `{repo_full_name}`")
        handlers = {
            "issues": self.handle_issue,
            "pull_request": self.handle_pull_request,
            "issue_comment": self.handle_issue_comment,
            "pull_request_review": self.handle_pull_request_review,
            "pull_request_review_comment": self.handle_pull_request_review_comment,
            "release": self.handle_release,
        }
        handler = handlers.get(event_type)
        if handler:
            await handler(data, repo_full_name)
            print(f"✅ [Webhook] Finished handling '{event_type}{action_suffix}' for '{repo_full_name}'")
        else:
            print(f"ℹ️ [Webhook] No handler for event '{event_type}' (repo: {repo_full_name}), skipping")
            await self.log_debug(f"ℹ️ No handler for event `{event_type}` (repo: `{repo_full_name}`), skipped")

    # ---------------------------
    # Event Handlers
    # ---------------------------

    async def handle_issue(self, data, repo_full_name):
        issue = data["issue"]
        number, title, url, author, action = (
            issue["number"],
            issue["title"],
            issue["html_url"],
            issue["user"]["login"],
            data["action"],
        )
        await self.log_info(f"🆕 **Issue {action.capitalize()}:** [#{number} {title}]({url}) • By **{author}** in `{repo_full_name}`")

        forum_id = await self.cog.config.issues_forum_id()
        forum = await self._resolve_target_channel(forum_id)
        tags = await get_issue_tags(forum, issue)

        # Role mention for issue chat
        role_mention = get_role_mention(
            forum.guild if forum else None, await self.cog.config.contributor_role_id()
        )
        initial_content = None
        if action == "opened":
            initial_content = format_message("🆕", "Issue created", title, url, author, "")

        thread, _ = await get_or_create_thread(
            self.cog.bot,
            forum_id,
            repo_full_name,
            number,
            title,
            url,
            tags,
            self.cog.thread_cache,
            initial_content,
        )
        if not thread:
            return

        # Send action-specific messages (skip "opened" if we already sent initial content)
        if action == "opened" and initial_content:
            pass
        elif action == "closed":
            await update_status_tag(thread, "Closed")
            await send_message(
                thread,
                format_message("❌", "Issue closed", title, url, author, ""),
            )
        elif action == "reopened":
            await update_status_tag(thread, "Open")
            await send_message(
                thread,
                format_message("🔄", "Issue reopened", title, url, author, ""),
            )
        elif action in ("assigned", "unassigned"):
            assignee = issue.get("assignee")
            assignee_text = (
                f"[{assignee['login']}]({assignee['html_url']})"
                if assignee
                else "Unknown"
            )
            await send_message(
                thread,
                f"👤 **Issue {action}:** {assignee_text}\n🔧 Updated by: **{author}**",
            )

        # Send concise overview notification to Issues Feed Chat channel/post (discovered in forum if not explicitly set)
        chat_ch = await self._get_or_discover_feed_chat(forum_id, "issues_feed_chat_id")
        if chat_ch:
            thread_ref = f"<#{thread.id}>" if thread else ""
            thread_suffix = f" • Thread: {thread_ref}" if thread_ref else ""
            try:
                if action == "opened":
                    await chat_ch.send(f"🆕 **Issue Created:** [#{number} {title}]({url}){thread_suffix} • By **{author}** {role_mention}".strip())
                elif action == "closed":
                    await chat_ch.send(f"❌ **Issue Closed:** [#{number} {title}]({url}){thread_suffix} • By **{author}** {role_mention}".strip())
                elif action == "reopened":
                    await chat_ch.send(f"🔄 **Issue Reopened:** [#{number} {title}]({url}){thread_suffix} • By **{author}**")
            except Exception as e:
                print(f"⚠️ Failed to send issue chat notification: {e}")

        # Send milestone/status update to Pinned Updates channel/post
        updates_ch_id = await self._get_config_id("updates_channel_id")
        if updates_ch_id:
            updates_ch = await self._resolve_target_channel(updates_ch_id)
            if updates_ch:
                thread_ref = f" • Thread: <#{thread.id}>" if thread else ""
                try:
                    if action == "opened":
                        await updates_ch.send(f"📋 **New Issue Opened:** [**#{number} {title}**](<{url}>){thread_ref} • By **{author}**")
                    elif action == "closed":
                        await updates_ch.send(f"✅ **Issue Closed:** [**#{number} {title}**](<{url}>){thread_ref} • By **{author}**")
                except Exception as e:
                    print(f"⚠️ Failed to send issue update notification: {e}")

    async def handle_pull_request(self, data, repo_full_name):
        pr = data["pull_request"]
        number, title, url, author, action = (
            pr["number"],
            pr["title"],
            pr["html_url"],
            pr["user"]["login"],
            data["action"],
        )
        merged_indicator = " (Merged)" if (action == "closed" and (pr.get("merged") or pr.get("merged_at"))) else ""
        await self.log_info(f"🔄 **PR {action.capitalize()}{merged_indicator}:** [#{number} {title}]({url}) • By **{author}** in `{repo_full_name}`")

        forum_id = await self.cog.config.prs_forum_id()
        forum = await self._resolve_target_channel(forum_id)
        tags = await get_pr_tags(forum, pr)

        # Role mention for PRs: only when opened or closed/merged in PR chat
        role_mention = get_role_mention(
            forum.guild if forum else None, await self.cog.config.contributor_role_id()
        )
        initial_content = None
        if action == "opened":
            initial_content = format_message("🆕", "PR created", title, url, author, "")

        thread, _ = await get_or_create_thread(
            self.cog.bot, forum_id, repo_full_name, number, title, url, tags, self.cog.thread_cache, initial_content
        )
        if not thread:
            return

        # Send action-specific messages (skip "opened" if we already sent initial content)
        if action == "opened" and initial_content:
            # Initial content already sent during thread creation
            pass
        elif action == "closed":
            if pr.get("merged") or pr.get("merged_at"):
                await update_status_tag(thread, "Merged")
                # No role mention inside thread (role tagged in prchat)
                await send_message(thread, format_message("✅", "PR merged", title, url, author, ""))
            else:
                await update_status_tag(thread, "Closed")
                # No role mention inside thread
                await send_message(thread, format_message("❌", "PR closed", title, url, author, ""))
        elif action == "reopened":
            await update_status_tag(thread, "Open")
            # No role mention on reopen
            await send_message(thread, format_message("🔄", "PR reopened", title, url, author, ""))
        elif action in ("assigned", "unassigned"):
            assignee = pr.get("assignee")
            assignee_text = f"[{assignee['login']}]({assignee['html_url']})" if assignee else "Unknown"
            await send_message(thread, f"👤 **PR {action}:** {assignee_text}\n🔧 Updated by: **{author}**")

        # Send concise overview notification to PRs Feed Chat channel/post (discovered in forum if not explicitly set)
        chat_ch = await self._get_or_discover_feed_chat(forum_id, "prs_feed_chat_id")
        if chat_ch:
            thread_ref = f"<#{thread.id}>" if thread else ""
            thread_suffix = f" • Thread: {thread_ref}" if thread_ref else ""
            try:
                if action == "opened":
                    await chat_ch.send(f"🆕 **PR Opened:** [#{number} {title}]({url}){thread_suffix} • By **{author}** {role_mention}".strip())
                elif action == "closed":
                    if pr.get("merged") or pr.get("merged_at"):
                        await chat_ch.send(f"🟣 **PR Merged:** [#{number} {title}]({url}){thread_suffix} • By **{author}** {role_mention}".strip())
                    else:
                        await chat_ch.send(f"❌ **PR Closed (Unmerged):** [#{number} {title}]({url}){thread_suffix} • By **{author}** {role_mention}".strip())
                elif action == "reopened":
                    await chat_ch.send(f"🔄 **PR Reopened:** [#{number} {title}]({url}){thread_suffix} • By **{author}**")
            except Exception as e:
                print(f"⚠️ Failed to send PR chat notification: {e}")

        # Send development milestone announcement to Pinned Updates channel (No role mentions)
        updates_ch_id = await self._get_config_id("updates_channel_id")
        if updates_ch_id:
            updates_ch = await self._resolve_target_channel(updates_ch_id)
            if updates_ch:
                thread_ref = f" • Thread: <#{thread.id}>" if thread else ""
                try:
                    if action == "opened":
                        await updates_ch.send(f"🚀 **New PR Opened:** [**#{number} {title}**](<{url}>){thread_ref} • By **{author}**")
                    elif action == "closed":
                        if pr.get("merged") or pr.get("merged_at"):
                            base_ref = pr.get("base", {}).get("ref", "main")
                            msg = f"🔨 **Merged into `{base_ref}`:** [**#{number} {title}**](<{url}>){thread_ref} • By **{author}**"
                            await updates_ch.send(msg)
                        else:
                            await updates_ch.send(f"❌ **PR Closed (Unmerged):** [**#{number} {title}**](<{url}>){thread_ref} • By **{author}**")
                except Exception as e:
                    print(f"⚠️ Failed to send pinned update on PR: {e}")

    async def handle_release(self, data, repo_full_name):
        """Handle GitHub release events and announce to Pinned Updates channel with prominent visual styling."""
        action = data.get("action")
        if action not in ("published", "created", "released"):
            return

        release = data.get("release", {})
        tag_name = release.get("tag_name", "")
        name = release.get("name") or tag_name or "New Release"
        body = release.get("body", "")
        url = release.get("html_url", "")
        author = release.get("author", {}).get("login", "Unknown")
        author_icon = release.get("author", {}).get("avatar_url")
        is_prerelease = release.get("prerelease", False) or "alpha" in tag_name.lower() or "beta" in tag_name.lower()

        updates_ch_id = await self._get_config_id("updates_channel_id")
        await self.log_info(f"🎉 **Release {action.capitalize()}:** [{name} ({tag_name})]({url}) • In `{repo_full_name}`")
        if updates_ch_id:
            updates_ch = await self._resolve_target_channel(updates_ch_id)
            if updates_ch:
                try:
                    clean_body = clean_github_markdown(body)
                    if len(clean_body) > 1800:
                        clean_body = clean_body[:1700].rstrip() + f"\n\n... *([Read full changelog on GitHub](<{url}>))*"

                    # Distinctive styling: Magenta for Alpha/Beta/Pre-release, Blurple for Official Releases
                    badge = "🧪 Alpha / Pre-release" if is_prerelease else "🎉 Official Release"
                    color = 0xEB459E if is_prerelease else 0x5865F2

                    embed = discord.Embed(
                        title=f"{badge}: {name} ({tag_name})",
                        url=url,
                        description=(clean_body if clean_body else f"Release **{tag_name}** is now available.") + f"\n\n↳ 📦 [**Download Release Assets on GitHub**](<{url}>)",
                        color=color,
                    )
                    embed.set_author(
                        name=f"Published by {author} ({repo_full_name})",
                        url=url,
                        icon_url=author_icon if author_icon else "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png",
                    )
                    embed.set_footer(text=f"GeneralsHub Release Announcement • {repo_full_name}")
                    await updates_ch.send(embed=embed)
                except Exception as e:
                    print(f"⚠️ Failed to send release announcement: {e}")

    async def handle_issue_comment(self, data, repo_full_name):
        if data.get("action") and data.get("action") != "created":
            return
        issue = data["issue"]
        number, body, author, url = (
            issue["number"],
            data["comment"]["body"],
            data["comment"]["user"]["login"],
            data["comment"]["html_url"],
        )
        await self.log_debug(f"💬 **Comment on #{number}:** By **{author}** in `{repo_full_name}`")
        is_pr = "pull_request" in issue
        forum_id = await (self.cog.config.prs_forum_id() if is_pr else self.cog.config.issues_forum_id())
        forum = self.cog.bot.get_channel(forum_id)
        tags = await (get_pr_tags(forum, issue) if is_pr else get_issue_tags(forum, issue))
        thread, _ = await get_or_create_thread(
            self.cog.bot, forum_id, repo_full_name, number, issue["title"], issue["html_url"], tags, self.cog.thread_cache
        )
        if not thread or not body:
            return

        author_icon = data["comment"]["user"].get("avatar_url") if data["comment"].get("user") else None
        is_bot = is_bot_author(author, data["comment"].get("user"))
        created_at = data["comment"].get("created_at")
        embed = create_comment_embed(
            author=author,
            body=body,
            url=url,
            author_icon=author_icon,
            is_bot=is_bot,
            is_review=False,
            created_at=created_at,
            repo=repo_full_name,
        )
        view = create_review_link_view(url, 1) if is_bot else None
        await send_message(thread, embed=embed, view=view)

    async def handle_pull_request_review(self, data, repo_full_name):
        if data.get("action") != "submitted":
            return
        pr_number = data["pull_request"]["number"]
        review_id = data["review"]["id"]
        review_body = data["review"]["body"]
        review_author = data["review"]["user"]["login"]
        review_url = data["review"]["html_url"]

        key = (repo_full_name, pr_number, review_id)
        entry = self.pending_reviews.setdefault(
            key, {"author": review_author, "url": review_url, "body": None, "comments": []}
        )
        entry["body"] = review_body
        await self._schedule_flush(repo_full_name, pr_number, review_id, data)

    async def handle_pull_request_review_comment(self, data, repo_full_name):
        if data.get("action") and data.get("action") != "created":
            return
        pr_number = data["pull_request"]["number"]
        review_id = data["comment"]["pull_request_review_id"]
        comment_body = data["comment"]["body"]
        comment_author = data["comment"]["user"]["login"]
        comment_url = data["comment"]["html_url"]

        key = (repo_full_name, pr_number, review_id)
        entry = self.pending_reviews.setdefault(
            key, {"author": comment_author, "url": comment_url, "body": None, "comments": []}
        )
        entry["comments"].append((comment_body, comment_url))
        await self._schedule_flush(repo_full_name, pr_number, review_id, data)

    async def _schedule_flush(self, repo_full_name, pr_number, review_id, data):
        key = (repo_full_name, pr_number, review_id)

        async def flush():
            await asyncio.sleep(2)
            entry = self.pending_reviews.pop(key, None)
            if not entry:
                return

            forum_id = await self.cog.config.prs_forum_id()
            forum = self.cog.bot.get_channel(forum_id)
            pr_data = data.get("pull_request") or data.get("issue")
            if not pr_data:
                return

            tags = await get_pr_tags(forum, pr_data)
            thread, _ = await get_or_create_thread(
                self.cog.bot, forum_id, repo_full_name, pr_number, pr_data["title"], pr_data["html_url"], tags, self.cog.thread_cache
            )
            if not thread:
                return

            is_bot = is_bot_author(entry["author"])
            extra_comments = len(entry["comments"]) if (is_bot and len(entry["comments"]) > 1) else 0

            created_at = data.get("review", {}).get("submitted_at") or pr_data.get("created_at")
            await self.log_info(f"📝 **PR Review Posted:** PR #{pr_number} by **{entry['author']}** in `{repo_full_name}`")
            view = create_review_link_view(entry["url"], extra_comments) if extra_comments > 0 else None
            if entry["body"]:
                embed = create_comment_embed(
                    author=entry["author"],
                    body=entry["body"],
                    url=entry["url"],
                    is_bot=is_bot,
                    is_review=True,
                    extra_count=extra_comments,
                    created_at=created_at,
                    repo=repo_full_name,
                )
                await send_message(thread, embed=embed, view=view)

            if entry["comments"]:
                if is_bot and len(entry["comments"]) > 1:
                    if not entry["body"]:
                        bot_summary = (
                            f"🤖 **{entry['author']}** submitted **{len(entry['comments'])} inline review comments** on GitHub.\n"
                            f"> 🔍 [**Click here to inspect all {len(entry['comments'])} comments on GitHub ➔**](<{entry['url']}>)"
                        )
                        btn_view = create_review_link_view(entry["url"], len(entry["comments"]))
                        await send_message(thread, bot_summary, view=btn_view)
                else:
                    for i, (body, url) in enumerate(reversed(entry["comments"])):
                        embed = create_comment_embed(
                            author=entry["author"],
                            body=body,
                            url=url,
                            is_bot=is_bot,
                            is_review=True,
                            created_at=created_at,
                            repo=repo_full_name,
                        )
                        await send_message(thread, embed=embed)

        if key in self.pending_reviews and "task" in self.pending_reviews[key]:
            self.pending_reviews[key]["task"].cancel()
        self.pending_reviews[key]["task"] = asyncio.create_task(flush())

    # ---------------------------
    # Reconciliation
    # ---------------------------

    async def _reconcile_item(self, session, forum, repo, item, is_pr, ctx, idx, repo_name):
        number = item["number"]
        title = item["title"]
        url = item["html_url"]
        author = item["user"]["login"] if item.get("user") else "Unknown"
        forum_id = forum.id

        # Only reconcile open items (skip closed/merged issues and PRs)
        if item.get("state") != "open":
            await self.log_debug(f"⏭️ Skipping non-open {('PR' if is_pr else 'issue')} {repo}#{number} ({item.get('state')})")
            return

        # Compute desired tags
        tags = await (get_pr_tags(forum, item) if is_pr else get_issue_tags(forum, item))
        repo_tag = await get_or_create_tag(forum, repo.split("/")[-1])
        if repo_tag and repo_tag not in tags:
            tags.append(repo_tag)

        # Prepare initial content (only tag role on PRs)
        role_mention = (
            get_role_mention(forum.guild, await self.cog.config.contributor_role_id())
            if is_pr
            else ""
        )
        emoji = "🆕"
        action = "PR created" if is_pr else "Issue created"
        initial_content = format_message(emoji, action, title, url, author, role_mention, number=number)

        # Get or create thread
        thread, created = await get_or_create_thread(
            self.cog.bot, forum_id, repo, number, title, url, tags, 
            self.cog.thread_cache, initial_content
        )
        
        if not thread:
            await self.log_error(f"❌ Failed to create/find forum thread for {repo}#{number} ({title[:80]})")
            return

        await self.log_debug(f"{'✅ Created' if created else '📝 Found existing'} thread for {repo}#{number}")

        # Handle initial message for existing threads
        if not created:
            try:
                history = []
                async for message in thread.history(limit=1, oldest_first=True):
                    history.append(message)
                    break

                if not history:
                    await send_message(thread, initial_content)
                    await self.log_debug(f"📝 Sent initial message to existing empty thread {repo}#{number}")
            except Exception as e:
                await self.log_error(f"⚠️ Could not check thread history for {repo}#{number}: {e}")

        if self.reconcile_cancelled:
            return

        # Reconcile tags (only if different)
        current = set(t.name.lower() for t in (thread.applied_tags or []))
        desired = set(t.name.lower() for t in (tags or []))
        if current != desired and not created:
            try:
                await thread.edit(applied_tags=tags or [])
            except Exception as e:
                await self.log_error(f"⚠️ Could not update tags for {repo}#{number}: {e}")

        # Check if item has any comments before making API requests
        # Note: GitHub issues endpoint returns 'comments' count, but pulls list endpoint does not.
        should_fetch_comments = True
        if not is_pr and item.get("comments") is not None and item.get("comments") == 0:
            should_fetch_comments = False

        if should_fetch_comments and not self.reconcile_cancelled:
            # Fetch and post comments with bot spam protection
            try:
                await self.log_debug(f"📥 Fetching comments and reviews for {repo}#{number}...")
                comments = await self._fetch_comments(session, repo, number, is_pr)

                if comments and not self.reconcile_cancelled:
                    # Get existing message URLs and bot authors in thread to avoid duplicates
                    existing_comment_urls = set()
                    existing_bot_authors = set()
                    if not created:
                        try:
                            async for message in thread.history(limit=50):
                                if message.content:
                                    urls = re.findall(r'https://github\.com/[^/]+/[^/]+/(?:issues|pull)/\d+[#\w\-]+', message.content)
                                    existing_comment_urls.update(urls)
                                for emb in getattr(message, "embeds", []):
                                    if emb.author and emb.author.name:
                                        # e.g. "deepsource-io[bot] (Bot Notice)" -> "deepsource-io[bot]"
                                        author_token = emb.author.name.split(" ")[0].lower().strip()
                                        existing_bot_authors.add(author_token)
                                    if emb.author and emb.author.url:
                                        existing_comment_urls.add(emb.author.url)
                                    if emb.description:
                                        urls = re.findall(r'https://github\.com/[^/]+/[^/]+/(?:issues|pull)/\d+[#\w\-]+', emb.description)
                                        existing_comment_urls.update(urls)
                        except Exception as e:
                            await self.log_error(f"⚠️ Could not check existing comments for {repo}#{number}: {e}")

                    # Separate comments into human comments and bot comments
                    human_comments = []
                    bot_comments_by_author = {}

                    for comment in comments:
                        author_login = comment.get('user', {}).get('login', 'Unknown')
                        if is_bot_author(author_login, comment.get('user')):
                            bot_comments_by_author.setdefault(author_login, []).append(comment)
                        else:
                            comment_url = comment.get('html_url', '')
                            if comment_url and comment_url in existing_comment_urls:
                                continue
                            human_comments.append(comment)

                    # 1. Post human comments
                    for comment in human_comments:
                        if self.reconcile_cancelled:
                            break
                        await self._post_comment_to_thread(thread, comment, role_mention, repo=repo)
                        await asyncio.sleep(0.2)

                    # 2. Post bot comments cleanly as at most 1 compact embed per bot (skip if bot already posted in thread)
                    for bot_name, b_comments in bot_comments_by_author.items():
                        if self.reconcile_cancelled:
                            break
                        if not b_comments:
                            continue

                        # If thread already has an embed from this bot, skip it to avoid duplicate reviews
                        if bot_name.lower().strip() in existing_bot_authors:
                            await self.log_debug(f"ℹ️ Skipping bot review from {bot_name} on {repo}#{number} (already in thread)")
                            continue

                        # Also check if any URL from b_comments is already in existing_comment_urls
                        if any(c.get('html_url', '') in existing_comment_urls for c in b_comments if c.get('html_url')):
                            continue

                        # Sort comments chronologically and post the latest/most recent review status
                        b_comments.sort(key=lambda c: c.get('created_at', ''))
                        latest_bot_comment = b_comments[-1]
                        extra_count = len(b_comments) - 1
                        await self._post_comment_to_thread(
                            thread,
                            latest_bot_comment,
                            role_mention,
                            extra_count=extra_count,
                            repo=repo,
                        )
                        existing_bot_authors.add(bot_name.lower().strip())
                        await asyncio.sleep(0.2)

            except Exception as e:
                await self.log_error(f"⚠️ Error fetching/posting comments for {repo}#{number}: {e}")

    async def reconcile_forum_tags(self, ctx=None, repo_filter: str = None):
        self.is_reconciling = True
        self.reconcile_cancelled = False

        try:
            allowed_repos = await self.cog.config.allowed_repos()
            print(f"🔍 Starting reconcile. Allowed repos: {allowed_repos}")
            await self.log_info(f"🔄 **Reconciliation Started** for {len(allowed_repos)} repositories ({', '.join(allowed_repos)})")
            
            token = await self.cog.config.github_token()
            headers = {"Accept": "application/vnd.github.v3+json"}
            if token:
                headers["Authorization"] = f"token {token}"
                await self.log_debug("✅ GitHub Token set in headers")
            else:
                await self.log_error("❌ No GitHub token configured for API requests")

            # Reset rate limiter for reconciliation
            self.rate_limiter = RateLimiter()

            async with aiohttp.ClientSession(headers=headers) as session:
                processed_repos = set()
                for repo in allowed_repos:
                    if self.reconcile_cancelled:
                        if ctx:
                            await ctx.send("🛑 Reconciliation cancelled by user.")
                        return

                    if repo_filter and repo != repo_filter:
                        continue
                        
                    repo = repo.strip().lstrip("/")
                    if repo in processed_repos:
                        await self.log_debug(f"⏭️ Skipping already processed repo: {repo}")
                        continue
                        
                    processed_repos.add(repo)
                    repo_name = repo.split("/")[-1]
                    await self.log_info(f"🔄 **Reconciling repository:** `{repo}`")
                    if ctx:
                        await ctx.send(f"🔄 Reconciling repo: {repo}")

                    # Check if repository exists
                    repo_check_url = f"https://api.github.com/repos/{repo}"
                    await self.log_debug(f"🔍 Checking if repository {repo} exists...")
                    
                    status, _ = await self._make_github_request(session, repo_check_url)
                    
                    if status == 404:
                        await self.log_error(f"❌ Repository `{repo}` does not exist on GitHub (404)")
                        if ctx:
                            await ctx.send(f"❌ Repository '{repo}' does not exist.")
                        continue
                    elif status == 403:
                        await self.log_error(f"🚫 Cannot access repository `{repo}` (403 Forbidden - check token permissions)")
                        if ctx:
                            await ctx.send(f"🚫 Cannot access '{repo}'. Check token permissions.")
                        continue
                    elif status == 401:
                        await self.log_error(f"🚫 GitHub authentication failed for `{repo}` (401 Unauthorized)")
                        if ctx:
                            await ctx.send(f"🚫 GitHub authentication failed. Check your token.")
                        continue
                    elif status != 200:
                        await self.log_error(f"⚠️ Unexpected status {status} checking repository `{repo}`")
                        if ctx:
                            await ctx.send(f"⚠️ Cannot verify repository '{repo}'")
                        continue
                    else:
                        await self.log_debug(f"✅ Repository {repo} exists and is accessible")

                    # Process issues
                    await self._reconcile_repo_items(session, repo, repo_name, False, ctx)
                    if self.reconcile_cancelled:
                        if ctx:
                            await ctx.send("🛑 Reconciliation cancelled by user.")
                        return

                    # Process PRs
                    await self._reconcile_repo_items(session, repo, repo_name, True, ctx)
                    if self.reconcile_cancelled:
                        if ctx:
                            await ctx.send("🛑 Reconciliation cancelled by user.")
                        return

            print("🎉 Reconciliation process finished!")
            await self.log_info("🎉 **Reconciliation Finished** successfully")
            if ctx:
                await ctx.send("✅ Reconciliation complete.")
        finally:
            self.is_reconciling = False

    async def _reconcile_repo_items(self, session, repo, repo_name, is_pr, ctx):
        """Reconcile issues or PRs for a repository with bounded parallel workers."""
        if self.reconcile_cancelled:
            return

        item_type = "PRs" if is_pr else "issues"
        endpoint = "pulls" if is_pr else "issues"
        forum_id = await (self.cog.config.prs_forum_id() if is_pr else self.cog.config.issues_forum_id())

        print(f"📋 {item_type} forum ID: {forum_id}")
        forum = await self._resolve_target_channel(forum_id)

        if not forum:
            await self.log_error(f"⚠️ {item_type} forum ID `{forum_id}` not found/accessible in Discord")
            if ctx:
                await ctx.send(f"⚠️ {item_type} forum not configured, skipping for {repo}")
            return

        await self.log_debug(f"✅ {item_type} forum found: {getattr(forum, 'name', forum_id)} ({forum_id})")

        # Collect all GitHub items (only fetch OPEN items for both issues and PRs)
        github_items = {}
        items_to_process = []
        page = 1
        max_pages = 50
        state_param = "open"  # Only fetch OPEN issues and OPEN PRs

        while page <= max_pages:
            if self.reconcile_cancelled:
                return

            url = f"https://api.github.com/repos/{repo}/{endpoint}?state={state_param}&per_page=100&page={page}"
            await self.log_debug(f"🌐 Fetching open {item_type.lower()} page {page} for {repo}")

            status, data = await self._make_github_request(session, url)

            if status != 200:
                await self.log_error(f"⚠️ Failed to fetch open {item_type.lower()} for `{repo}` (status: {status})")
                if ctx:
                    await ctx.send(f"⚠️ Failed to fetch {item_type.lower()} for '{repo}'")
                return

            if not data or len(data) == 0:
                break

            for item in data:
                if self.reconcile_cancelled:
                    return

                # Filter out PRs from issues endpoint
                if not is_pr and item.get("pull_request"):
                    continue

                # Skip any non-open item
                if item.get("state") != "open":
                    continue

                number = item["number"]
                github_items[number] = item
                items_to_process.append(item)

            if len(data) < 100:
                break
            page += 1

        total_count = len(items_to_process)
        if total_count == 0:
            await self.log_debug(f"ℹ️ No open {item_type.lower()} found to reconcile for {repo}")
            if ctx:
                await ctx.send(f"ℹ️ No {item_type.lower()} to reconcile for `{repo}`.")
            return

        await self.log_info(f"⚡ Reconciling **{total_count} open {item_type.lower()}** for `{repo}` in parallel (4 workers)...")
        if ctx:
            await ctx.send(f"⚡ Reconciling **{total_count} {item_type.lower()}** for `{repo}` in parallel (4 concurrent workers)...")

        # Bounded parallel workers with Semaphore
        concurrency_limit = 4
        sem = asyncio.Semaphore(concurrency_limit)
        processed_count = 0
        progress_lock = asyncio.Lock()

        async def worker(item, idx):
            nonlocal processed_count
            if self.reconcile_cancelled:
                return
            async with sem:
                if self.reconcile_cancelled:
                    return
                try:
                    await self._reconcile_item(session, forum, repo, item, is_pr, ctx, idx, repo_name)
                except Exception as e:
                    await self.log_error(f"❌ Error reconciling {item_type.lower()[:-1]} {repo}#{item.get('number')}: {e}")

                async with progress_lock:
                    processed_count += 1
                    if ctx and not self.reconcile_cancelled and (processed_count % 15 == 0 or processed_count == total_count):
                        pct = int((processed_count / total_count) * 100)
                        await ctx.send(f"📊 **Progress ({repo_name} {item_type}):** {processed_count}/{total_count} processed ({pct}%)")

        tasks = [worker(item, i + 1) for i, item in enumerate(items_to_process)]
        await asyncio.gather(*tasks)

        await self.log_info(f"✅ {item_type} reconciliation complete for `{repo}`: **{processed_count}/{total_count}** processed")
        if ctx and not self.reconcile_cancelled:
            await ctx.send(f"✅ Processed {processed_count}/{total_count} {item_type.lower()} for `{repo}`")

        # Clean up orphaned threads (only for issues; PRs only reconcile open ones so closed PR threads are preserved)
        if not is_pr:
            await self._cleanup_orphaned_threads(forum, repo, github_items, is_pr)

    async def _cleanup_orphaned_threads(self, forum, repo, github_items, is_pr):
        """Clean up threads that exist in forum but don't have corresponding GitHub items."""
        item_type = "PRs" if is_pr else "issues"
        print(f"🧹 Checking for orphaned {item_type.lower()} threads in {forum.name}...")

        # Get all threads in the forum
        all_threads = []
        orphaned_count = 0

        # Check active threads
        try:
            for thread in forum.threads:
                all_threads.append(thread)
        except (TypeError, AttributeError):
            pass  # Handle mock objects in tests

        # Check archived threads (limit to avoid excessive API calls)
        if hasattr(forum, "archived_threads"):
            try:
                async for thread in forum.archived_threads(limit=100):  # Reasonable limit
                    all_threads.append(thread)
            except (TypeError, AttributeError):
                pass  # Handle mock objects in tests

        # Check each thread to see if it corresponds to a GitHub item
        for thread in all_threads:
            try:
                # Extract issue/PR number from thread name
                import re
                match = re.search(r'\[GH\]\s*\[#(\d+)\]', thread.name)
                if not match:
                    continue

                number = int(match.group(1))

                # Check if this thread corresponds to our repository
                # Look for the repo tag or check thread content
                repo_tag_found = False
                if hasattr(thread, 'applied_tags') and thread.applied_tags:
                    for tag in thread.applied_tags:
                        if hasattr(tag, 'name') and tag.name.lower() == repo.split('/')[-1].lower():
                            repo_tag_found = True
                            break

                if not repo_tag_found:
                    continue  # This thread is for a different repo

                # Check if GitHub item still exists
                if number not in github_items:
                    orphaned_count += 1
                    print(f"🗑️ Found orphaned {item_type.lower()[:-1]} thread: #{number} - {thread.name[:50]}...")

                    # Try to delete the orphaned thread
                    try:
                        await thread.delete()
                        print(f"✅ Deleted orphaned thread #{number}")
                    except discord.Forbidden:
                        print(f"⚠️ Cannot delete thread #{number}: Missing permissions")
                    except discord.NotFound:
                        print(f"ℹ️ Thread #{number} already deleted or not found")
                    except Exception as e:
                        print(f"⚠️ Failed to delete orphaned thread #{number}: {e}")

            except Exception as e:
                print(f"⚠️ Error checking thread {getattr(thread, 'name', 'unknown')}: {e}")
                continue

        if orphaned_count > 0:
            print(f"🧹 Cleaned up {orphaned_count} orphaned {item_type.lower()} threads")
        else:
            print(f"✅ No orphaned {item_type.lower()} threads found")
