import discord


async def send_message(channel, content: str, prefix: str = ""):
    """Send a message, splitting into chunks if >2000 chars."""
    limit = 2000
    chunks = [content[i : i + limit] for i in range(0, len(content), limit)]
    for i, chunk in enumerate(chunks):
        if i == 0 and prefix:
            await channel.send(prefix + chunk)
        else:
            await channel.send(chunk)


def resolve_tag(forum: discord.ForumChannel, tag_id: int):
    """Resolve a tag ID into a ForumTag object if available."""
    if not tag_id:
        return None
    return discord.utils.get(forum.available_tags, id=tag_id)
