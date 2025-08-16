import discord
import asyncio
from .utils import send_message, resolve_tag


class GitHubEventHandlers:
    def __init__(self, cog):
        self.cog = cog
        # Store pending reviews temporarily to group body + comments
        self.pending_reviews = {}

    async def process_payload(self, request, data):
        repo_full_name = data.get("repository", {}).get("full_name")
        allowed_repos = await self.cog.config.allowed_repos()
        if repo_full_name not in allowed_repos:
            return

        event_type = request.headers.get("X-GitHub-Event")
        if event_type == "issues":
            await self.handle_issue(data)
        elif event_type == "pull_request":
            await self.handle_pull_request(data)
        elif event_type == "issue_comment":
            await self.handle_issue_comment(data)
        elif event_type == "pull_request_review":
            await self.handle_pull_request_review(data)
        elif event_type == "pull_request_review_comment":
            await self.handle_pull_request_review_comment(data)

    async def log_error(self, message):
        log_channel_id = await self.cog.config.log_channel_id()
        if log_channel_id:
            log_channel = self.cog.bot.get_channel(log_channel_id)
            if log_channel:
                await send_message(log_channel, message)

    # ---------------------------
    # GitHub Event Handlers
    # ---------------------------

    async def handle_issue(self, data):
        issue_number = data["issue"]["number"]
        issue_title = data["issue"]["title"]
        issue_url = data["issue"]["html_url"]
        issue_author = data["issue"]["user"]["login"]
        action = data["action"]

        contributor_role_id = await self.cog.config.contributor_role_id()
        role_mention = f"<@&{contributor_role_id}>" if contributor_role_id else ""

        forum_id = await self.cog.config.issues_forum_id()
        forum = self.cog.bot.get_channel(forum_id)

        if action == "opened" and forum:
            open_tag_id = await self.cog.config.issues_open_tag_id()
            tag = resolve_tag(forum, open_tag_id)
            thread_with_msg = await forum.create_thread(
                name=f"「#{issue_number}」{issue_title}",
                content=f"[#{issue_number}]({issue_url})",
                applied_tags=[tag] if tag else [],
            )
            thread = thread_with_msg.thread
            self.cog.thread_cache[issue_number] = thread.id

        thread = await self.find_thread(forum_id, issue_number)
        if not thread and forum:
            open_tag_id = await self.cog.config.issues_open_tag_id()
            tag = resolve_tag(forum, open_tag_id)
            thread_with_msg = await forum.create_thread(
                name=f"「#{issue_number}」{issue_title}",
                content=f"[#{issue_number}]({issue_url})",
                applied_tags=[tag] if tag else [],
            )
            thread = thread_with_msg.thread
            self.cog.thread_cache[issue_number] = thread.id

        if action == "closed" and thread:
            closed_tag_id = await self.cog.config.issues_closed_tag_id()
            tag = resolve_tag(thread.parent, closed_tag_id)
            await thread.edit(applied_tags=[tag] if tag else [])
            await send_message(
                thread,
                f"❌ Issue closed: **{issue_title}** Closed By: {issue_author} {role_mention}",
            )
        elif action == "reopened" and thread:
            open_tag_id = await self.cog.config.issues_open_tag_id()
            tag = resolve_tag(thread.parent, open_tag_id)
            await thread.edit(applied_tags=[tag] if tag else [])
            await send_message(
                thread,
                f"🔄 Issue reopened: **{issue_title}** Reopened By: {issue_author} {role_mention}",
            )

    async def handle_pull_request(self, data):
        pr_number = data["pull_request"]["number"]
        pr_title = data["pull_request"]["title"]
        pr_url = data["pull_request"]["html_url"]
        pr_author = data["pull_request"]["user"]["login"]
        action = data["action"]

        contributor_role_id = await self.cog.config.contributor_role_id()
        role_mention = f"<@&{contributor_role_id}>" if contributor_role_id else ""

        forum_id = await self.cog.config.prs_forum_id()
        forum = self.cog.bot.get_channel(forum_id)

        if action == "opened" and forum:
            open_tag_id = await self.cog.config.prs_open_tag_id()
            tag = resolve_tag(forum, open_tag_id)
            thread_with_msg = await forum.create_thread(
                name=f"「#{pr_number}」{pr_title}",
                content=f"[#{pr_number}]({pr_url})",
                applied_tags=[tag] if tag else [],
            )
            thread = thread_with_msg.thread
            self.cog.thread_cache[pr_number] = thread.id

        thread = await self.find_thread(forum_id, pr_number)
        if not thread and forum:
            open_tag_id = await self.cog.config.prs_open_tag_id()
            tag = resolve_tag(forum, open_tag_id)
            thread_with_msg = await forum.create_thread(
                name=f"「#{pr_number}」{pr_title}",
                content=f"[#{pr_number}]({pr_url})",
                applied_tags=[tag] if tag else [],
            )
            thread = thread_with_msg.thread
            self.cog.thread_cache[pr_number] = thread.id

        if action == "closed" and thread:
            if data["pull_request"].get("merged"):
                merged_tag_id = await self.cog.config.prs_merged_tag_id()
                tag = resolve_tag(thread.parent, merged_tag_id)
                await thread.edit(applied_tags=[tag] if tag else [])
                await send_message(
                    thread,
                    f"✅ PR merged: **{pr_title}** Merged By: {pr_author} {role_mention}",
                )
            else:
                closed_tag_id = await self.cog.config.prs_closed_tag_id()
                tag = resolve_tag(thread.parent, closed_tag_id)
                await thread.edit(applied_tags=[tag] if tag else [])
                await send_message(
                    thread,
                    f"❌ PR closed: **{pr_title}** Closed By: {pr_author} {role_mention}",
                )
        elif action == "reopened" and thread:
            open_tag_id = await self.cog.config.prs_open_tag_id()
            tag = resolve_tag(thread.parent, open_tag_id)
            await thread.edit(applied_tags=[tag] if tag else [])
            await send_message(
                thread,
                f"🔄 PR reopened: **{pr_title}** Reopened By: {pr_author} {role_mention}",
            )

    # ---------------------------
    # Review Batching
    # ---------------------------

    async def handle_pull_request_review(self, data):
        if data.get("action") != "submitted":
            return

        pr_number = data["pull_request"]["number"]
        review_id = data["review"]["id"]
        review_body = data["review"]["body"]
        review_author = data["review"]["user"]["login"]
        review_url = data["review"]["html_url"]

        key = (pr_number, review_id)
        entry = self.pending_reviews.setdefault(
            key,
            {"author": review_author, "url": review_url, "body": None, "comments": []},
        )
        entry["body"] = review_body

        await self._schedule_flush(pr_number, review_id, data)

    async def handle_pull_request_review_comment(self, data):
        pr_number = data["pull_request"]["number"]
        review_id = data["comment"]["pull_request_review_id"]
        comment_body = data["comment"]["body"]
        comment_author = data["comment"]["user"]["login"]
        comment_url = data["comment"]["html_url"]

        key = (pr_number, review_id)
        entry = self.pending_reviews.setdefault(
            key,
            {"author": comment_author, "url": comment_url, "body": None, "comments": []},
        )
        entry["comments"].append((comment_body, comment_url))

        await self._schedule_flush(pr_number, review_id, data)

    async def _schedule_flush(self, pr_number, review_id, data):
        key = (pr_number, review_id)

        async def flush():
            await asyncio.sleep(2)  # wait for all events to arrive
            entry = self.pending_reviews.pop(key, None)
            if not entry:
                return

            forum_id = await self.cog.config.prs_forum_id()
            thread = await self.find_thread(forum_id, pr_number)
            if not thread:
                forum = self.cog.bot.get_channel(forum_id)
                if forum:
                    open_tag_id = await self.cog.config.prs_open_tag_id()
                    tag = resolve_tag(forum, open_tag_id)
                    pr_title = data["pull_request"]["title"]
                    pr_url = data["pull_request"]["html_url"]
                    thread_with_msg = await forum.create_thread(
                        name=f"「#{pr_number}」{pr_title}",
                        content=f"[#{pr_number}]({pr_url})",
                        applied_tags=[tag] if tag else [],
                    )
                    thread = thread_with_msg.thread
                    self.cog.thread_cache[pr_number] = thread.id

            if not thread:
                return

            # Post review body first
            if entry["body"]:
                prefix = f"# **[ Review from {entry['author']} ]({entry['url']})**\n"
                await send_message(thread, entry["body"], prefix=prefix)

            # ✅ Post inline comments oldest → newest
            for body, url in reversed(entry["comments"]):
                prefix = f"# **[ New PR review comment from {entry['author']} ]({url})**\n"
                await send_message(thread, body, prefix=prefix)

        # Cancel any existing flush task and reschedule
        if key in self.pending_reviews and "task" in self.pending_reviews[key]:
            self.pending_reviews[key]["task"].cancel()

        task = asyncio.create_task(flush())
        self.pending_reviews[key]["task"] = task

    # ---------------------------
    # Issue/PR Comments (not reviews)
    # ---------------------------

    async def handle_issue_comment(self, data):
        issue_number = data["issue"]["number"]
        comment_body = data["comment"]["body"]
        comment_author = data["comment"]["user"]["login"]
        comment_url = data["comment"]["html_url"]

        is_pr = "pull_request" in data["issue"]

        await self._handle_comment_or_review(
            data=data,
            number=issue_number,
            body=comment_body,
            author=comment_author,
            url=comment_url,
            is_pr=is_pr,
            prefix_label="New PR comment" if is_pr else "New issue comment",
        )

    async def _handle_comment_or_review(
        self,
        data: dict,
        number: int,
        body: str,
        author: str,
        url: str,
        is_pr: bool,
        prefix_label: str,
    ):
        forum_id = (
            await self.cog.config.prs_forum_id()
            if is_pr
            else await self.cog.config.issues_forum_id()
        )
        prefix = f"# **[ {prefix_label} from {author} ]({url})**\n"

        thread = await self.find_thread(forum_id, number)
        if not thread and forum_id:
            forum = self.cog.bot.get_channel(forum_id)
            if forum:
                open_tag_id = (
                    await self.cog.config.prs_open_tag_id()
                    if is_pr
                    else await self.cog.config.issues_open_tag_id()
                )
                tag = resolve_tag(forum, open_tag_id)
                title = (
                    data["issue"]["title"]
                    if "issue" in data
                    else data["pull_request"]["title"]
                )
                html_url = (
                    data["issue"]["html_url"]
                    if "issue" in data
                    else data["pull_request"]["html_url"]
                )
                thread_with_msg = await forum.create_thread(
                    name=f"「#{number}」{title}",
                    content=f"[#{number}]({html_url})",
                    applied_tags=[tag] if tag else [],
                )
                thread = thread_with_msg.thread
                self.cog.thread_cache[number] = thread.id

        if thread and body:
            await send_message(thread, body, prefix=prefix)

    # ---------------------------
    # Thread Finder
    # ---------------------------

    async def find_thread(self, forum_id, topic_number):
        if topic_number in self.cog.thread_cache:
            thread_id = self.cog.thread_cache[topic_number]
            thread = self.cog.bot.get_channel(thread_id)
            if thread:
                return thread

        forum = self.cog.bot.get_channel(forum_id)
        if not forum:
            return None

        for thread in forum.threads:
            if f"「#{topic_number}」" in thread.name:
                self.cog.thread_cache[topic_number] = thread.id
                return thread

        async for thread in forum.archived_threads(limit=None):
            if f"「#{topic_number}」" in thread.name:
                self.cog.thread_cache[topic_number] = thread.id
                return thread

        return None
