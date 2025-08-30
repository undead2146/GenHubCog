import pytest
import asyncio
from unittest.mock import AsyncMock, patch, Mock
from GenHub.handlers import GitHubEventHandlers


@pytest.mark.asyncio
async def test_pull_request_review_flushes_message():
    """Test that a submitted PR review is flushed into the thread."""
    cog = Mock()
    cog.config = Mock()
    cog.config.prs_forum_id = AsyncMock(return_value=123)
    cog.config.contributor_role_id = AsyncMock(return_value=None)

    mock_thread = AsyncMock()
    mock_thread.edit = AsyncMock()
    mock_thread.guild = Mock()

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

    async def fake_get_or_create_thread(*a, **k): return mock_thread, False

    cog.bot = Mock()
    forum = Mock()
    forum.available_tags = []
    forum.create_tag = AsyncMock()
    cog.bot.get_channel = Mock(return_value=forum)

    with (
        patch("GenHub.handlers.send_message", new_callable=AsyncMock) as mock_send,
        patch("GenHub.handlers.get_or_create_thread", side_effect=fake_get_or_create_thread),
    ):
        await handler.handle_pull_request_review(data, "owner/repo")

        task = handler.pending_reviews[("owner/repo", 42, 101)]["task"]
        await task

        mock_send.assert_awaited()


@pytest.mark.asyncio
async def test_pull_request_review_comment_flushes_message():
    """Test that a PR review comment is flushed into the thread."""
    cog = Mock()
    cog.config = Mock()
    cog.config.prs_forum_id = AsyncMock(return_value=123)
    cog.config.contributor_role_id = AsyncMock(return_value=None)

    mock_thread = AsyncMock()
    mock_thread.edit = AsyncMock()
    mock_thread.guild = Mock()

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

    async def fake_get_or_create_thread(*a, **k): return mock_thread, False

    cog.bot = Mock()
    forum = Mock()
    forum.available_tags = []
    forum.create_tag = AsyncMock()
    cog.bot.get_channel = Mock(return_value=forum)

    with (
        patch("GenHub.handlers.send_message", new_callable=AsyncMock) as mock_send,
        patch("GenHub.handlers.get_or_create_thread", side_effect=fake_get_or_create_thread),
    ):
        await handler.handle_pull_request_review_comment(data, "owner/repo")

        task = handler.pending_reviews[("owner/repo", 99, 202)]["task"]
        await task

        mock_send.assert_awaited()
