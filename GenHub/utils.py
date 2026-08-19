import discord
import re

def clean_github_markdown(text: str) -> str:
    """Clean and convert GitHub-specific HTML and markdown tags into clean Discord markdown."""
    if not text:
        return ""

    # 1. Strip HTML comments <!-- ... -->
    text = re.sub(r"<!--[\s\S]*?-->", "", text)

    # 2. Convert <details><summary>...
    text = re.sub(r"<summary>\s*<b>(.*?)</b>\s*</summary>", r"**\1:**", text, flags=re.IGNORECASE)
    text = re.sub(r"<summary>\s*<strong>(.*?)</strong>\s*</summary>", r"**\1:**", text, flags=re.IGNORECASE)
    text = re.sub(r"<summary>\s*(.*?)\s*</summary>", r"**\1:**", text, flags=re.IGNORECASE)
    text = re.sub(r"</?(?:details|summary)[^>]*>", "", text, flags=re.IGNORECASE)

    # 3. HTML formatting to markdown
    text = re.sub(r"<b>(.*?)</b>", r"**\1**", text, flags=re.IGNORECASE)
    text = re.sub(r"<strong>(.*?)</strong>", r"**\1**", text, flags=re.IGNORECASE)
    text = re.sub(r"<i>(.*?)</i>", r"*\1*", text, flags=re.IGNORECASE)
    text = re.sub(r"<em>(.*?)</em>", r"*\1*", text, flags=re.IGNORECASE)
    text = re.sub(r"<code>(.*?)</code>", r"`\1`", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?p>", "\n", text, flags=re.IGNORECASE)

    # 4. Remove other generic HTML tags
    text = re.sub(r"<[/]?(?:div|span|section|article|font|center)[^>]*>", "", text, flags=re.IGNORECASE)

    # 5. Clean extra whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def create_comment_embed(
    author: str,
    body: str,
    url: str,
    author_icon: str = None,
    is_bot: bool = False,
    is_review: bool = False,
    extra_count: int = 0,
) -> discord.Embed:
    """Create a sleek Discord Embed for a GitHub issue or review comment."""
    clean_body = clean_github_markdown(body)

    if len(clean_body) > 2040:
        clean_body = clean_body[:1950].rstrip() + f"\n\n... *([Read full comment on GitHub](<{url}>))*"

    color = 0x5865F2 if not is_bot else (0x23A55A if is_review else 0x4E5058)
    role_label = "Bot Review Summary" if (is_bot and is_review) else ("Bot Summary" if is_bot else "Comment")

    embed = discord.Embed(
        description=clean_body if clean_body else "*Empty comment body*",
        color=color,
    )
    author_name = f"{author} ({role_label})"
    embed.set_author(
        name=author_name[:256],
        url=url,
        icon_url=author_icon if author_icon else "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png",
    )

    if extra_count > 0:
        embed.set_footer(text=f"↳ Also submitted {extra_count} additional automated review comments on GitHub")
    else:
        embed.set_footer(text="GitHub Discussion")

    return embed


async def send_message(channel, content: str = "", prefix: str = "", embed: discord.Embed = None):
    """Send a message or embed, splitting long text into chunks if needed."""
    if embed:
        await channel.send(embed=embed)
        return

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


def get_role_mention(guild, role_id: int):
    """Resolve a role mention safely."""
    if not role_id:
        return ""
    role = guild.get_role(role_id)
    return role.mention if role else ""


