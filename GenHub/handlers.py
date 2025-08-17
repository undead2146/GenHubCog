import discord
import asyncio
import aiohttp
import re
from .utils import send_message

# Regex to extract GitHub issue/PR link from thread content
GITHUB_ISSUE_RE = re.compile(r"https://github\.com/([^/]+)/([^/]+)/(issues|pull)/(\d+)")


class GitHubEventHandlers:
    def __init__(self, cog):
        self.cog = cog
        self.pending_reviews = {}

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

    async def log_error(self, message):
        log_channel_id = await self.cog.config.log_channel_id()
        if log_channel_id:
            log_channel = self.cog.bot.get_channel(log_channel_id)
            if log_channel:
                await send_message(log_channel, message)

    # ---------------------------
    # Thread Management
    # ---------------------------

    async def get_or_create_thread(self, forum_id, repo_full_name, number, title, url, tags):
        key = (forum_id, repo_full_name, number)
        thread = await self.find_thread(forum_id, repo_full_name, number)
        if thread:
            return thread

        forum = self.cog.bot.get_channel(forum_id)
        if not forum:
            return None

        # Ensure repo tag exists
        repo_tag = await self._get_or_create_tag(forum, repo_full_name.split("/")[-1])
        if repo_tag and repo_tag not in tags:
            tags.append(repo_tag)

        thread_with_msg = await forum.create_thread(
            name=f"「#{number}」{title}",
            content=f"[#{number}]({url})",
            applied_tags=tags,
        )
        thread = thread_with_msg.thread
        self.cog.thread_cache[key] = thread.id
        return thread

    async def find_thread(self, forum_id, repo_full_name, topic_number):
        key = (forum_id, repo_full_name, topic_number)
        if key in self.cog.thread_cache:
            thread_id = self.cog.thread_cache[key]
            thread = self.cog.bot.get_channel(thread_id)
            if thread:
                return thread

        forum = self.cog.bot.get_channel(forum_id)
        if not forum:
            return None

        repo_tag = await self._get_or_create_tag(forum, repo_full_name.split("/")[-1])

        for thread in forum.threads:
            if f"「#{topic_number}」" in thread.name and repo_tag in thread.applied_tags:
                self.cog.thread_cache[key] = thread.id
                return thread

        async for thread in forum.archived_threads(limit=None):
            if f"「#{topic_number}」" in thread.name and repo_tag in thread.applied_tags:
                self.cog.thread_cache[key] = thread.id
                return thread

        return None

    # ---------------------------
    # Tag Helpers
    # ---------------------------

    async def _get_or_create_tag(self, forum, name):
        """Find or create a tag by name (case-insensitive)."""
        for tag in forum.available_tags:
            if tag.name.lower() == name.lower():
                return tag
        try:
            tag = await forum.create_tag(name=name, moderated=False)
            print(f"✅ Created tag '{name}' in forum {forum.name}")
            return tag
        except discord.Forbidden:
            print(f"❌ Missing Manage Channels permission to create tag '{name}' in {forum.name}")
            return None
        except Exception as e:
            print(f"⚠️ Failed to create tag '{name}' in {forum.name}: {e}")
            return None

    async def _get_issue_tags(self, forum, issue):
        tags = []
        if issue["state"] == "open":
            tag = await self._get_or_create_tag(forum, "Open")
        else:
            tag = await self._get_or_create_tag(forum, "Closed")
        if tag:
            tags.append(tag)

        if issue.get("assignees"):
            active_tag = await self._get_or_create_tag(forum, "Active")
            if active_tag:
                tags.append(active_tag)

        return tags

    async def _get_pr_tags(self, forum, pr):
        tags = []
        if pr.get("state") == "open":
            tag = await self._get_or_create_tag(forum, "Open")
        elif pr.get("merged") or pr.get("merged_at") or (
            "pull_request" in pr and pr["pull_request"].get("merged_at")
        ):
            tag = await self._get_or_create_tag(forum, "Merged")
        else:
            tag = await self._get_or_create_tag(forum, "Closed")

        if tag:
            tags.append(tag)
        return tags

    async def _update_status_tag(self, thread, new_status_name):
        """Replace status tag while preserving repo tag."""
        forum = thread.parent
        new_status_tag = await self._get_or_create_tag(forum, new_status_name)
        if not new_status_tag:
            return

        # Keep repo tag(s), remove old status tags
        current_tags = list(thread.applied_tags)
        status_names = {"open", "closed", "merged", "active"}
        current_tags = [t for t in current_tags if t.name.lower() not in status_names]

        # Add new status tag
        current_tags.append(new_status_tag)

        await thread.edit(applied_tags=current_tags)

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
        tags = await self._get_issue_tags(forum, issue)
        thread = await self.get_or_create_thread(forum_id, repo_full_name, number, title, url, tags)
        if not thread:
            return

        contributor_role_id = await self.cog.config.contributor_role_id()
        role_mention = f"<@&{contributor_role_id}>" if contributor_role_id else ""

        if action == "closed":
            await self._update_status_tag(thread, "Closed")
            await send_message(thread, f"❌ Issue closed: **{title}** by {author} {role_mention}")
        elif action == "reopened":
            await self._update_status_tag(thread, "Open")
            await send_message(thread, f"🔄 Issue reopened: **{title}** by {author} {role_mention}")
        elif action in ("assigned", "unassigned"):
            active_tag = await self._get_or_create_tag(thread.parent, "Active")
            tags = list(thread.applied_tags)
            if action == "assigned" and active_tag and active_tag not in tags:
                tags.append(active_tag)
            elif action == "unassigned" and active_tag in tags:
                tags.remove(active_tag)
            await thread.edit(applied_tags=tags)
            await send_message(thread, f"👤 Issue assignment updated by {author} ({action}).")

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
        tags = await self._get_pr_tags(forum, pr)
        thread = await self.get_or_create_thread(forum_id, repo_full_name, number, title, url, tags)
        if not thread:
            return

        contributor_role_id = await self.cog.config.contributor_role_id()
        role_mention = f"<@&{contributor_role_id}>" if contributor_role_id else ""

        if action == "closed":
            if pr.get("merged") or pr.get("merged_at"):
                await self._update_status_tag(thread, "Merged")
                await send_message(thread, f"✅ PR merged: **{title}** by {author} {role_mention}")
            else:
                await self._update_status_tag(thread, "Closed")
                await send_message(thread, f"❌ PR closed: **{title}** by {author} {role_mention}")
        elif action == "reopened":
            await self._update_status_tag(thread, "Open")
            await send_message(thread, f"🔄 PR reopened: **{title}** by {author} {role_mention}")

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

        tags = await (self._get_pr_tags(forum, issue) if is_pr else self._get_issue_tags(forum, issue))
        thread = await self.get_or_create_thread(forum_id, repo_full_name, number, issue["title"], issue["html_url"], tags)
        if thread and body:
            prefix = f"# **[ {'New PR comment' if is_pr else 'New issue comment'} from {author} ]({url})**\n"
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

            tags = await self._get_pr_tags(forum, pr_data)
            thread = await self.get_or_create_thread(
                forum_id, repo_full_name, pr_number, pr_data["title"], pr_data["html_url"], tags
            )
            if not thread:
                return

            if entry["body"]:
                prefix = f"# **[ Review from {entry['author']} ]({entry['url']})**\n"
                await send_message(thread, entry["body"], prefix=prefix)

            for body, url in reversed(entry["comments"]):
                prefix = f"# **[ New PR review comment from {entry['author']} ]({url})**\n"
                await send_message(thread, body, prefix=prefix)

        if key in self.pending_reviews and "task" in self.pending_reviews[key]:
            self.pending_reviews[key]["task"].cancel()
        self.pending_reviews[key]["task"] = asyncio.create_task(flush())

    # ---------------------------
    # Reconciliation
    # ---------------------------

    async def reconcile_forum_tags(self, ctx=None, repo_filter: str = None):
        """Go over all forum posts in Issues/PRs forums and fix their tags."""
        issues_forum_id = await self.cog.config.issues_forum_id()
        prs_forum_id = await self.cog.config.prs_forum_id()

        for forum_id, is_pr in [(issues_forum_id, False), (prs_forum_id, True)]:
            forum = self.cog.bot.get_channel(forum_id)
            if not forum:
                continue

            threads = list(forum.threads)
            async for t in forum.archived_threads(limit=None):
                threads.append(t)

            total = len(threads)
            if ctx:
                await ctx.send(f"🔄 Reconciling **{total}** threads in forum: {forum.name}")

            print(f"🔄 Reconciling {total} threads in forum: {forum.name}")

            async with aiohttp.ClientSession() as session:
                for idx, thread in enumerate(threads, start=1):
                    try:
                        # Get first message content
                        first_msg = None
                        async for msg in thread.history(limit=1, oldest_first=True):
                            first_msg = msg
                        if not first_msg:
                            continue

                        match = GITHUB_ISSUE_RE.search(first_msg.content)
                        if not match:
                            continue

                        owner, repo, kind, number = match.groups()
                        number = int(number)
                        repo_full_name = f"{owner}/{repo}"

                        if repo_filter and repo_filter.lower() != repo.lower():
                            continue

                        # Build correct API URL
                        if kind == "issues":
                            url = f"https://api.github.com/repos/{owner}/{repo}/issues/{number}"
                        else:  # pull
                            url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}"

                        # Auth headers
                        headers = {"Accept": "application/vnd.github+json"}
                        token = await self.cog.config.github_token()
                        if token:
                            headers["Authorization"] = f"Bearer {token}"

                        async with session.get(url, headers=headers) as resp:
                            if resp.status != 200:
                                print(f"⚠️ Failed to fetch {url}: {resp.status}")
                                continue
                            data = await resp.json()

                        # Determine correct tags
                        if kind == "issues":
                            tags = await self._get_issue_tags(forum, data)
                        else:
                            tags = await self._get_pr_tags(forum, data)

                        # Always add repo tag
                        repo_tag = await self._get_or_create_tag(forum, repo)
                        if repo_tag and repo_tag not in tags:
                            tags.append(repo_tag)

                        # Compare with current
                        current = set(t.name.lower() for t
