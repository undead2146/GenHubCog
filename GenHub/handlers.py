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

        # Prepare initial content for thread creation
        role_mention = get_role_mention(
            forum.guild if forum else None, await self.cog.config.contributor_role_id()
        )
        initial_content = None
        if action == "opened":
            initial_content = format_message("🆕", "Issue created", title, url, author, role_mention)

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
            # Initial content already sent during thread creation
            pass
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

        # Prepare initial content for thread creation
        role_mention = get_role_mention(
            forum.guild if forum else None, await self.cog.config.contributor_role_id()
        )
        initial_content = None
        if action == "opened":
            initial_content = format_message("🆕", "PR created", title, url, author, role_mention)

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

        role_mention = get_role_mention(thread.guild, await self.cog.config.contributor_role_id())
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

            role_mention = get_role_mention(thread.guild, await self.cog.config.contributor_role_id())

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
        role_mention = get_role_mention(
            forum.guild, await self.cog.config.contributor_role_id()
        )
        emoji = "🆕"
        action = "PR created" if is_pr else "Issue created"
        initial_content = format_message(emoji, action, title, url, author, role_mention)

        thread, created = await get_or_create_thread(
            self.cog.bot, forum_id, repo, number, title, url, tags, self.cog.thread_cache, initial_content
        )
        if not thread:
            print(f"❌ Failed to get or create thread for {repo}#{number}")
            return

        print(f"{'✅ Created' if created else '📝 Found existing'} thread for {repo}#{number}")

        if created:
            # Newly created → initial message already sent via initial_content
            pass
        else:
            # Existing thread - check if it needs the initial message
            # This handles cases where thread was deleted and recreated
            try:
                # Check if thread has any messages (might be empty if just recreated)
                history = []
                async for message in thread.history(limit=1, oldest_first=True):
                    history.append(message)
                    break

                if not history:
                    # Thread is empty, send initial message
                    await send_message(thread, initial_content)
                    print(f"📝 Sent initial message to existing empty thread #{number}")
            except Exception as e:
                print(f"⚠️ Could not check thread history for #{number}: {e}")

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
                repo_accessible = True
                try:
                    async with session.get(repo_check_url) as resp:
                        if resp.status == 404:
                            print(f"❌ Repository '{repo}' does not exist")
                            if ctx:
                                await ctx.send(f"❌ Repository '{repo}' does not exist. Please check the repository name.")
                            repo_accessible = False
                        elif resp.status == 403:
                            print(f"🚫 Cannot access repository '{repo}' (private or no permission)")
                            if ctx:
                                await ctx.send(f"🚫 Cannot access '{repo}'. This could be because:\n"
                                             f"• The repository is private and your token lacks access\n"
                                             f"• Your GitHub token doesn't have the required permissions\n"
                                             f"• The repository doesn't exist\n"
                                             f"• Check your token at: https://github.com/settings/tokens")
                            repo_accessible = False
                        elif resp.status == 401:
                            print(f"🚫 Authentication failed for '{repo}' (401)")
                            if ctx:
                                await ctx.send(f"🚫 GitHub authentication failed. Please check your token:\n"
                                             f"• Use `!genhub token <your_token>` to set a new token\n"
                                             f"• Or set the `GENHUB_GITHUB_TOKEN` environment variable\n"
                                             f"• Generate a token at: https://github.com/settings/tokens")
                            repo_accessible = False
                        elif resp.status != 200:
                            print(f"⚠️ Unexpected response {resp.status} when checking repository {repo}")
                            if ctx:
                                await ctx.send(f"⚠️ Cannot verify repository '{repo}' (status: {resp.status})")
                            repo_accessible = False
                        else:
                            print(f"✅ Repository {repo} exists and is accessible")
                except Exception as e:
                    print(f"❌ Error checking repository {repo}: {e}")
                    if ctx:
                        await ctx.send(f"❌ Error checking repository '{repo}': {e}")
                    repo_accessible = False

                if not repo_accessible:
                    continue  # Skip this repo entirely

                # Process issues
                await self._reconcile_repo_items(session, repo, repo_name, False, ctx)

                # Process PRs
                await self._reconcile_repo_items(session, repo, repo_name, True, ctx)

        print("🎉 Reconciliation process finished!")
        if ctx:
            await ctx.send("✅ Reconciliation complete.")

    async def _reconcile_repo_items(self, session, repo, repo_name, is_pr, ctx):
        """Reconcile issues or PRs for a repository with proper error handling and cleanup."""
        item_type = "PRs" if is_pr else "issues"
        endpoint = "pulls" if is_pr else "issues"
        forum_id = await (self.cog.config.prs_forum_id() if is_pr else self.cog.config.issues_forum_id())

        print(f"📋 {item_type} forum ID: {forum_id}")
        forum = self.cog.bot.get_channel(forum_id)

        if not forum:
            print(f"⚠️ {item_type} forum not configured (forum_id: {forum_id})")
            if ctx:
                await ctx.send(f"⚠️ {item_type} forum not configured, skipping {item_type.lower()} for {repo}")
            return

        print(f"✅ {item_type} forum found: {forum.name} ({forum.id})")

        # Collect all GitHub items
        github_items = {}
        page = 1
        max_pages = 50
        total_items = 0

        while page <= max_pages:
            url = f"https://api.github.com/repos/{repo}/{endpoint}?state=all&per_page=100&page={page}"
            print(f"🌐 Fetching {item_type.lower()} page {page} for {repo}")

            try:
                async with session.get(url) as resp:
                    print(f"📡 {item_type} API response: {resp.status}")

                    if resp.status == 404:
                        print(f"❌ Repository '{repo}' not found (404)")
                        if ctx:
                            await ctx.send(f"❌ Repository '{repo}' not found. Please check the repository name.")
                        return
                    elif resp.status == 403:
                        print(f"🚫 Access forbidden to '{repo}' (403)")
                        if ctx:
                            await ctx.send(f"🚫 Cannot access '{repo}'. This could be because:\n"
                                         f"• The repository is private and your token lacks access\n"
                                         f"• Your GitHub token doesn't have the required permissions\n"
                                         f"• The repository doesn't exist\n"
                                         f"• Check your token at: https://github.com/settings/tokens")
                        return
                    elif resp.status == 401:
                        print(f"🚫 Authentication failed for '{repo}' (401)")
                        if ctx:
                            await ctx.send(f"🚫 GitHub authentication failed. Please check your token:\n"
                                         f"• Use `!genhub token <your_token>` to set a new token\n"
                                         f"• Or set the `GENHUB_GITHUB_TOKEN` environment variable\n"
                                         f"• Generate a token at: https://github.com/settings/tokens")
                        return
                    elif resp.status != 200:
                        print(f"⚠️ Unexpected response {resp.status} for {repo}")
                        if ctx:
                            await ctx.send(f"⚠️ Failed to fetch {item_type.lower()} for '{repo}' (status: {resp.status})")
                        return

                    data = await resp.json()
                    print(f"📦 {item_type} data received: {len(data)} items")

                    if len(data) == 0:
                        break

                    for item in data:
                        # Filter out PRs from issues endpoint
                        if not is_pr and item.get("pull_request"):
                            print(f"⏭️ Skipping PR in issues: {item['number']}")
                            continue

                        number = item["number"]
                        github_items[number] = item
                        total_items += 1

                        print(f"📝 Processing {item_type.lower()[:-1]} {number}: {item['title'][:50]}...")
                        try:
                            await self._reconcile_item(session, forum, repo, item, is_pr, ctx, total_items, repo_name)
                        except Exception as e:
                            print(f"❌ Error reconciling {item_type.lower()[:-1]} {number}: {e}")

            except Exception as e:
                print(f"❌ Exception fetching {item_type.lower()} for {repo}: {e}")
                if ctx:
                    await ctx.send(f"⚠️ Failed to fetch {item_type.lower()} for {repo}: {e}")
                return

            page += 1
            await asyncio.sleep(1)  # rate limit

        print(f"✅ {item_type} processing complete for {repo}: {total_items} processed")
        if ctx:
            await ctx.send(f"✅ Processed {total_items} {item_type.lower()} for {repo}")

        # Clean up orphaned threads (threads that exist but shouldn't)
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
