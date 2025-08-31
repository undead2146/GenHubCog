import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
from GenHub.handlers import GitHubEventHandlers


@pytest.mark.asyncio
async def test_handle_issue_opened_creates_message():
    cog = Mock()
    cog.config = Mock()
    cog.config.issues_forum_id = AsyncMock(return_value=123)
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

    issue = {
        "number": 1,
        "title": "Test Issue",
        "html_url": "http://url",
        "user": {"login": "tester"},
        "state": "open",
    }
    data = {"action": "opened", "issue": issue}

    async def fake_get_or_create_thread(*args, **kwargs):
        # Check if initial_content was passed for opened action
        assert len(args) >= 9  # Should have 9 arguments
        initial_content = args[8] if len(args) > 8 else None  # initial_content is the 9th argument
        assert initial_content is not None
        assert "🆕 Issue created" in initial_content
        assert "Test Issue" in initial_content
        return mock_thread, False

    with patch("GenHub.handlers.send_message", new_callable=AsyncMock) as mock_send, \
         patch("GenHub.handlers.get_or_create_thread", side_effect=fake_get_or_create_thread):
        await handler.handle_issue(data, "owner/repo")

        # For opened action, send_message should NOT be called since initial content is used
        mock_send.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_pr_closed_merged():
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

    pr = {
        "number": 2,
        "title": "Test PR",
        "html_url": "http://url",
        "user": {"login": "tester"},
        "state": "closed",
        "merged": True,
    }
    data = {"action": "closed", "pull_request": pr}

    async def fake_get_or_create_thread(*args, **kwargs):
        return mock_thread, False

    with patch("GenHub.handlers.send_message", new_callable=AsyncMock) as mock_send, \
         patch("GenHub.handlers.get_or_create_thread", side_effect=fake_get_or_create_thread):
        await handler.handle_pull_request(data, "owner/repo")

        mock_send.assert_awaited()
        args, kwargs = mock_send.await_args
        body = args[1]
        prefix = kwargs.get("prefix", "")
        assert "pr merged" in prefix.lower() or "Test PR" in body


@pytest.mark.asyncio
async def test_process_payload_repo_not_allowed():
    cog = Mock()
    cog.config = Mock()
    cog.config.allowed_repos = AsyncMock(return_value=["other/repo"])
    handler = GitHubEventHandlers(cog)

    req = Mock()
    req.headers = {"X-GitHub-Event": "issues"}
    data = {"repository": {"full_name": "not/allowed"}}
    # should just return without error
    await handler.process_payload(req, data)


@pytest.mark.asyncio
async def test_handle_issue_closed_and_reopened_and_assigned():
    cog = Mock()
    cog.config = Mock()
    cog.config.issues_forum_id = AsyncMock(return_value=123)
    cog.config.contributor_role_id = AsyncMock(return_value=None)

    mock_thread = AsyncMock()
    mock_thread.guild = Mock()
    mock_forum = Mock()
    mock_forum.available_tags = []
    mock_forum.create_tag = AsyncMock()
    cog.bot = Mock()
    cog.bot.get_channel = Mock(return_value=mock_forum)

    async def fake_get_or_create_thread(*a, **k):
        return mock_thread, False

    with patch("GenHub.handlers.get_or_create_thread", side_effect=fake_get_or_create_thread), \
         patch("GenHub.handlers.send_message", new_callable=AsyncMock) as mock_send, \
         patch("GenHub.handlers.update_status_tag", new_callable=AsyncMock):
        handler = GitHubEventHandlers(cog)
        issue = {"number": 1, "title": "T", "html_url": "u", "user": {"login": "a"}, "state": "open"}
        for action in ["closed", "reopened", "assigned"]:
            data = {"action": action, "issue": issue}
            await handler.handle_issue(data, "owner/repo")
        assert mock_send.await_count >= 2


@pytest.mark.asyncio
async def test_handle_pull_request_closed_not_merged_and_reopened():
    cog = Mock()
    cog.config = Mock()
    cog.config.prs_forum_id = AsyncMock(return_value=123)
    cog.config.contributor_role_id = AsyncMock(return_value=None)

    mock_thread = AsyncMock()
    mock_thread.guild = Mock()
    mock_forum = Mock()
    mock_forum.available_tags = []
    mock_forum.create_tag = AsyncMock()
    cog.bot = Mock()
    cog.bot.get_channel = Mock(return_value=mock_forum)

    async def fake_get_or_create_thread(*a, **k):
        return mock_thread, False

    with patch("GenHub.handlers.get_or_create_thread", side_effect=fake_get_or_create_thread), \
         patch("GenHub.handlers.send_message", new_callable=AsyncMock) as mock_send, \
         patch("GenHub.handlers.update_status_tag", new_callable=AsyncMock):
        handler = GitHubEventHandlers(cog)
        pr = {"number": 1, "title": "T", "html_url": "u", "user": {"login": "a"}}
        for action in ["closed", "reopened", "assigned"]:
            data = {"action": action, "pull_request": pr}
            await handler.handle_pull_request(data, "owner/repo")
        assert mock_send.await_count >= 2


