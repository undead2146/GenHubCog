import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from GenHub.handlers import GitHubEventHandlers


@pytest.mark.asyncio
async def test_pull_request_review_flushes_message():
    """Test that a submitted PR review is flushed into the thread."""
    cog = AsyncMock()
    cog.config.prs_forum_id = AsyncMock(return_value=123)
    cog.config.contributor_role_id = AsyncMock(return_value=None)

    mock_forum = AsyncMock()
    mock_thread = AsyncMock()
    mock_forum.create_thread.return_value.thread = mock_thread
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

        # Wait for flush task to run
        await asyncio.sleep(2.5)

        mock_send.assert_awaited()
        args, kwargs = mock_send.await_args
        assert "Review submitted" in args[0] or "Looks good" in args[1]


@pytest.mark.asyncio
async def test_pull_request_review_comment_flushes_message():
    """Test that a PR review comment is flushed into the thread."""
    cog = AsyncMock()
    cog.config.prs_forum_id = AsyncMock(return_value=123)
    cog.config.contributor_role_id = AsyncMock(return_value=None)

    mock_forum = AsyncMock()
    mock_thread = AsyncMock()
    mock_forum.create_thread.return_value.thread = mock_thread
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

        # Wait for flush task to run
        await asyncio.sleep(2.5)

        mock_send.assert_awaited()
        args, kwargs = mock_send.await_args
        assert "review comment" in args[0].lower() or "Please fix" in args[1]
