import pytest
import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from types import SimpleNamespace

import discord
import aiohttp

from GenHub import utils
from GenHub.utils import (
    DiscordRateLimiter,
    safe_discord_call,
    _extract_discord_retry_after,
    send_message,
    get_or_create_tag,
    get_or_create_thread,
    DISCORD_RATE_LIMITER,
)
from GenHub.handlers import GitHubEventHandlers, RateLimiter
from GenHub.genhub import GenHub


def test_extract_discord_retry_after():
    """test retry_after extraction from various exception formats."""
    # 1. custom object with retry_after attribute
    class CustomRateLimited(Exception):
        retry_after = 3.5
        is_global = True

    delay, is_glob = _extract_discord_retry_after(CustomRateLimited())
    assert delay == 3.5
    assert is_glob is True

    # 2. exception string matching
    err = RuntimeError("429 Too Many Requests: retry_after: 4.25s")
    delay, is_glob = _extract_discord_retry_after(err)
    assert delay == 4.25


@pytest.mark.asyncio
async def test_safe_discord_call_recovers_from_429():
    """test that safe_discord_call detects 429 and retries until success."""
    call_count = 0

    class FakeRateLimitError(discord.HTTPException):
        def __init__(self):
            self.status = 429
            self.retry_after = 0.01

    async def flaky_operation(target_id: int):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise FakeRateLimitError()
        return f"result_for_{target_id}"

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        res = await safe_discord_call(
            flaky_operation,
            123,
            max_retries=5,
            operation_name="Flaky Discord Operation"
        )
        assert res == "result_for_123"
        assert call_count == 3
        assert mock_sleep.await_count >= 2


@pytest.mark.asyncio
async def test_safe_discord_call_handles_transient_network_error():
    """test that safe_discord_call handles client os error and transient disconnects."""
    call_count = 0

    async def network_operation():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise aiohttp.ClientOSError("Connection reset by peer")
        return "connected"

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        res = await safe_discord_call(
            network_operation,
            max_retries=3,
            operation_name="Network Operation"
        )
        assert res == "connected"
        assert call_count == 2
        mock_sleep.assert_awaited()


@pytest.mark.asyncio
async def test_safe_discord_call_exhausts_retries():
    """test that safe_discord_call raises after exhausting all retries."""
    class FakeRateLimitError(discord.HTTPException):
        def __init__(self):
            self.status = 429
            self.retry_after = 0.01

    async def failing_op():
        raise FakeRateLimitError()

    with patch("asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(discord.HTTPException):
            await safe_discord_call(
                failing_op,
                max_retries=2,
                operation_name="Failing Op"
            )


@pytest.mark.asyncio
async def test_discord_rate_limiter_pacing():
    """test that pace_thread_creation paces consecutive calls."""
    limiter = DiscordRateLimiter()
    limiter._min_thread_interval = 0.05
    start = time.time()
    await limiter.pace_thread_creation(999)
    await limiter.pace_thread_creation(999)
    elapsed = time.time() - start
    assert elapsed >= 0.04


@pytest.mark.asyncio
async def test_tag_caching_and_creation():
    """test tag caching avoids duplicate discord channel edits."""
    utils._FORUM_TAG_CACHE.clear()

    tag_obj = SimpleNamespace(name="Open")
    forum = Mock()
    forum.id = 101
    forum.available_tags = [tag_obj]
    forum.create_tag = AsyncMock()

    # lookup existing
    tag1 = await get_or_create_tag(forum, "open")
    assert tag1 is tag_obj
    forum.create_tag.assert_not_awaited()

    # lookup created
    new_tag = SimpleNamespace(name="Bug")
    forum.create_tag = AsyncMock(return_value=new_tag)
    tag2 = await get_or_create_tag(forum, "Bug")
    assert tag2 is new_tag
    forum.create_tag.assert_awaited_once()

    # lookup again from cache
    forum.create_tag.reset_mock()
    tag3 = await get_or_create_tag(forum, "bug")
    assert tag3 is new_tag
    forum.create_tag.assert_not_awaited()


@pytest.mark.asyncio
async def test_tag_creation_failure_fallback():
    """test that tag creation gracefully falls back to none on rate limit or permission error."""
    utils._FORUM_TAG_CACHE.clear()
    forum = Mock()
    forum.id = 202
    forum.name = "TestForum"
    forum.available_tags = []
    forum.create_tag = AsyncMock(side_effect=discord.Forbidden(Mock(status=403), "Channel edit cooldown"))

    tag = await get_or_create_tag(forum, "NonExistent")
    assert tag is None


@pytest.mark.asyncio
async def test_send_message_with_rate_limit_recovery():
    """test that send_message delivers all chunks under rate limits."""
    channel = AsyncMock()
    call_idx = 0

    class FakeRateLimitError(discord.HTTPException):
        def __init__(self):
            self.status = 429
            self.retry_after = 0.01

    async def flaky_send(*args, **kwargs):
        nonlocal call_idx
        call_idx += 1
        if call_idx == 1:
            raise FakeRateLimitError()
        return Mock(id=12345)

    channel.send = AsyncMock(side_effect=flaky_send)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        await send_message(channel, "hello world")
        assert call_idx >= 2


@pytest.mark.asyncio
async def test_github_rate_limiter_secondary_abuse_recovery():
    """test that _make_github_request recovers from secondary abuse rate limits."""
    cog = Mock()
    handler = GitHubEventHandlers(cog)

    call_count = 0

    class FakeResp:
        def __init__(self, status, text_body, headers):
            self.status = status
            self._text = text_body
            self.headers = headers

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def text(self):
            return self._text

        async def json(self):
            return {"data": "ok"}

    class FakeSession:
        def request(self, method, url):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Secondary rate limit 403
                return FakeResp(403, "You have exceeded a secondary rate limit.", {"Retry-After": "0.01"})
            return FakeResp(200, "ok", {"X-RateLimit-Remaining": "4990"})

    with patch("asyncio.sleep", new_callable=AsyncMock):
        status, data = await handler._make_github_request(FakeSession(), "https://api.github.com/test")
        assert status == 200
        assert data == {"data": "ok"}
        assert call_count == 2


@pytest.mark.asyncio
async def test_on_guild_join_syncs_tree():
    """test that on_guild_join syncs slash commands for the new guild."""
    bot = Mock()
    bot.tree = Mock()
    bot.tree.sync = AsyncMock()

    cog = GenHub(bot)
    new_guild = Mock()
    new_guild.name = "New Awesome Server"
    new_guild.id = 555666777

    await cog.on_guild_join(new_guild)
    bot.tree.sync.assert_awaited_once_with(guild=new_guild)