@pytest.mark.asyncio
async def test_handle_pr_closed_not_merged():
    cog = Mock()
    cog.config = Mock()
    cog.config.prs_forum_id = AsyncMock(return_value=123)
    cog.config.contributor_role_id = AsyncMock(return_value=None)

    mock_thread = AsyncMock()
    mock_thread.guild = Mock()
    mock_forum = Mock()
    mock_forum.available_tags = []
    mock_forum.create_tag = AsyncMock()
    cog.bot = Mock()
    cog.bot.get_channel = Mock(return_value=mock_forum)

    async def fake_get_or_create_thread(*a, **k):
        return mock_thread, False
    with patch("GenHub.handlers.get_or_create_thread", side_effect=fake_get_or_create_thread), \
         patch("GenHub.handlers.send_message", new_callable=AsyncMock) as mock_send, \
         patch("GenHub.handlers.update_status_tag", new_callable=AsyncMock):
        handler = GitHubEventHandlers(cog)
        pr = {"number": 3, "title": "T", "html_url": "u", "user": {"login": "a"}, "state": "closed", "merged": False}
        data = {"action": "closed", "pull_request": pr}
        await handler.handle_pull_request(data, "owner/repo")
        assert mock_send.await_count >= 1


@pytest.mark.asyncio
async def test_slash_commands_config_command_calls_update():
    from GenHub.slash_commands import SlashCommands

    class DummyConfigEntry:
        def __init__(self):
            self.set = AsyncMock()

    class DummyCog:
        def __init__(self):
            self.config = type("Config", (), {})()
            self.config.webhook_host = DummyConfigEntry()
            self.config.webhook_port = DummyConfigEntry()

    sc = SlashCommands(DummyCog())
    inter = Mock()
    inter.response = Mock()
    inter.response.send_message = AsyncMock()
    await sc.config_command(inter, webhook_host="h", webhook_port=1)
    inter.response.send_message.assert_awaited()


@pytest.mark.asyncio
async def test_process_payload_skips_and_calls_handler():
    cog = Mock()
    cog.config = Mock()
    cog.config.allowed_repos = AsyncMock(return_value=["owner/repo"])
    handler = GitHubEventHandlers(cog)

    req = Mock()
    req.headers = {"X-GitHub-Event": "issues"}
    data = {"repository": {"full_name": "owner/repo"}, "issue": {"number":1,"title":"t","html_url":"u","user":{"login":"a"}}, "action":"opened"}

    # Patch handle_issue
    handler.handle_issue = AsyncMock()
    await handler.process_payload(req, data)
    handler.handle_issue.assert_awaited()


@pytest.mark.asyncio
async def test_handle_issue_no_thread_and_empty_body():
    cog = Mock()
    cog.config = Mock()
    cog.config.issues_forum_id = AsyncMock(return_value=123)
    cog.config.contributor_role_id = AsyncMock(return_value=None)
    cog.bot = Mock()
    forum = Mock()
    forum.available_tags = []
    forum.create_tag = AsyncMock()
    forum.create_thread = AsyncMock()
    forum.threads = []
    async def fake_archived_threads(limit=None):
        if False:
            yield None
    forum.archived_threads = fake_archived_threads
    cog.bot.get_channel = Mock(return_value=forum)
    cog.thread_cache = {}
    handler = GitHubEventHandlers(cog)

    # Patch get_or_create_thread to return None
    async def fake_get_or_create_thread(*a, **k):
        return None, False
    from GenHub import utils as _utils
    _utils.get_or_create_thread = fake_get_or_create_thread

    data = {"action":"opened","issue":{"number":1,"title":"t","html_url":"u","user":{"login":"a"}, "state":"open"}}
    await handler.handle_issue(data, "owner/repo")  # should just return


@pytest.mark.asyncio
async def test_handle_issue_comment_empty_body_skips(monkeypatch):
    cog = Mock()
    cog.config = Mock()
    cog.config.issues_forum_id = AsyncMock(return_value=123)
    cog.config.contributor_role_id = AsyncMock(return_value=None)
    cog.bot = Mock()
    forum = Mock()
    forum.available_tags = []
    forum.create_tag = AsyncMock()
    forum.create_thread = AsyncMock()
    forum.threads = []
    async def fake_archived_threads(limit=None):
        if False:
            yield None
    forum.archived_threads = fake_archived_threads
    cog.bot.get_channel = Mock(return_value=forum)
    cog.thread_cache = {}
    handler = GitHubEventHandlers(cog)

    async def fake_get_or_create_thread(*a, **k):
        return Mock(), False
    from GenHub import utils as _utils
    monkeypatch.setattr(_utils, "get_or_create_thread", fake_get_or_create_thread)

    data = {"issue":{"number":1,"title":"t","html_url":"u","user":{"login":"a"}, "state":"open"}, "comment":{"body":"","user":{"login":"b"},"html_url":"c"}}
    await handler.handle_issue_comment(data, "owner/repo")