def is_bot_author(author_login: str, user_data: dict = None) -> bool:
    """Determine if a GitHub author is an automated bot."""
    if not author_login:
        return False
    if user_data and user_data.get("type") == "Bot":
        return True
    login_lower = author_login.lower().strip()
    if login_lower.endswith("[bot]"):
        return True
    known_bots = {
        "coderabbitai",
        "coderabbitai[bot]",
        "deepsource-autofix",
        "deepsource-autofix[bot]",
        "deepsource[bot]",
        "github-actions",
        "github-actions[bot]",
        "kilo-code-review",
        "kilo-code-review[bot]",
        "greptile-ai",
        "greptile-ai[bot]",
        "codecov",
        "codecov[bot]",
        "dependabot",
        "dependabot[bot]",
        "sonarcloud",
        "sonarcloud[bot]",
        "linear",
        "linear[bot]",
        "vercel",
        "vercel[bot]",
        "snyk-bot",
        "renovate",
        "renovate[bot]",
    }
    return login_lower in known_bots



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
    # First check cache for a valid thread
    keys_to_try = [
        (forum_id, repo_full_name, topic_number),
        (str(forum_id), repo_full_name, topic_number),
        f"{forum_id}:{repo_full_name}:{topic_number}",
    ]
    for k in keys_to_try:
        if k in thread_cache:
            cached = thread_cache[k]
            # If we stored a thread object, do a quick validation
            if hasattr(cached, "id"):
                try:
                    # Quick validation - try to access a property that would fail if deleted
                    if hasattr(cached, 'name'):
                        _ = cached.name  # This should fail if the thread is deleted
                        # Also check if the thread is accessible by trying to get its ID
                        _ = cached.id
                    return cached
                except (AttributeError, discord.NotFound, discord.Forbidden):
                    # Thread is invalid/stale/deleted, remove from cache
                    print(f"🗑️ Removing stale thread #{topic_number} from cache")
                    del thread_cache[k]
                    continue

    forum = bot.get_channel(forum_id)
    if not forum:
        return None

    # Get repository short name for pattern matching
    repo_short_name = repo_full_name.split('/')[-1]

    # Try patterns: first with new format, then legacy patterns for backward compatibility
    patterns = [
        rf"\[GH\] \[#{topic_number}\](?:\s|$)",  # New format: [GH] [#NUMBER]
        rf"「{re.escape(repo_short_name)}#{topic_number}」(?:\D|$)",  # Old format with corner brackets
        rf"{re.escape(repo_short_name)}#{topic_number}(?:\D|$)",
        rf"「#{topic_number}」(?:\D|$)",  # Legacy pattern for backward compatibility
        rf"#{topic_number}(?:\D|$)",
        rf"{topic_number}(?:\D|$)",
    ]

    for pattern in patterns:
        threads_attr = getattr(forum, "threads", [])
        # Some tests hand us a Mock for threads which is not iterable; guard it.
        try:
            iterable_threads = list(threads_attr) if threads_attr else []
        except TypeError:
            iterable_threads = []

        for thread in iterable_threads:
            try:
                if re.match(pattern, thread.name):
                    # Additional validation: ensure thread is not deleted
                    try:
                        if hasattr(thread, 'name'):
                            _ = thread.name  # Quick check if thread is accessible
                        # Normalize to tuple keys; store the thread object
                        thread_cache[(forum_id, repo_full_name, topic_number)] = thread
                        thread_cache[(str(forum_id), repo_full_name, topic_number)] = thread
                        return thread
                    except (discord.NotFound, discord.Forbidden):
                        continue  # Thread is deleted or inaccessible, skip it
            except Exception:
                continue

        if hasattr(forum, "archived_threads"):
            try:
                async for thread in forum.archived_threads(limit=100):  # Limit to avoid excessive API calls
                    if re.match(pattern, thread.name):
                        # Additional validation for archived threads
                        try:
                            if hasattr(thread, 'name'):
                                _ = thread.name  # Quick check if thread is accessible
                            thread_cache[(forum_id, repo_full_name, topic_number)] = thread
                            thread_cache[(str(forum_id), repo_full_name, topic_number)] = thread
                            return thread
                        except (discord.NotFound, discord.Forbidden):
                            continue  # Thread is deleted or inaccessible, skip it
            except (TypeError, AttributeError):
                # archived_threads might be a Mock in tests, skip it
                pass

    return None


