import pytest
from unittest.mock import AsyncMock, Mock, patch
from GenHub.handlers import GitHubEventHandlers


@pytest.mark.asyncio
async def test_pull_request_review_flushes_message():
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

    data = {
        "action": "submitted",
        "pull_request": {
            "number": 42,
            "title": "Improve docs",
            "html_url": "http://url/pr/42",
        },
        "review": {
            "id": 101,
            "body": "Looks good to me!",
            "user": {"login": "reviewer"},
            "html_url": "http://url/review/101",
        },
    }

    with patch("GenHub.handlers.send_message", new_callable=AsyncMock) as mock_send:
        await handler.handle_pull_request_review(data, "owner/repo")

        task = handler.pending_reviews[("owner/repo", 42, 101)]["task"]
        await task

        mock_send.assert_awaited()
        call = mock_send.await_args_list[0]
        args, kwargs = call
        assert "review submitted" in kwargs["prefix"].lower() or "Looks good" in args[1]


@pytest.mark.asyncio
async def test_pull_request_review_comment_flushes_message():
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

    data = {
        "pull_request": {
            "number": 99,
            "title": "Refactor code",
            "html_url": "http://url/pr/99",
        },
        "comment": {
            "pull_request_review_id": 202,
            "body": "Please fix this line.",
            "user": {"login": "reviewer2"},
            "html_url": "http://url/comment/202",
        },
    }

    with patch("GenHub.handlers.send_message", new_callable=AsyncMock) as mock_send:
        await handler.handle_pull_request_review_comment(data, "owner/repo")

        task = handler.pending_reviews[("owner/repo", 99, 202)]["task"]
        await task

        mock_send.assert_awaited()
        call = mock_send.await_args_list[0]
        args, kwargs = call
        assert "review comment" in kwargs["prefix"].lower() or "Please fix" in args[1]