@pytest.mark.asyncio
async def test_handle_issue_comment_sends_message():
    cog = Mock()
    cog.config = Mock()
    cog.config.issues_forum_id = AsyncMock(return_value=123)
    cog.config.prs_forum_id = AsyncMock(return_value=456)
    cog.config.contributor_role_id = AsyncMock(return_value=None)

    mock_thread = AsyncMock()
    mock_thread.guild = Mock()
    mock_forum = Mock()
    mock_forum.available_tags = []
    mock_forum.create_tag = AsyncMock()
    cog.bot = Mock()
    cog.bot.get_channel = Mock(return_value=mock_forum)
    cog.thread_cache = {}

    async def fake_get_or_create_thread(*a, **k):
        return mock_thread, False
    with patch("GenHub.handlers.get_or_create_thread", side_effect=fake_get_or_create_thread), \
         patch("GenHub.handlers.send_message", new_callable=AsyncMock) as mock_send:
        handler = GitHubEventHandlers(cog)
        issue = {"number": 1, "title": "T", "html_url": "u", "user": {"login": "a"}, "state": "open"}
        comment = {"body": "hi", "user": {"login": "me"}, "html_url": "c"}
        data = {"issue": issue, "comment": comment}
        await handler.handle_issue_comment(data, "owner/repo")
        mock_send.assert_awaited()


@pytest.mark.asyncio
async def test_handle_pull_request_review_non_submitted():
    """Should return early if action is not 'submitted'."""
    cog = Mock()
    handler = GitHubEventHandlers(cog)
    data = {"action": "edited", "pull_request": {"number": 1}, "review": {"id": 1}}
    # Should not raise, just return
    await handler.handle_pull_request_review(data, "owner/repo")


@pytest.mark.asyncio
async def test_schedule_flush_no_pr_data(monkeypatch):
    """Flush should skip if no pull_request or issue in data."""
    cog = Mock()
    cog.config = Mock()
    cog.config.prs_forum_id = AsyncMock(return_value=123)
    cog.config.contributor_role_id = AsyncMock(return_value=None)
    cog.bot = Mock()
    forum = Mock()
    forum.available_tags = []
    forum.create_tag = AsyncMock()
    cog.bot.get_channel = Mock(return_value=forum)
    handler = GitHubEventHandlers(cog)

    data = {"review": {"id": 1, "user": {"login": "a"}, "html_url": "u"}}
    key = ("owner/repo", 1, 1)
    handler.pending_reviews[key] = {
        "author": "a",
        "url": "u",
        "body": None,
        "comments": []
    }
    await handler._schedule_flush("owner/repo", 1, 1, data)
    handler.pending_reviews[key]["task"].cancel()


@pytest.mark.asyncio
async def test_reconcile_repo_filter_and_bad_status(monkeypatch):
    """Should skip threads if repo_filter mismatches or resp.status != 200."""
    cog = Mock()
    cog.config = Mock()
    cog.config.issues_forum_id = AsyncMock(return_value=1)
    cog.config.prs_forum_id = AsyncMock(return_value=None)
    cog.config.github_token = AsyncMock(return_value="")
    cog.config.allowed_repos = AsyncMock(return_value=["owner/repo"])

    # Fake forum with one thread
    thread = AsyncMock()
    thread.name = "[GH] [#1] Test"
    msg = Mock()
    msg.content = "https://github.com/owner/repo/issues/1"
    async def fake_history(limit, oldest_first):
        yield msg
    thread.history = fake_history
    forum = Mock()
    forum.threads = [thread]
    async def fake_archived_threads(limit=None):
        if False:
            yield None
        return
    forum.archived_threads = fake_archived_threads
    cog.bot = Mock()
    cog.bot.get_channel = Mock(return_value=forum)
    cog.bot.loop = asyncio.get_event_loop()
    cog.thread_cache = {}

    handler = GitHubEventHandlers(cog)

    # Patch aiohttp.ClientSession to return bad status
    class FakeResp:
        status = 404
        async def __aenter__(self): return self
        async def __aexit__(self,*a): return False
        async def json(self): return {}
    class FakeSession:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*a): return False
        def get(self,*a,**k): return FakeResp()
    monkeypatch.setattr("GenHub.handlers.aiohttp.ClientSession", lambda *args, **kwargs: FakeSession())

    await handler.reconcile_forum_tags(repo_filter="owner/repo")
    await handler.reconcile_forum_tags(repo_filter=None)
