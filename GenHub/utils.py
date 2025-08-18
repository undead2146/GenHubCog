import discord

async def send_message(channel, content: str, prefix: str = ""):
    """Send a message, splitting into chunks if >2000 chars (including prefix)."""
    limit = 2000
    allowed_mentions = discord.AllowedMentions(
        roles=True,  # allow role mentions
        users=True,  # allow user mentions
        everyone=True  # allow @everyone/@here
    )

    # If prefix itself is too long, truncate it
    if len(prefix) > limit:
        prefix = prefix[: limit - 3] + "..."

    # Split content into chunks
    chunks = [content[i : i + limit] for i in range(0, len(content), limit)]

    for i, chunk in enumerate(chunks):
        if i == 0 and prefix:
            available = limit - len(prefix)
            if len(chunk) > available:
                await channel.send(
                    prefix + chunk[:available],
                    allowed_mentions=allowed_mentions,
                )
                remainder = chunk[available:]
                for j in range(0, len(remainder), limit):
                    await channel.send(
                        remainder[j : j + limit],
                        allowed_mentions=allowed_mentions,
                    )
            else:
                await channel.send(
                    prefix + chunk, allowed_mentions=allowed_mentions
                )
        else:
            await channel.send(chunk, allowed_mentions=allowed_mentions)

def resolve_tag(forum: discord.ForumChannel, tag_id: int):
    """Resolve a tag ID into a ForumTag object if available."""
    if not tag_id:
        return None
    return discord.utils.get(forum.available_tags, id=tag_id)
