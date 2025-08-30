import discord
import re

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
    # Keep action plain (no bold) so tests that match substrings like
    # "🆕 Issue created" succeed consistently.
    msg = f"{emoji} {action}: [{title}]({url})\n"
    msg += f"👤 By: {author} {role_mention}"
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
    # Support both tuple and legacy string keys, and values that are either
    # thread objects or string IDs.
    keys_to_try = [
        (forum_id, repo_full_name, topic_number),
        (str(forum_id), repo_full_name, topic_number),
        f"{forum_id}:{repo_full_name}:{topic_number}",
    ]
    for k in keys_to_try:
        if k in thread_cache:
            cached = thread_cache[k]
            # If we stored a thread object, return it directly
            if hasattr(cached, "id"):
                return cached
            # Otherwise, assume it's an ID string
            try:
                thread = bot.get_channel(int(cached))
                if thread:
                    return thread
            except Exception:
                pass

    forum = bot.get_channel(forum_id)
    if not forum:
        return None

    pattern = rf"「#{topic_number}」(?:\D|$)"

    threads_attr = getattr(forum, "threads", [])
    # Some tests hand us a Mock for threads which is not iterable; guard it.
    try:
        iterable_threads = list(threads_attr) if threads_attr else []
    except TypeError:
        iterable_threads = []

    for thread in iterable_threads:
        try:
            if re.match(pattern, thread.name):
                # Normalize to tuple keys; store the thread object
                thread_cache[(forum_id, repo_full_name, topic_number)] = thread
                thread_cache[(str(forum_id), repo_full_name, topic_number)] = thread
                return thread
        except Exception:
            continue

    if hasattr(forum, "archived_threads"):
        async for thread in forum.archived_threads(limit=None):
            if re.match(pattern, thread.name):
                thread_cache[(forum_id, repo_full_name, topic_number)] = thread
                thread_cache[(str(forum_id), repo_full_name, topic_number)] = thread
                return thread

    return None


async def get_or_create_thread(
    bot, forum_id, repo_full_name, number, title, url, tags, thread_cache
):
    # First try to find an existing thread
    existing = await find_thread(bot, forum_id, repo_full_name, number, thread_cache)
    if existing:
        return existing, False

    forum = bot.get_channel(forum_id)
    if not forum:
        return None, False

    try:
        thread_with_msg = await forum.create_thread(
            name=f"「#{number}」{title}",
            content=f"[#{number}]({url})",
            applied_tags=tags,
        )
    except discord.Forbidden:
        print(f"⚠️ Missing permissions to create thread in {forum.name}")
        return None, False

    thread = getattr(thread_with_msg, "thread", thread_with_msg)
    # Normalize cache to tuple keys and store the thread object directly
    key_tuple_int = (forum_id, repo_full_name, number)
    key_tuple_str = (str(forum_id), repo_full_name, number)
    thread_cache[key_tuple_int] = thread
    thread_cache[key_tuple_str] = thread
    return thread, True
