import discord
from .utils import send_message, resolve_tag


class GitHubEventHandlers:
    def __init__(self, cog):
        self.cog = cog

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
            thread = await forum.create_thread(
                name=f"「#{issue_number}」{issue_title}",
                content=f"[#{issue_number}]({issue_url})",
                applied_tags=[tag] if tag else [],
            )
            self.cog.thread_cache[issue_number] = thread.id

        thread = await self.find_thread(forum_id, issue_number)
        if not thread and forum:
            # Auto-create missing thread
            open_tag_id = await self.cog.config.issues_open_tag_id()
            tag = resolve_tag(forum, open_tag_id)
            thread = await forum.create_thread(
                name=f"「#{issue_number}」{issue_title}",
                content=f"[#{issue_number}]({issue_url})",
                applied_tags=[tag] if tag else [],
            )
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

        # Feed chat announcements
        feed_chat_id = await self.cog.config.issues_feed_chat_id()
        if feed_chat_id:
            feed_chat = self.cog.bot.get_channel(feed_chat_id)
            if feed_chat:
                if action == "opened":
                    await send_message(
                        feed_chat,
                        f"{role_mention} New issue opened: "
                        f"**[{issue_title}]({issue_url})** by {issue_author}",
                    )
                elif action == "closed":
                    await send_message(
                        feed_chat,
                        f"Issue closed: **[{issue_title}]({issue_url})** Closed By: {issue_author} {role_mention}",
                    )
                elif action == "reopened":
                    await send_message(
                        feed_chat,
                        f"Issue reopened: **[{issue_title}]({issue_url})** Reopened By: {issue_author} {role_mention}",
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
            thread = await forum.create_thread(
                name=f"「#{pr_number}」{pr_title}",
                content=f"[#{pr_number}]({pr_url})",
                applied_tags=[tag] if tag else [],
            )
            self.cog.thread_cache[pr_number] = thread.id

        thread = await self.find_thread(forum_id, pr_number)
        if not thread and forum:
            # Auto-create missing thread
            open_tag_id = await self.cog.config.prs_open_tag_id()
            tag = resolve_tag(forum, open_tag_id)
            thread = await forum.create_thread(
                name=f"「#{pr_number}」{pr_title}",
                content=f"[#{pr_number}]({pr_url})",
                applied_tags=[tag] if tag else [],
            )
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

        # Feed chat announcements
        feed_chat_id = await self.cog.config.prs_feed_chat_id()
        if feed_chat_id:
            feed_chat = self.cog.bot.get_channel(feed_chat_id)
            if feed_chat:
                if action == "opened":
                    await send_message(
                        feed_chat,
                        f"{role_mention} New pull request opened: "
                        f"**[{pr_title}]({pr_url})** by {pr_author}",
                    )
                elif action == "closed":
                    if data["pull_request"].get("merged"):
                        await send_message(
                            feed_chat,
                            f"PR merged: **[{pr_title}]({pr_url})** Merged By: {pr_author} {role_mention}",
                        )
                    else:
                        await send_message(
                            feed_chat,
                            f"PR closed: **[{pr_title}]({pr_url})** Closed By: {pr_author} {role_mention}",
                        )
                elif action == "reopened":
                    await send_message(
                        feed_chat,
                        f"PR reopened: **[{pr_title}]({pr_url})** Reopened By: {pr_author} {role_mention}",
                    )

    async def handle_issue_comment(self, data):
        issue_number = data["issue"]["number"]
        comment_body = data["comment"]["body"]
        comment_author = data["comment"]["user"]["login"]
        comment_url = data["comment"]["html_url"]

        forum_id = await self.cog.config.issues_forum_id()
        thread = await self.find_thread(forum_id, issue_number)
        prefix = f"# **[ New comment from {comment_author} ]({comment_url})**\n"

        if not thread and forum_id:
            forum = self.cog.bot.get_channel(forum_id)
            if forum:
                open_tag_id = await self.cog.config.issues_open_tag_id()
                tag = resolve_tag(forum, open_tag_id)
                issue_title = data["issue"]["title"]
                issue_url = data["issue"]["html_url"]

                thread = await forum.create_thread(
                    name=f"「#{issue_number}」{issue_title}",
                    content=f"[#{issue_number}]({issue_url})",
                    applied_tags=[tag] if tag else [],
                )
                self.cog.thread_cache[issue_number] = thread.id

        if thread:
            await send_message(thread, comment_body, prefix=prefix)

    async def handle_pull_request_review(self, data):
        pr_number = data["pull_request"]["number"]
        review_body = data["review"]["body"]
        review_author = data["review"]["user"]["login"]
        review_url = data["review"]["html_url"]

        forum_id = await self.cog.config.prs_forum_id()
        thread = await self.find_thread(forum_id, pr_number)
        prefix = f"# **[ Review from {review_author} ]({review_url})**\n"

        if not thread and forum_id:
            forum = self.cog.bot.get_channel(forum_id)
            if forum:
                open_tag_id = await self.cog.config.prs_open_tag_id()
                tag = resolve_tag(forum, open_tag_id)
                pr_title = data["pull_request"]["title"]
                pr_url = data["pull_request"]["html_url"]

                thread = await forum.create_thread(
                    name=f"「#{pr_number}」{pr_title}",
                    content=f"[#{pr_number}]({pr_url})",
                    applied_tags=[tag] if tag else [],
                )
                self.cog.thread_cache[pr_number] = thread.id

        if thread:
            await send_message(thread, review_body, prefix=prefix)

    async def handle_pull_request_review_comment(self, data):
        pr_number = data["pull_request"]["number"]
        comment_body = data["comment"]["body"]
        comment_author = data["comment"]["user"]["login"]
        comment_url = data["comment"]["html_url"]

        forum_id = await self.cog.config.prs_forum_id()
        thread = await self.find_thread(forum_id, pr_number)
        prefix = f"# **[ New comment from {comment_author} ]({comment_url})**\n"

        if not thread and forum_id:
            forum = self.cog.bot.get_channel(forum_id)
            if forum:
                open_tag_id = await self.cog.config.prs_open_tag_id()
                tag = resolve_tag(forum, open_tag_id)
                pr_title = data["pull_request"]["title"]
                pr_url = data["pull_request"]["html_url"]

                thread = await forum.create_thread(
                    name=f"「#{pr_number}」{pr_title}",
                    content=f"[#{pr_number}]({pr_url})",
                    applied_tags=[tag] if tag else [],
                )
                self.cog.thread_cache[pr_number] = thread.id

        if thread:
            await send_message(thread, comment_body, prefix=prefix)

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
