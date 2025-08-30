import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
from GenHub.handlers import GitHubEventHandlers


@pytest.mark.asyncio
async def test_pull_request_review_flushes_message():
    cog = Mock()
    cog.config = Mock()
    cog.config.prs_forum_id = AsyncMock(return_value=123)
    cog.config.contributor_role_id = AsyncMock(return_value=None)

    from tests.utils import make_fake_forum_with_threads

    mock_thread = AsyncMock()
    mock_thread.edit = AsyncMock()
    mock_thread.name = "thread"
    mock_thread.applied_tags = []

    mock_forum = make_fake_forum_with_threads([mock_thread])
    mock_forum.available_tags = []
    mock_forum.create_tag = AsyncMock()
    mock_forum.create_thread = AsyncMock(return_value=Mock(thread=mock_thread))

    cog.bot = Mock()
    cog.bot.get_channel = Mock(return_value=mock_forum)
    cog.bot.loop = asyncio.get_event_loop()
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

    async def fake_get_or_create_thread(*args, **kwargs):
        return mock_thread, False

    with patch("GenHub.handlers.send_message", new_callable=AsyncMock) as mock_send, \
         patch("GenHub.handlers.get_or_create_thread", side_effect=fake_get_or_create_thread):
        await handler.handle_pull_request_review(data, "owner/repo")

        task = handler.pending_reviews[("owner/repo", 42, 101)]["task"]
        await task

        mock_send.assert_awaited()
        args, kwargs = mock_send.await_args
        body = args[1]
        prefix = kwargs.get("prefix", "")
        assert "review submitted" in prefix.lower() or "Looks good" in body


@pytest.mark.asyncio
async def test_pull_request_review_comment_flushes_message():
    cog = Mock()
    cog.config = Mock()
    cog.config.prs_forum_id = AsyncMock(return_value=123)
    cog.config.contributor_role_id = AsyncMock(return_value=None)

    from tests.utils import make_fake_forum_with_threads

    mock_thread = AsyncMock()
    mock_thread.edit = AsyncMock()
    mock_thread.name = "thread"
    mock_thread.applied_tags = []

    mock_forum = make_fake_forum_with_threads([mock_thread])
    mock_forum.available_tags = []
    mock_forum.create_tag = AsyncMock()
    mock_forum.create_thread = AsyncMock(return_value=Mock(thread=mock_thread))

    cog.bot = Mock()
    cog.bot.get_channel = Mock(return_value=mock_forum)
    cog.bot.loop = asyncio.get_event_loop()
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

    async def fake_get_or_create_thread(*args, **kwargs):
        return mock_thread, False

    with patch("GenHub.handlers.send_message", new_callable=AsyncMock) as mock_send, \
         patch("GenHub.handlers.get_or_create_thread", side_effect=fake_get_or_create_thread):
        await handler.handle_pull_request_review_comment(data, "owner/repo")

        task = handler.pending_reviews[("owner/repo", 99, 202)]["task"]
        await task

        mock_send.assert_awaited()
        args, kwargs = mock_send.await_args
        body = args[1]
        prefix = kwargs.get("prefix", "")
        assert "review comment" in prefix.lower() or "Please fix" in body
