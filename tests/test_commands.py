import pytest
from unittest.mock import AsyncMock
from GenHub.slash_commands import SlashCommands
from GenHub.config_commands import ConfigCommands


class DummyConfigEntry:
    def __init__(self):
        self.set = AsyncMock()


class DummyCog:
    def __init__(self):
        self.config = type("Config", (), {})()
        self.config.webhook_host = DummyConfigEntry()
        self.config.webhook_port = DummyConfigEntry()


@pytest.mark.asyncio
async def test_slash_command_updates_config():
    cog = DummyCog()
    slash = SlashCommands(cog)

    class DummyResponse:
        def __init__(self):
            self.send_message = AsyncMock()

    class DummyInteraction:
        def __init__(self):
            self.response = DummyResponse()

    interaction = DummyInteraction()

    await slash._do_config_update(
        interaction,
        webhook_host="127.0.0.1",
        webhook_port=9000,
    )

    cog.config.webhook_host.set.assert_awaited_with("127.0.0.1")
    cog.config.webhook_port.set.assert_awaited_with(9000)
    interaction.response.send_message.assert_awaited()


@pytest.mark.asyncio
async def test_config_command_addrepo():
    cog = DummyCog()
    cmd = ConfigCommands(cog)

    class DummyCtx:
        def __init__(self):
            self.send = AsyncMock()

    ctx = DummyCtx()

    class FakeRepos(list):
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

    def allowed_repos_callable():
        return FakeRepos()

    cog.config.allowed_repos = allowed_repos_callable

    await cmd.addrepo(ctx, "new/repo")

    ctx.send.assert_awaited()
