import pytest
import asyncio
from unittest.mock import AsyncMock, Mock
from GenHub.genhub import GenHub

@pytest.mark.asyncio
async def test_setup_adds_cog():
    # minimal test to exercise GenHub.__init__.setup
    # import the package module itself (not the __init__ attribute)
    import GenHub as genhub

    bot = Mock()
    bot.add_cog = AsyncMock()

    # call setup from the package and ensure add_cog awaited
    await genhub.setup(bot)
    bot.add_cog.assert_awaited()


@pytest.mark.asyncio
async def test_cog_load_and_unload(monkeypatch):
    from unittest.mock import AsyncMock, Mock
    from GenHub.genhub import GenHub

    bot = AsyncMock()
    bot.guilds = [Mock(id=1, name="Guild")]
    bot.tree.sync = AsyncMock()
    bot.add_cog = AsyncMock()
    bot.tree.add_command = Mock()

    monkeypatch.setattr("GenHub.genhub.WebhookServer.start", AsyncMock(return_value=None))
    monkeypatch.setattr("GenHub.genhub.WebhookServer.stop", AsyncMock(return_value=None))

    cog = GenHub(bot)
    # Mock config methods
    cog.config.thread_cache = AsyncMock(return_value={})
    cog.config.thread_cache.set = AsyncMock()
    await cog.cog_load()
    bot.add_cog.assert_awaited()
    bot.tree.add_command.assert_called()

    await cog.cog_unload()
    # Task should be cancelled or in cancelling state (robust across environments)
    assert cog.task.cancelled() or cog.task.cancelling()


@pytest.mark.asyncio
async def test_cog_load_sync_failure(capsys):
    from unittest.mock import AsyncMock, Mock
    from GenHub.genhub import GenHub

    bot = AsyncMock()
    bot.guilds = [Mock(id=1, name="Guild")]
    bot.tree.sync = AsyncMock(side_effect=RuntimeError("fail"))
    bot.add_cog = AsyncMock()
    bot.tree.add_command = Mock()

    cog = GenHub(bot)
    # Mock config methods
    cog.config.thread_cache = AsyncMock(return_value={})
    cog.config.thread_cache.set = AsyncMock()
    await cog.cog_load()
    out = capsys.readouterr().out
    assert "Failed to sync slash commands" in out
