import discord
import asyncio
import aiohttp
import re
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
        thread = await get_or_create_thread(
            self.cog.bot, forum_id, repo_full_name, number, title, url, tags, self.cog.thread_cache
        )
        if not thread:
            return

        role_mention = await get_role_mention(thread.guild, await self.cog.config.contributor_role_id())

        if action == "opened":
            msg = format_message("🆕", "Issue created", title, url, author, role_mention)
            await send_message(thread, msg, prefix="Issue created")
        elif action == "closed":
            await update_status_tag(thread, "Closed")
            msg = format_message("❌", "Issue closed", title, url, author, role_mention)
            await send_message(thread, msg, prefix="Issue closed")
        elif action == "reopened":
            await update_status_tag(thread, "Open")
            msg = format_message("🔄", "Issue reopened", title, url, author, role_mention)
            await send_message(thread, msg, prefix="Issue reopened")
        elif action in ("assigned", "unassigned"):
            assignee = issue.get("assignee")
            assignee_text = f"[{assignee['login']}]({assignee['html_url']})" if assignee else "Unknown"
            await send_message(thread, f"👤 **Issue {action}:** {assignee_text}\n🔧 Updated by: **{author}**", prefix=f"Issue {action}")

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
        thread = await get_or_create_thread(
            self.cog.bot, forum_id, repo_full_name, number, title, url, tags, self.cog.thread_cache
        )
        if not thread:
            return

        role_mention = await get_role_mention(thread.guild, await self.cog.config.contributor_role_id())

        if action == "opened":
            msg = format_message("🆕", "PR created", title, url, author, role_mention)
            await send_message(thread, msg, prefix="PR created")
        elif action == "closed":
            if pr.get("merged") or pr.get("merged_at"):
                await update_status_tag(thread, "Merged")
                msg = format_message("✅", "PR merged", title, url, author, role_mention)
                await send_message(thread, msg, prefix="PR merged")
            else:
                await update_status_tag(thread, "Closed")
                msg = format_message("❌", "PR closed", title, url, author, role_mention)
                await send_message(thread, msg, prefix="PR closed")
        elif action == "reopened":
            await update_status_tag(thread, "Open")
            msg = format_message("🔄", "PR reopened", title, url, author, role_mention)
            await send_message(thread, msg, prefix="PR reopened")
        elif action in ("assigned", "unassigned"):
            assignee = pr.get("assignee")
            assignee_text = f"[{assignee['login']}]({assignee['html_url']})" if assignee else "Unknown"
            await send_message(thread, f"👤 **PR {action}:** {assignee_text}\n🔧 Updated by: **{author}**", prefix=f"PR {action}")

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
        thread = await get_or_create_thread(
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
            thread = await get_or_create_thread(
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

    async def reconcile_forum_tags(self, ctx=None, repo_filter: str = None):
        issues_forum_id = await self.cog.config.issues_forum_id()
        prs_forum_id = await self.cog.config.prs_forum_id()
        for forum_id, is_pr in [(issues_forum_id, False), (prs_forum_id, True)]:
            forum = self.cog.bot.get_channel(forum_id)
            if not forum:
                continue
            threads = list(forum.threads)
            # archived_threads may not be an async iterable in tests/mocks.
            try:
                archived = forum.archived_threads(limit=None)
                if hasattr(archived, "__aiter__"):
                    async for t in archived:
                        threads.append(t)
                else:
                    # It might be an awaitable returning an iterable
                    try:
                        result = await archived
                        for t in result:
                            threads.append(t)
                    except Exception:
                        pass
            except TypeError:
                # archived_threads() raised because it's not callable/iterable in mocks
                pass
            total = len(threads)
            if ctx:
                await ctx.send(f"🔄 Reconciling **{total}** threads in forum: {forum.name}")
            async with aiohttp.ClientSession() as session:
                for idx, thread in enumerate(threads, start=1):
                    try:
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
                        if repo_filter and repo_filter.lower() != repo.lower():
                            continue
                        if kind == "issues":
                            url = f"https://api.github.com/repos/{owner}/{repo}/issues/{number}"
                        else:
                            url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}"
                        headers = {"Accept": "application/vnd.github+json"}
                        token = await self.cog.config.github_token()
                        if token:
                            headers["Authorization"] = f"Bearer {token}"
                        async with session.get(url, headers=headers) as resp:
                            if resp.status != 200:
                                continue
                            data = await resp.json()
                        tags = await (get_issue_tags(forum, data) if kind == "issues" else get_pr_tags(forum, data))
                        repo_tag = await get_or_create_tag(forum, repo)
                        if repo_tag and repo_tag not in tags:
                            tags.append(repo_tag)
                        current = set(t.name.lower() for t in thread.applied_tags)
                        desired = set(t.name.lower() for t in tags)
                        if current != desired:
                            await thread.edit(applied_tags=tags)
                        if ctx and idx % 10 == 0:
                            await ctx.send(f"[{idx}/{total}] Processed {thread.name}")
                        await asyncio.sleep(1)
                    except Exception as e:
                        print(f"❌ Error reconciling {thread.name}: {e}")
