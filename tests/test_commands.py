import pytest
from unittest.mock import AsyncMock, Mock
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


@pytest.mark.asyncio
async def test_config_commands_group_and_reconcile():
    cog = Mock()
    cog.config = Mock()
    cog.handlers = AsyncMock()
    cmd = ConfigCommands(cog)
    ctx = Mock()
    ctx.send = AsyncMock()
    await ConfigCommands.genhub(cmd, ctx)  # group function
    await cmd.reconcile(ctx, repo="owner/repo")
    ctx.send.assert_awaited()


@pytest.mark.asyncio
async def test_addrepo_already_exists():
    cog = DummyCog()
    cmd = ConfigCommands(cog)
    ctx = type("Ctx", (), {"send": AsyncMock()})()

    class FakeRepos(list):
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

    def repos_callable(): return FakeRepos(["exists/repo"])
    cog.config.allowed_repos = repos_callable

    await cmd.addrepo(ctx, "exists/repo")
    ctx.send.assert_awaited_with("⚠️ `exists/repo` is already in the allowed repositories")


@pytest.mark.asyncio
async def test_removerepo_removes_and_not_found():
    cog = DummyCog()
    cmd = ConfigCommands(cog)
    ctx = type("Ctx", (), {"send": AsyncMock()})()

    class FakeRepos(list):
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

    def repos_callable(): return FakeRepos(["old/repo"])
    cog.config.allowed_repos = repos_callable

    await cmd.removerepo(ctx, "old/repo")
    ctx.send.assert_awaited_with("✅ Removed `old/repo` from allowed repositories")

    await cmd.removerepo(ctx, "missing/repo")
    ctx.send.assert_awaited_with("⚠️ `missing/repo` is not in the allowed repositories")


@pytest.mark.asyncio
async def test_other_setters_and_showconfig():
    # prepare a DummyCog with many config entries
    class FullDummyCog(DummyCog):
        def __init__(self):
            super().__init__()
            for key in [
                "webhook_host", "webhook_port", "github_secret",
                "log_channel_id", "log_level", "issues_forum_id", "prs_forum_id",
                "issues_feed_chat_id", "prs_feed_chat_id", "updates_channel_id",
                "contributor_role_id", "github_token"
            ]:
                setattr(self.config, key, DummyConfigEntry())
            async def allowed_repos_callable():
                return []
            self.config.allowed_repos = lambda: allowed_repos_callable()
            self.handlers = AsyncMock()

    cog = FullDummyCog()
    cmd = ConfigCommands(cog)
    ctx = type("Ctx", (), {"send": AsyncMock(), "guild": None})()

    # exercise all simple setters
    await cmd.host(ctx, "1.2.3.4")
    await cmd.port(ctx, 1234)
    await cmd.secret(ctx, secret="sec")
    cog.config.github_secret.set.assert_awaited_with("sec")
    await cmd.secret(ctx, secret="")
    cog.config.github_secret.set.assert_awaited_with("")
    await cmd.secret(ctx, secret="none")
    cog.config.github_secret.set.assert_awaited_with("")
    await cmd.token(ctx, token="ghp_123")
    cog.config.github_token.set.assert_awaited_with("ghp_123")
    await cmd.token(ctx, token="clear")
    cog.config.github_token.set.assert_awaited_with("")
    await cmd.logchannel(ctx, channel_id="111")
    await cmd.logchannel(ctx, channel_id="none")
    await cmd.issuesforum(ctx, 222)
    await cmd.prsforum(ctx, 333)
    await cmd.issuesfeedchat(ctx, 444)
    await cmd.prsfeedchat(ctx, 555)
    await cmd.updates(ctx, 777)
    await cmd.contributorrole(ctx, 666)

    # showconfig
    async def fake_all():
        return {
            "webhook_host": "h",
            "webhook_port": 1,
            "github_secret": "s",
            "github_token": "",
            "allowed_repos": ["r"],
            "log_channel_id": 1,
            "issues_forum_id": 2,
            "prs_forum_id": 3,
            "issues_feed_chat_id": 4,
            "prs_feed_chat_id": 5,
            "updates_channel_id": 7,
            "contributor_role_id": 6,
        }
    cog.config.all = fake_all
    await cmd.showconfig(ctx)
    ctx.send.assert_awaited()

    # loglevel
    await cmd.loglevel(ctx, "invalid_level")
    ctx.send.assert_awaited()
    await cmd.loglevel(ctx, "errors")
    cog.config.log_level.set.assert_awaited_with("errors")
    await cmd.loglevel(ctx, "info")
    cog.config.log_level.set.assert_awaited_with("info")
    await cmd.loglevel(ctx, "verbose")
    cog.config.log_level.set.assert_awaited_with("all")

    # cancelreconcile when not running
    cog.handlers.is_reconciling = False
    await cmd.cancelreconcile(ctx)

    # cancelreconcile when running
    cog.handlers.is_reconciling = True
    await cmd.cancelreconcile(ctx)
    assert cog.handlers.reconcile_cancelled is True


@pytest.mark.asyncio
async def test_whitelist_commands_and_check():
    from GenHub.config_commands import is_genhub_admin

    cog = DummyCog()
    whitelisted_list = [135370180913004544]
    cog.config.whitelisted_users = AsyncMock(return_value=whitelisted_list)
    cog.config.whitelisted_users.set = AsyncMock()

    cmd = ConfigCommands(cog)

    # 1. Test is_genhub_admin check predicate
    check_predicate = is_genhub_admin().predicate

    ctx_owner = Mock()
    ctx_owner.author.id = 135370180913004544
    ctx_owner.cog = cmd
    assert await check_predicate(ctx_owner) is True

    ctx_other = Mock()
    ctx_other.author.id = 99999999
    ctx_other.cog = cmd
    ctx_other.bot.is_owner = AsyncMock(return_value=False)
    assert await check_predicate(ctx_other) is False

    # 2. Test whitelist add
    ctx_send = Mock()
    ctx_send.send = AsyncMock()
    user_to_add = Mock()
    user_to_add.id = 55555
    user_to_add.mention = "<@55555>"

    await cmd.whitelist_add(ctx_send, user_to_add)
    cog.config.whitelisted_users.set.assert_awaited()
    assert 55555 in cog.config.whitelisted_users.set.call_args[0][0]

    # 3. Test whitelist remove primary owner forbidden
    primary_user = Mock()
    primary_user.id = 135370180913004544
    await cmd.whitelist_remove(ctx_send, primary_user)
    assert "Cannot remove primary owner" in ctx_send.send.call_args[0][0]

    # 4. Test whitelist list
    ctx_list = Mock()
    ctx_list.send = AsyncMock()
    ctx_list.bot.get_user = Mock(return_value=None)
    await cmd.whitelist_list(ctx_list)
    ctx_list.send.assert_awaited()