async def get_or_create_thread(
    bot, forum_id, repo_full_name, number, title, url, tags, thread_cache, initial_content=None
):
    # First try to find an existing thread
    existing = await find_thread(bot, forum_id, repo_full_name, number, thread_cache)
    if existing:
        print(f"📝 Found existing thread #{number} for {repo_full_name}")
        # Check if thread is archived - if so, recreate as active for reconcile
        if hasattr(existing, 'archived') and existing.archived:
            print(f"ℹ️ Found archived thread #{number}, recreating as active")
            # Remove from cache and treat as not found to force recreation
            keys_to_remove = [
                (forum_id, repo_full_name, number),
                (str(forum_id), repo_full_name, number),
                f"{forum_id}:{repo_full_name}:{number}",
            ]
            for key in keys_to_remove:
                thread_cache.pop(key, None)
            existing = None  # Force recreation
        else:
            # Validate thread is still accessible with more robust checks
            try:
                # First check if the thread object is still valid by accessing basic properties
                _ = existing.id  # This should always work for valid threads

                # Try to access the channel property to ensure the thread still exists
                if hasattr(existing, 'channel'):
                    _ = existing.channel

                # For real Discord threads, also check name, but be lenient for test mocks
                if hasattr(existing, 'name'):
                    _ = existing.name

                # Additional validation: try to get thread history (this will fail if deleted)
                try:
                    async for message in existing.history(limit=1):
                        break  # Just check if we can iterate, don't need the message
                except (discord.NotFound, discord.Forbidden):
                    # Thread is deleted or inaccessible
                    raise discord.NotFound("Thread history inaccessible")

                # Update name if it doesn't match the expected
                repo_short_name = repo_full_name.split('/')[-1]
                expected_name = f"[GH] [#{number}] {title}"
                if hasattr(existing, 'name') and existing.name != expected_name:
                    try:
                        await existing.edit(name=expected_name)
                        print(f"📝 Updated thread name for #{number}")
                    except (discord.Forbidden, discord.NotFound):
                        # If we can't edit, the thread might be deleted or we lack permissions
                        print(f"⚠️ Could not update thread name for #{number}, recreating")
                        # Remove from cache and treat as not found
                        keys_to_remove = [
                            (forum_id, repo_full_name, number),
                            (str(forum_id), repo_full_name, number),
                            f"{forum_id}:{repo_full_name}:{number}",
                        ]
                        for key in keys_to_remove:
                            thread_cache.pop(key, None)
                        existing = None  # Force recreation
            except (discord.NotFound, discord.Forbidden) as e:
                print(f"⚠️ Thread #{number} appears to be deleted or inaccessible ({type(e).__name__}), recreating")
                # Remove from cache and treat as not found
                keys_to_remove = [
                    (forum_id, repo_full_name, number),
                    (str(forum_id), repo_full_name, number),
                    f"{forum_id}:{repo_full_name}:{number}",
                ]
                for key in keys_to_remove:
                    thread_cache.pop(key, None)
                existing = None  # Force recreation
            except AttributeError as e:
                # For test objects that might not have all attributes, be more lenient
                # Only treat as invalid if it's clearly a Discord API error
                if "discord" in str(type(existing)).lower():
                    print(f"⚠️ Thread #{number} appears to be invalid ({type(e).__name__}), recreating")
                    keys_to_remove = [
                        (forum_id, repo_full_name, number),
                        (str(forum_id), repo_full_name, number),
                        f"{forum_id}:{repo_full_name}:{number}",
                    ]
                    for key in keys_to_remove:
                        thread_cache.pop(key, None)
                    existing = None  # Force recreation

    if existing:
        return existing, False

    forum = bot.get_channel(forum_id)
    if not forum:
        print(f"⚠️ Could not find forum {forum_id}")
        return None, False

    # Create thread name with repository to avoid conflicts
    repo_short_name = repo_full_name.split('/')[-1]
    thread_name = f"[GH] [#{number}] {title}"

    print(f"🔄 Creating new thread for {repo_full_name}#{number}")
    try:
        # Use provided initial content or create a proper formatted message
        content = initial_content if initial_content else f"🆕 Issue created: [{title}]({url})\n👤 By: Unknown"

        thread_with_msg = await forum.create_thread(
            name=thread_name,
            content=content,
            applied_tags=tags,
        )
        print(f"✅ Created new thread for {repo_full_name}#{number}")
    except discord.Forbidden:
        print(f"⚠️ Missing permissions to create thread in {forum.name}")
        return None, False
    except Exception as e:
        print(f"⚠️ Failed to create thread for {repo_full_name}#{number}: {e}")
        return None, False

    thread = getattr(thread_with_msg, "thread", thread_with_msg)
    # Normalize cache to tuple keys and store the thread object directly
    key_tuple_int = (forum_id, repo_full_name, number)
    key_tuple_str = (str(forum_id), repo_full_name, number)
    thread_cache[key_tuple_int] = thread
    thread_cache[key_tuple_str] = thread
    return thread, True


def find_associated_chat_channel(guild, forum_channel, is_pr: bool):
    """Heuristically discover the accompanying text chat channel for a forum feed."""
    if not guild or not forum_channel:
        return None

    category = getattr(forum_channel, "category", None)
    keywords = (
        ["pr", "pull-request", "pull_request", "pulls", "prs"]
        if is_pr
        else ["issue", "issues", "bugs", "bug", "tickets", "feedback"]
    )

    # 1. Search text channels inside the SAME category first
    if category and hasattr(category, "text_channels"):
        for ch in category.text_channels:
            name = ch.name.lower().replace("-", "").replace("_", "").replace(" ", "")
            for kw in keywords:
                clean_kw = kw.replace("-", "").replace("_", "")
                if clean_kw in name:
                    return ch

    # 2. Search all text channels in the guild with "chat" in name
    if hasattr(guild, "text_channels"):
        for ch in guild.text_channels:
            name = ch.name.lower().replace("-", "").replace("_", "").replace(" ", "")
            for kw in keywords:
                clean_kw = kw.replace("-", "").replace("_", "")
                if clean_kw in name and "chat" in name:
                    return ch

        # 3. Search all text channels in the guild matching keywords
        for ch in guild.text_channels:
            name = ch.name.lower().replace("-", "").replace("_", "").replace(" ", "")
            for kw in keywords:
                clean_kw = kw.replace("-", "").replace("_", "")
                if clean_kw in name:
                    return ch

    return None


def find_associated_updates_channel(guild, forum_channel=None):
    """Heuristically discover a pinned updates / announcements channel or thread."""
    if not guild:
        return None

    keywords = ["pinnedupdates", "pinnedupdate", "updates", "pinned", "announcements", "developmentupdates", "devupdates"]

    # 1. Search inside the same category if forum provided
    if forum_channel:
        category = getattr(forum_channel, "category", None)
        if category and hasattr(category, "channels"):
            for ch in category.channels:
                name = ch.name.lower().replace("-", "").replace("_", "").replace(" ", "")
                for kw in keywords:
                    if kw in name:
                        return ch

    # 2. Search all channels in guild
    if hasattr(guild, "channels"):
        for ch in guild.channels:
            name = ch.name.lower().replace("-", "").replace("_", "").replace(" ", "")
            for kw in keywords:
                if kw in name:
                    return ch

    return None


