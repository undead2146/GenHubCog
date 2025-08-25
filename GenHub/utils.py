import discord

async def send_message(channel, content: str, prefix: str = ""):
    """Send a message, splitting into chunks if >2000 chars (including prefix)."""
    limit = 2000
    allowed_mentions = discord.AllowedMentions(
        roles=True, users=True, everyone=True
    )

    if len(prefix) > limit:
        prefix = prefix[: limit - 3] + "..."

    chunks = [content[i : i + limit] for i in range(0, len(content), limit)]

    for i, chunk in enumerate(chunks):
        if i == 0 and prefix:
            available = limit - len(prefix)
            if len(chunk) > available:
                await channel.send(
                    prefix + chunk[:available], allowed_mentions=allowed_mentions
                )
                remainder = chunk[available:]
                for j in range(0, len(remainder), limit):
                    await channel.send(
                        remainder[j : j + limit], allowed_mentions=allowed_mentions
                    )
            else:
                await channel.send(
                    prefix + chunk, allowed_mentions=allowed_mentions
                )
        else:
            await channel.send(chunk, allowed_mentions=allowed_mentions)


async def get_role_mention(guild, role_id: int):
    """Resolve a role mention safely."""
    if not role_id:
        return ""
    role = guild.get_role(role_id)
    return role.mention if role else ""


def format_message(emoji, action, title, url, author, role_mention, extra=""):
    """Format a standard message for issues/PRs."""
    msg = f"{emoji} **{action}:** [{title}]({url})\n"
    msg += f"👤 By: **{author}** {role_mention}"
    if extra:
        msg += f"\n{extra}"
    return msg


async def get_or_create_tag(forum, name):
    """Find or create a tag by name (case-insensitive)."""
    for tag in forum.available_tags:
        if tag.name.lower() == name.lower():
            return tag
    try:
        return await forum.create_tag(name=name, moderated=False)
    except Exception as e:
        print(f"⚠️ Failed to create tag '{name}' in {forum.name}: {e}")
        return None


async def get_issue_tags(forum, issue):
    tags = []
    if issue["state"] == "open":
        tag = await get_or_create_tag(forum, "Open")
    else:
        tag = await get_or_create_tag(forum, "Closed")
    if tag:
        tags.append(tag)
    if issue.get("assignees"):
        active_tag = await get_or_create_tag(forum, "Active")
        if active_tag:
            tags.append(active_tag)
    return tags


async def get_pr_tags(forum, pr):
    tags = []
    if pr.get("state") == "open":
        tag = await get_or_create_tag(forum, "Open")
    elif pr.get("merged") or pr.get("merged_at") or (
        "pull_request" in pr and pr["pull_request"].get("merged_at")
    ):
        tag = await get_or_create_tag(forum, "Merged")
    else:
        tag = await get_or_create_tag(forum, "Closed")
    if tag:
        tags.append(tag)
    return tags


async def update_status_tag(thread, new_status_name):
    """Replace status tag while preserving repo tag."""
    forum = thread.parent
    new_status_tag = await get_or_create_tag(forum, new_status_name)
    if not new_status_tag:
        return
    current_tags = list(thread.applied_tags)
    status_names = {"open", "closed", "merged", "active"}
    current_tags = [t for t in current_tags if t.name.lower() not in status_names]
    current_tags.append(new_status_tag)
    await thread.edit(applied_tags=current_tags)
async def find_thread(bot, forum_id, repo_full_name, topic_number, thread_cache):
    """Find an existing thread by repo + number."""
    key = (forum_id, repo_full_name, topic_number)
    if key in thread_cache:
        cached = thread_cache[key]
        if hasattr(cached, "id"):
            return cached
        thread = bot.get_channel(cached)
        if thread:
            return thread

    forum = bot.get_channel(forum_id)
    if not forum:
        return None

    repo_tag = await get_or_create_tag(forum, repo_full_name.split("/")[-1])

    for thread in getattr(forum, "threads", []):
        if f"「#{topic_number}」" in thread.name and repo_tag in thread.applied_tags:
            thread_cache[key] = thread
            return thread

    if hasattr(forum, "archived_threads"):
        async for thread in forum.archived_threads(limit=None):
            if f"「#{topic_number}」" in thread.name and repo_tag in thread.applied_tags:
                thread_cache[key] = thread
                return thread

    return None


from types import SimpleNamespace

async def get_or_create_thread(
    bot, forum_id, repo_full_name, number, title, url, tags, thread_cache
):
    key_str = (str(forum_id), repo_full_name, number)
    key_int = (int(forum_id), repo_full_name, number)

    # --- Cache lookup ---
    for key in (key_str, key_int):
        if key in thread_cache:
            cached = thread_cache[key]
            if cached is None:
                continue
            # unwrap if it's a wrapper
            if hasattr(cached, "thread"):
                return cached.thread
            return cached

    forum = bot.get_channel(forum_id)
    if not forum:
        return None

    thread_with_msg = await forum.create_thread(
        name=f"「#{number}」{title}",
        content=f"[#{number}]({url})",
        applied_tags=tags,
    )

    # unwrap if forum.create_thread returned a wrapper
    if hasattr(thread_with_msg, "thread"):
        thread = thread_with_msg.thread
    else:
        thread = thread_with_msg

    # store the actual thread object in cache
    thread_cache[key_str] = thread
    thread_cache[key_int] = thread

    # always return the actual thread object
    return thread
