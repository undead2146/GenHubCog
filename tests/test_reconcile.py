import pytest
from unittest.mock import AsyncMock, patch, MagicMock, Mock
from GenHub.handlers import GitHubEventHandlers


@pytest.mark.asyncio
async def test_reconcile_forum_tags_updates_thread_tags():
    cog = Mock()
    cog.config = Mock()
    cog.config.issues_forum_id = AsyncMock(return_value=123)
    cog.config.prs_forum_id = AsyncMock(return_value=None)
    cog.config.github_token = AsyncMock(return_value="")

    mock_forum = AsyncMock()
    mock_forum.name = "Issues Forum"
    mock_thread = AsyncMock()
    mock_thread.name = "「#1」Test Issue"
    mock_thread.applied_tags = []
    mock_forum.threads = [mock_thread]

    mock_msg = MagicMock()
    mock_msg.content = "https://github.com/owner/repo/issues/1"

    async def fake_history(limit, oldest_first):
        yield mock_msg

    mock_thread.history = fake_history
    cog.bot = Mock()
    cog.bot.get_channel = Mock(return_value=mock_forum)

    handler = GitHubEventHandlers(cog)

    fake_issue_data = {
        "number": 1,
        "title": "Test Issue",
        "html_url": "http://url/issue/1",
        "state": "open",
        "user": {"login": "tester"},
    }

    class FakeResponse:
        status = 200
        async def json(self): return fake_issue_data
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

    class FakeSession:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url, headers=None): return FakeResponse()

    with patch("GenHub.handlers.aiohttp.ClientSession", return_value=FakeSession()):
        await handler.reconcile_forum_tags(ctx=None, repo_filter=None)

    mock_thread.edit.assert_awaited()
    args, kwargs = mock_thread.edit.await_args
    assert "applied_tags" in kwargs
    assert len(kwargs["applied_tags"]) > 0
