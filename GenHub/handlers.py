import discord
import asyncio
import aiohttp
import re
import os
from .utils import (
    send_message,
    get_role_mention,
    format_message,
    get_issue_tags,
    get_pr_tags,
    update_status_tag,
    get_or_create_thread,
    get_or_create_tag,
)

GITHUB_ISSUE_RE = re.compile(
    r"https://github\.com/([^/]+)/([^/]+)/(issues|pull)/(\d+)"
)


class GitHubEventHandlers:
    def __init__(self, cog):
        self.cog = cog
        self.pending_reviews = {}

    async def log_error(self, message: str):
        """Log errors to console and optionally to a Discord log channel."""
        print(f"❌ GenHub Error: {message}")
        log_channel_id = await self.cog.config.log_channel_id()
        if log_channel_id:
            channel = self.cog.bot.get_channel(log_channel_id)
            if channel:
                try:
                    await channel.send(f"❌ **GenHub Error:**\n```{message}```")
                except Exception as e:
                    print(f"⚠️ Failed to send error log to channel: {e}")

    # ---------------------------
    # Entry Point
    # ---------------------------

    async def process_payload(self, request, data):
        repo_full_name = data.get("repository", {}).get("full_name")
        allowed_repos = await self.cog.config.allowed_repos()
        if repo_full_name not in allowed_repos:
            return

        event_type = request.headers.get("X-GitHub-Event")
        handlers = {
            "issues": self.handle_issue,
            "pull_request": self.handle_pull_request,
            "issue_comment": self.handle_issue_comment,
            "pull_request_review": self.handle_pull_request_review,
            "pull_request_review_comment": self.handle_pull_request_review_comment,
        }
        handler = handlers.get(event_type)
        if handler:
            await handler(data, repo_full_name)

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

        forum_id = await self.cog.config.issues_forum_id()
        forum = self.cog.bot.get_channel(forum_id)
        tags = await get_issue_tags(forum, issue)
        thread, _ = await get_or_create_thread(
            self.cog.bot,
            forum_id,
            repo_full_name,
            number,
            title,
            url,
            tags,
            self.cog.thread_cache,
        )
        if not thread:
            return

        role_mention = await get_role_mention(
            thread.guild, await self.cog.config.contributor_role_id()
        )

        if action == "opened":
            await send_message(
                thread,
                format_message("🆕", "Issue created", title, url, author, role_mention),
            )
        elif action == "closed":
            await update_status_tag(thread, "Closed")
            await send_message(
                thread,
                format_message("❌", "Issue closed", title, url, author, role_mention),
            )
        elif action == "reopened":
            await update_status_tag(thread, "Open")
            await send_message(
                thread,
                format_message("🔄", "Issue reopened", title, url, author, role_mention),
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

    # (rest of your handlers remain unchanged)

    async def handle_pull_request(self, data, repo_full_name):
        pr = data["pull_request"]
        number, title, url, author, action = (
            pr["number"],
            pr["title"],
            pr["html_url"],
            pr["user"]["login"],
            data["action"],
        )

        forum_id = await self.cog.config.prs_forum_id()
        forum = self.cog.bot.get_channel(forum_id)
        tags = await get_pr_tags(forum, pr)
        thread, _ = await get_or_create_thread(
            self.cog.bot, forum_id, repo_full_name, number, title, url, tags, self.cog.thread_cache
        )
        if not thread:
            return

        role_mention = await get_role_mention(thread.guild, await self.cog.config.contributor_role_id())

        if action == "opened":
            await send_message(thread, format_message("🆕", "PR created", title, url, author, role_mention))
        elif action == "closed":
            if pr.get("merged") or pr.get("merged_at"):
                await update_status_tag(thread, "Merged")
                await send_message(thread, format_message("✅", "PR merged", title, url, author, role_mention))
            else:
                await update_status_tag(thread, "Closed")
                await send_message(thread, format_message("❌", "PR closed", title, url, author, role_mention))
        elif action == "reopened":
            await update_status_tag(thread, "Open")
            await send_message(thread, format_message("🔄", "PR reopened", title, url, author, role_mention))
        elif action in ("assigned", "unassigned"):
            assignee = pr.get("assignee")
            assignee_text = f"[{assignee['login']}]({assignee['html_url']})" if assignee else "Unknown"
            await send_message(thread, f"👤 **PR {action}:** {assignee_text}\n🔧 Updated by: **{author}**")

    async def handle_issue_comment(self, data, repo_full_name):
        issue = data["issue"]
        number, body, author, url = (
            issue["number"],
            data["comment"]["body"],
            data["comment"]["user"]["login"],
            data["comment"]["html_url"],
        )
        is_pr = "pull_request" in issue
        forum_id = await (self.cog.config.prs_forum_id() if is_pr else self.cog.config.issues_forum_id())
        forum = self.cog.bot.get_channel(forum_id)
        tags = await (get_pr_tags(forum, issue) if is_pr else get_issue_tags(forum, issue))
        thread, _ = await get_or_create_thread(
            self.cog.bot, forum_id, repo_full_name, number, issue["title"], issue["html_url"], tags, self.cog.thread_cache
        )
        if not thread or not body:
            return

        role_mention = await get_role_mention(thread.guild, await self.cog.config.contributor_role_id())
        prefix = f"💬 **New {'PR' if is_pr else 'Issue'} comment** by **{author}** {role_mention} → [View Comment]({url})\n"
        await send_message(thread, body, prefix=prefix)

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

            role_mention = await get_role_mention(thread.guild, await self.cog.config.contributor_role_id())

            if entry["body"]:
                prefix = f"📝 **Review submitted** by **{entry['author']}** {role_mention} → [View Review]({entry['url']})\n"
                await send_message(thread, entry["body"], prefix=prefix)

            for body, url in reversed(entry["comments"]):
                prefix = f"💬 **PR review comment** by **{entry['author']}** {role_mention} → [View Comment]({url})\n"
                await send_message(thread, body, prefix=prefix)

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

        # Always compute desired tags
        tags = await (get_pr_tags(forum, item) if is_pr else get_issue_tags(forum, item))
        repo_tag = await get_or_create_tag(forum, repo.split("/")[-1])
        if repo_tag and repo_tag not in tags:
            tags.append(repo_tag)

        # Ensure thread exists (create if missing)
        thread, created = await get_or_create_thread(
            self.cog.bot, forum_id, repo, number, title, url, tags, self.cog.thread_cache
        )
        if not thread:
            return

        if created:
            # Newly created → send initial message
            role_mention = await get_role_mention(
                thread.guild, await self.cog.config.contributor_role_id()
            )
            emoji = "🆕"
            action = "PR created" if is_pr else "Issue created"
            msg = format_message(emoji, action, title, url, author, role_mention)
            await send_message(thread, msg)

        # Always reconcile tags (update if changed)
        current = set(t.name.lower() for t in (thread.applied_tags or []))
        desired = set(t.name.lower() for t in (tags or []))
        if current != desired:
            await thread.edit(applied_tags=tags or [])

        if ctx and idx % 50 == 0:
            await ctx.send(f"Processed {idx} items for {repo_name} so far...")

    async def reconcile_forum_tags(self, ctx=None, repo_filter: str = None):
        allowed_repos = await self.cog.config.allowed_repos()
        print(f"🔍 Starting reconcile. Allowed repos: {allowed_repos}")
        # Get token from environment variable, fallback to config
        token = os.environ.get("GENHUB_GITHUB_TOKEN") or await self.cog.config.github_token()
        print(f"🔑 Token source: {'ENV' if os.environ.get('GENHUB_GITHUB_TOKEN') else 'CONFIG'}")
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
            print("✅ Token set in headers")
        else:
            print("❌ No token available")

        async with aiohttp.ClientSession(headers=headers) as session:
            processed_repos = set()
            for repo in allowed_repos:
                if repo_filter and repo != repo_filter:
                    continue
                # Normalize repo name
                repo = repo.strip().lstrip("/")
                if repo in processed_repos:
                    print(f"⏭️ Skipping already processed repo: {repo}")
                    continue
                processed_repos.add(repo)
                repo_name = repo.split("/")[-1]
                print(f"🔄 Processing repo: {repo}")
                if ctx:
                    await ctx.send(f"🔄 Reconciling repo: {repo}")

                # Check if repository exists first
                repo_check_url = f"https://api.github.com/repos/{repo}"
                print(f"🔍 Checking if repository {repo} exists...")
                try:
                    async with session.get(repo_check_url) as resp:
                        if resp.status == 404:
                            print(f"❌ Repository '{repo}' does not exist")
                            if ctx:
                                await ctx.send(f"❌ Repository '{repo}' does not exist. Please check the repository name.")
                            continue  # Skip to next repo
                        elif resp.status == 403:
                            print(f"🚫 Cannot access repository '{repo}' (private or no permission)")
                            if ctx:
                                await ctx.send(f"🚫 Cannot access '{repo}'. Repository may be private or token lacks permission.")
                            continue  # Skip to next repo
                        elif resp.status != 200:
                            print(f"⚠️ Unexpected response {resp.status} when checking repository {repo}")
                            if ctx:
                                await ctx.send(f"⚠️ Cannot verify repository '{repo}' (status: {resp.status})")
                            continue  # Skip to next repo
                        else:
                            print(f"✅ Repository {repo} exists and is accessible")
                except Exception as e:
                    print(f"❌ Error checking repository {repo}: {e}")
                    if ctx:
                        await ctx.send(f"❌ Error checking repository '{repo}': {e}")
                    continue  # Skip to next repo

                # Fetch issues
                issues_forum_id = await self.cog.config.issues_forum_id()
                print(f"📋 Issues forum ID: {issues_forum_id}")
                forum = self.cog.bot.get_channel(issues_forum_id)
                issues_failed = False
                if forum:
                    print(f"✅ Issues forum found: {forum.name} ({forum.id})")
                    page = 1
                    max_pages = 50
                    total_issues = 0
                    while page <= max_pages:
                        url = f"https://api.github.com/repos/{repo}/issues?state=all&per_page=100&page={page}"
                        print(f"🌐 Fetching issues page {page} for {repo}")
                        try:
                            async with session.get(url) as resp:
                                print(f"📡 Issues API response: {resp.status}")
                                if resp.status == 404:
                                    print(f"❌ Repository '{repo}' not found (404)")
                                    print(f"ℹ️  Please verify the repository name and ensure it exists")
                                    if ctx:
                                        await ctx.send(f"❌ Repository '{repo}' not found. Please check the repository name.")
                                    break
                                elif resp.status == 403:
                                    print(f"🚫 Access forbidden to '{repo}' (403)")
                                    print(f"ℹ️  Token may not have permission or repository may be private")
                                    if ctx:
                                        await ctx.send(f"🚫 Cannot access '{repo}'. Check token permissions.")
                                    break
                                elif resp.status != 200:
                                    print(f"⚠️ Unexpected response {resp.status} for {repo}")
                                    if ctx:
                                        await ctx.send(f"⚠️ Failed to fetch issues for '{repo}' (status: {resp.status})")
                                    break
                                    if ctx:
                                        if resp.status == 404:
                                            await ctx.send(
                                                f"❌ Failed to fetch issues for {repo}, status: 404 (repo not found). Removing from allowed repos."
                                            )
                                            async with self.cog.config.allowed_repos() as repos:
                                                if repo in repos:
                                                    repos.remove(repo)
                                            issues_failed = True
                                        elif resp.status == 403:
                                            await ctx.send(
                                                f"⚠️ Failed to fetch issues for {repo}, status: 403 (forbidden). Check token or permissions."
                                            )
                                            issues_failed = True
                                        else:
                                            await ctx.send(
                                                f"⚠️ Failed to fetch issues for {repo}, status: {resp.status}"
                                            )
                                            issues_failed = True
                                    break
                                data = await resp.json()
                                print(f"📦 Issues data received: {len(data)} items")
                                if len(data) == 0:
                                    print(f"ℹ️  No issues found for {repo}. This could mean:")
                                    print(f"   - Repository has no issues")
                                    print(f"   - Repository doesn't exist")
                                    print(f"   - Token lacks permission to view issues")
                                    print(f"   - Repository is private and token has no access")
                        except Exception as e:
                            # Swallow exceptions so reconcile continues/returns gracefully
                            print(
                                f"❌ Exception fetching issues for {repo}: {e}"
                            )
                            if ctx:
                                try:
                                    await ctx.send(
                                        f"⚠️ Failed to fetch issues for {repo}: {e}"
                                    )
                                except Exception:
                                    pass
                            issues_failed = True
                            break
                        if not data:
                            break
                        for item in data:
                            if item.get("pull_request"):
                                print(f"⏭️ Skipping PR in issues: {item['number']}")
                                continue  # skip PRs
                            total_issues += 1
                            print(f"📝 Processing issue {item['number']}: {item['title'][:50]}...")
                            try:
                                await self._reconcile_item(session, forum, repo, item, False, ctx, total_issues, repo_name)
                            except Exception as e:
                                print(f"❌ Error reconciling issue {item.get('number')}: {e}")
                        page += 1
                        await asyncio.sleep(1)  # rate limit
                    if not issues_failed and ctx:
                        await ctx.send(f"✅ Processed {total_issues} issues for {repo}")
                    print(f"✅ Issues processing complete for {repo}: {total_issues} processed")
                else:
                    if ctx:
                        await ctx.send(f"⚠️ Issues forum not configured (issues_forum_id: {issues_forum_id}), skipping issues for {repo}")
                    issues_failed = True

                # Fetch PRs
                prs_forum_id = await self.cog.config.prs_forum_id()
                print(f"📋 PRs forum ID: {prs_forum_id}")
                forum = self.cog.bot.get_channel(prs_forum_id)
                prs_failed = False
                if forum:
                    print(f"✅ PRs forum found: {forum.name} ({forum.id})")
                    page = 1
                    max_pages = 50 
                    total_prs = 0
                    while page <= max_pages:
                        url = f"https://api.github.com/repos/{repo}/pulls?state=all&per_page=100&page={page}"
                        print(f"🌐 Fetching PRs page {page} for {repo}")
                        try:
                            async with session.get(url) as resp:
                                print(f"📡 PRs API response: {resp.status}")
                                if resp.status == 404:
                                    print(f"❌ Repository '{repo}' not found (404)")
                                    print(f"ℹ️  Please verify the repository name and ensure it exists")
                                    if ctx:
                                        await ctx.send(f"❌ Repository '{repo}' not found. Please check the repository name.")
                                    break
                                elif resp.status == 403:
                                    print(f"🚫 Access forbidden to '{repo}' (403)")
                                    print(f"ℹ️  Token may not have permission or repository may be private")
                                    if ctx:
                                        await ctx.send(f"🚫 Cannot access '{repo}'. Check token permissions.")
                                    break
                                elif resp.status != 200:
                                    print(f"⚠️ Unexpected response {resp.status} for {repo}")
                                    if ctx:
                                        await ctx.send(f"⚠️ Failed to fetch PRs for '{repo}' (status: {resp.status})")
                                    break
                                    if ctx:
                                        if resp.status == 404:
                                            await ctx.send(
                                                f"❌ Failed to fetch PRs for {repo}, status: 404 (repo not found). Removing from allowed repos."
                                            )
                                            async with self.cog.config.allowed_repos() as repos:
                                                if repo in repos:
                                                    repos.remove(repo)
                                            prs_failed = True
                                        elif resp.status == 403:
                                            await ctx.send(
                                                f"⚠️ Failed to fetch PRs for {repo}, status: 403 (forbidden). Check token or permissions."
                                            )
                                            prs_failed = True
                                        else:
                                            await ctx.send(
                                                f"⚠️ Failed to fetch PRs for {repo}, status: {resp.status}"
                                            )
                                            prs_failed = True
                                    break
                                data = await resp.json()
                                print(f"📦 PRs data received: {len(data)} items")
                                if len(data) == 0:
                                    print(f"ℹ️  No PRs found for {repo}. This could mean:")
                                    print(f"   - Repository has no pull requests")
                                    print(f"   - Repository doesn't exist")
                                    print(f"   - Token lacks permission to view PRs")
                                    print(f"   - Repository is private and token has no access")
                        except Exception as e:
                            print(
                                f"⚠️ Failed to fetch PRs for {repo}: {e}"
                            )
                            if ctx:
                                try:
                                    await ctx.send(
                                        f"⚠️ Failed to fetch PRs for {repo}: {e}"
                                    )
                                except Exception:
                                    pass
                            prs_failed = True
                            break
                        if not data:
                            break
                        for item in data:
                            # In PRs endpoint, all items are PRs by definition, no filtering needed
                            total_prs += 1
                            print(f"🔄 Processing PR {item['number']}: {item['title'][:50]}...")
                            try:
                                await self._reconcile_item(session, forum, repo, item, True, ctx, total_prs, repo_name)
                            except Exception as e:
                                print(f"❌ Error reconciling PR {item.get('number')}: {e}")
                        page += 1
                        await asyncio.sleep(1)
                    if not prs_failed and ctx:
                        await ctx.send(f"✅ Processed {total_prs} PRs for {repo}")
                    print(f"✅ PRs processing complete for {repo}: {total_prs} processed")
                else:
                    if ctx:
                        await ctx.send(f"⚠️ PRs forum not configured (prs_forum_id: {prs_forum_id}), skipping PRs for {repo}")
                    prs_failed = True

        print("🎉 Reconciliation process finished!")
