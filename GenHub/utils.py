import discord

async def send_message(channel, content: str, prefix: str = ""):
    """Send a message, splitting into chunks if >2000 chars (including prefix)."""
    limit = 2000

    # If prefix itself is too long, truncate it
    if len(prefix) > limit:
        prefix = prefix[:limit - 3] + "..."

    # Split content into chunks
    chunks = [content[i:i + limit] for i in range(0, len(content), limit)]

    for i, chunk in enumerate(chunks):
        if i == 0 and prefix:
            # Ensure prefix + chunk fits
            available = limit - len(prefix)
            if len(chunk) > available:
                await channel.send(prefix + chunk[:available])
                # Send the rest as new chunks
                remainder = chunk[available:]
                for j in range(0, len(remainder), limit):
                    await channel.send(remainder[j:j + limit])
            else:
                await channel.send(prefix + chunk)
        else:
            await channel.send(chunk)

def resolve_tag(forum: discord.ForumChannel, tag_id: int):
    """Resolve a tag ID into a ForumTag object if available."""
    if not tag_id:
        return None
    return discord.utils.get(forum.available_tags, id=tag_id)
