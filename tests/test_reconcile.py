import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock, Mock
from GenHub.handlers import GitHubEventHandlers


@pytest.mark.asyncio
async def test_reconcile_forum_tags_updates_thread_tags():
    cog = Mock()
    cog.config = Mock()
    cog.config.issues_forum_id = AsyncMock(return_value=123)
    cog.config.prs_forum_id = AsyncMock(return_value=None)
    cog.config.github_token = AsyncMock(return_value="")
    cog.config.allowed_repos = AsyncMock(return_value=["owner/repo"])

    from tests.utils import make_fake_forum_with_threads

    mock_thread = AsyncMock()
    mock_thread.name = "「#1」Test Issue"
    mock_thread.applied_tags = []
    mock_thread.edit = AsyncMock()

    mock_forum = make_fake_forum_with_threads([mock_thread], name="Issues Forum")
    mock_forum.available_tags = []
    from types import SimpleNamespace
    mock_forum.create_tag = AsyncMock(side_effect=lambda name, moderated=False: SimpleNamespace(name=name))

    mock_msg = MagicMock()
    mock_msg.content = "https://github.com/owner/repo/issues/1"

    async def fake_history(limit, oldest_first):
        yield mock_msg

    mock_thread.history = fake_history
    cog.bot = Mock()
    cog.bot.get_channel = Mock(return_value=mock_forum)
    cog.bot.loop = asyncio.get_event_loop()
    cog.thread_cache = {}

    handler = GitHubEventHandlers(cog)

    fake_issue_data = {
        "number": 1,
        "title": "Test Issue",
        "html_url": "http://url/issue/1",
        "state": "open",
        "user": {"login": "tester"},
    }

    from tests.utils import make_fake_aiohttp_session

    async def fake_get_or_create_thread(*args, **kwargs):
        return mock_thread, False

    with patch("GenHub.handlers.aiohttp.ClientSession",
               return_value=make_fake_aiohttp_session([fake_issue_data])), \
         patch("GenHub.handlers.get_or_create_thread", side_effect=fake_get_or_create_thread):
        await handler.reconcile_forum_tags(ctx=None, repo_filter=None)

    mock_thread.edit.assert_awaited()
    args, kwargs = mock_thread.edit.await_args
    assert "applied_tags" in kwargs
    assert len(kwargs["applied_tags"]) > 0


@pytest.mark.asyncio
async def test_reconcile_forum_tags_exception(monkeypatch):
    cog = Mock()
    cog.config = Mock()
    cog.config.issues_forum_id = AsyncMock(return_value=1)
    cog.config.prs_forum_id = AsyncMock(return_value=None)
    cog.config.github_token = AsyncMock(return_value="")
    cog.config.allowed_repos = AsyncMock(return_value=["owner/repo"])
    forum = Mock()
    forum.threads = [Mock(name="bad", history=lambda **k: (_ for _ in () ))]
    async def fake_archived_threads(limit=None):
        yield Mock(name="bad2", history=lambda **k: (_ for _ in () ))
    forum.archived_threads = fake_archived_threads
    cog.bot = Mock()
    cog.bot.get_channel = Mock(return_value=forum)
    cog.bot.loop = asyncio.get_event_loop()
    cog.thread_cache = {}
    handler = GitHubEventHandlers(cog)

    # Patch aiohttp.ClientSession to raise on get
    class FakeSession:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*a): return False
        def get(self,*a,**k):
            raise RuntimeError("fail")
    monkeypatch.setattr("GenHub.handlers.aiohttp.ClientSession", lambda *args, **kwargs: FakeSession())

    await handler.reconcile_forum_tags()


@pytest.mark.asyncio
async def test_reconcile_creates_missing_thread():
    """Test that reconciliation creates a thread for missing issues and sends initial message."""
    cog = Mock()
    cog.config = Mock()
    cog.config.issues_forum_id = AsyncMock(return_value=123)
    cog.config.prs_forum_id = AsyncMock(return_value=None)
    cog.config.github_token = AsyncMock(return_value="")
    cog.config.allowed_repos = AsyncMock(return_value=["owner/repo"])
    cog.config.contributor_role_id = AsyncMock(return_value=None)

    from tests.utils import make_fake_forum_with_threads

    mock_thread = AsyncMock()
    mock_thread.name = "「#1」Test Issue"
    mock_thread.applied_tags = []
    mock_thread.edit = AsyncMock()
    mock_thread.guild = Mock()

    mock_forum = make_fake_forum_with_threads([], name="Issues Forum")  # Empty threads
    mock_forum.available_tags = []
    from types import SimpleNamespace
    mock_forum.create_tag = AsyncMock(side_effect=lambda name, moderated=False: SimpleNamespace(name=name))

    cog.bot = Mock()
    cog.bot.get_channel = Mock(return_value=mock_forum)
    cog.bot.loop = asyncio.get_event_loop()
    cog.thread_cache = {}

    handler = GitHubEventHandlers(cog)

    fake_issue_data = {
        "number": 1,
        "title": "Test Issue",
        "html_url": "http://url/issue/1",
        "state": "open",
        "user": {"login": "tester"},
    }

    from tests.utils import make_fake_aiohttp_session

    async def fake_get_or_create_thread(*args, **kwargs):
        return mock_thread, True  # Thread was created

    with patch("GenHub.handlers.aiohttp.ClientSession",
               return_value=make_fake_aiohttp_session([fake_issue_data])), \
         patch("GenHub.handlers.get_or_create_thread", side_effect=fake_get_or_create_thread), \
         patch("GenHub.handlers.send_message", new_callable=AsyncMock) as mock_send:
        await handler.reconcile_forum_tags(ctx=None, repo_filter=None)

    # Assert that send_message was called for the initial message
    mock_send.assert_awaited_once()
    args, kwargs = mock_send.await_args
    thread_arg, message = args
    assert thread_arg == mock_thread
    assert "🆕 Issue created" in message
    assert "Test Issue" in message
    assert "tester" in message
