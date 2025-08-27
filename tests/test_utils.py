import pytest
from unittest.mock import AsyncMock, Mock
from GenHub import utils
from GenHub.utils import send_message, format_message

@pytest.mark.asyncio
async def test_send_message_splits_long_text():
    channel = AsyncMock()
    long_text = "x" * 5000
    await send_message(channel, long_text, prefix="PREFIX: ")
    assert channel.send.await_count > 1

def test_format_message_contains_fields():
    msg = format_message("🔥", "Test", "Title", "http://url", "author", "@role")
    assert "🔥" in msg
    assert "Title" in msg
    assert "author" in msg


@pytest.mark.asyncio
async def test_send_message_prefix_too_long_and_split():
    channel = AsyncMock()
    prefix = "x" * 2100
    content = "y" * 10
    await send_message(channel, content, prefix=prefix)
    channel.send.assert_awaited()


@pytest.mark.asyncio
async def test_get_role_mention_none_and_missing():
    from GenHub import utils
    guild = Mock()
    guild.get_role = Mock(return_value=None)
    result = await utils.get_role_mention(guild, None)
    assert result == ""
    result = await utils.get_role_mention(guild, 123)
    assert result == ""


@pytest.mark.asyncio
async def test_get_or_create_tag_exception():
    from GenHub import utils
    forum = Mock()
    forum.available_tags = []
    forum.create_tag = AsyncMock(side_effect=Exception("fail"))
    tag = await utils.get_or_create_tag(forum, "X")
    assert tag is None


@pytest.mark.asyncio
async def test_update_status_tag_no_new_tag(monkeypatch):
    from GenHub import utils
    thread = AsyncMock()
    thread.parent = Mock()
    async def fake_get_or_create_tag(forum, name): return None
    monkeypatch.setattr(utils, "get_or_create_tag", fake_get_or_create_tag)
    await utils.update_status_tag(thread, "Open")
    # should not call edit
    thread.edit.assert_not_awaited()


@pytest.mark.asyncio
async def test_find_thread_archived_found():
    from GenHub import utils
    forum = AsyncMock()
    tag = Mock()
    tag.name = "repo"
    forum.available_tags = [tag]
    t = Mock()
    t.name = "「#1」Test"
    t.applied_tags = [tag]
    async def fake_archived_threads(limit=None):
        yield t
    forum.archived_threads = fake_archived_threads
    forum.threads = []  # <-- Add this to make it iterable
    bot = Mock()
    bot.get_channel = Mock(return_value=forum)
    result = await utils.find_thread(bot, 1, "owner/repo", 1, {})
    assert result == t


@pytest.mark.asyncio
async def test_send_message_splits_remainder():
    channel = AsyncMock()
    prefix = "PRE:"
    content = "x" * 2100
    await utils.send_message(channel, content, prefix=prefix)
    assert channel.send.await_count > 1


@pytest.mark.asyncio
async def test_utils_send_message_edge_cases():
    channel = AsyncMock()
    # prefix longer than 2000
    await utils.send_message(channel, "short", prefix="x"*2100)
    # content exactly 2000
    await utils.send_message(channel, "y"*2000, prefix="PRE:")


@pytest.mark.asyncio
async def test_utils_get_or_create_thread_forum_none():
    bot = Mock()
    bot.get_channel = Mock(return_value=None)
    res = await utils.get_or_create_thread(bot, 1, "owner/repo", 1, "t", "u", [], {})
    assert res is None


@pytest.mark.asyncio
async def test_utils_find_thread_forum_none():
    bot = Mock()
    bot.get_channel = Mock(return_value=None)
    res = await utils.find_thread(bot, 1, "owner/repo", 1, {})
    assert res is None
