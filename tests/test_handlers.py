import pytest
from unittest.mock import AsyncMock, Mock, patch
from GenHub.handlers import GitHubEventHandlers


@pytest.mark.asyncio
async def test_handle_issue_opened_creates_message():
    cog = Mock()
    cog.config = Mock()
    cog.config.issues_forum_id = AsyncMock(return_value=123)
    cog.config.contributor_role_id = AsyncMock(return_value=None)

    mock_forum = Mock()
    mock_forum.available_tags = []
    mock_forum.create_tag = AsyncMock()

    mock_thread = AsyncMock()
    mock_forum.create_thread = AsyncMock(return_value=Mock(thread=mock_thread))

    cog.bot = Mock()
    cog.bot.get_channel = Mock(return_value=mock_forum)
    cog.thread_cache = {}

    handler = GitHubEventHandlers(cog)

    issue = {
        "number": 1,
        "title": "Test Issue",
        "html_url": "http://url",
        "user": {"login": "tester"},
        "state": "open",
    }
    data = {"action": "opened", "issue": issue}

    with patch("GenHub.handlers.send_message", new_callable=AsyncMock) as mock_send:
        await handler.handle_issue(data, "owner/repo")

        mock_send.assert_awaited()
        call = mock_send.await_args_list[0]
        args, kwargs = call
        # args[1] is the body, kwargs["prefix"] is the prefix
        assert "issue created" in kwargs["prefix"].lower() or "Test Issue" in args[1]


@pytest.mark.asyncio
async def test_handle_pr_closed_merged():
    cog = Mock()
    cog.config = Mock()
    cog.config.prs_forum_id = AsyncMock(return_value=123)
    cog.config.contributor_role_id = AsyncMock(return_value=None)

    mock_forum = Mock()
    mock_forum.available_tags = []
    mock_forum.create_tag = AsyncMock()

    mock_thread = AsyncMock()
    mock_forum.create_thread = AsyncMock(return_value=Mock(thread=mock_thread))

    cog.bot = Mock()
    cog.bot.get_channel = Mock(return_value=mock_forum)
    cog.thread_cache = {}

    handler = GitHubEventHandlers(cog)

    pr = {
        "number": 2,
        "title": "Test PR",
        "html_url": "http://url",
        "user": {"login": "tester"},
        "state": "closed",
        "merged": True,
    }
    data = {"action": "closed", "pull_request": pr}

    with patch("GenHub.handlers.send_message", new_callable=AsyncMock) as mock_send:
        await handler.handle_pull_request(data, "owner/repo")

        mock_send.assert_awaited()
        call = mock_send.await_args_list[0]
        args, kwargs = call
        assert "pr merged" in kwargs["prefix"].lower() or "Test PR" in args[1]
