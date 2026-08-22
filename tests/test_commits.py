import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
import discord
from GenHub.utils import (
    parse_commit_info,
    format_commit_headline,
    create_commits_embed,
    create_commits_link_view,
    format_commits_log_snippet,
    format_log_line,
)
from GenHub.handlers import GitHubEventHandlers


def test_parse_commit_info_api_format():
    commit_data = {
        "sha": "1a2b3c4d5e6f7g8h9i0j",
        "commit": {
            "author": {
                "name": "Jane Developer",
                "email": "jane@example.com",
                "date": "2026-08-22T12:00:00Z",
            },
            "message": "feat(core): add sound volume controls\n\nDetailed description here",
        },
        "html_url": "https://github.com/community-outpost/GenHub/commit/1a2b3c4d5e6f7g8h9i0j",
        "author": {
            "login": "janedev",
            "avatar_url": "https://avatars.githubusercontent.com/u/123",
        },
    }

    info = parse_commit_info(commit_data, repo="community-outpost/GenHub")
    assert info["sha"] == "1a2b3c4d5e6f7g8h9i0j"
    assert info["short_sha"] == "1a2b3c4"
    assert info["headline"] == "feat(core): add sound volume controls"
    assert info["author"] == "janedev"
    assert info["author_icon"] == "https://avatars.githubusercontent.com/u/123"
    assert info["url"] == "https://github.com/community-outpost/GenHub/commit/1a2b3c4d5e6f7g8h9i0j"
    assert info["created_at"] == "2026-08-22T12:00:00Z"


def test_parse_commit_info_webhook_push_format():
    commit_data = {
        "id": "9f8e7d6c5b4a3210",
        "message": "fix(build): resolve msbuild lock contention",
        "timestamp": "2026-08-22T13:00:00Z",
        "url": "https://github.com/community-outpost/GenHub/commit/9f8e7d6c5b4a3210",
        "author": {
            "name": "John Doe",
            "username": "johndoe",
            "email": "john@example.com",
        },
    }

    info = parse_commit_info(commit_data, repo="community-outpost/GenHub")
    assert info["sha"] == "9f8e7d6c5b4a3210"
    assert info["short_sha"] == "9f8e7d6"
    assert info["headline"] == "fix(build): resolve msbuild lock contention"
    assert info["author"] == "johndoe"
    assert info["created_at"] == "2026-08-22T13:00:00Z"


def test_parse_commit_info_fallback():
    commit_data = {"sha": "abcdef123456"}
    info = parse_commit_info(commit_data, repo="owner/repo")
    assert info["short_sha"] == "abcdef1"
    assert info["headline"] == "*No commit message*"
    assert info["author"] == "Unknown"
    assert info["url"] == "https://github.com/owner/repo/commit/abcdef123456"


def test_format_commit_headline():
    assert format_commit_headline("fix: bug") == "fix: bug"
    assert format_commit_headline("<b>feat:</b> test <code>code</code>") == "feat: test code"
    assert format_commit_headline("") == "*No commit message*"
    long_msg = "x" * 100
    assert len(format_commit_headline(long_msg, max_len=50)) <= 50
    assert format_commit_headline(long_msg, max_len=50).endswith("...")


def test_create_commits_embed_initial():
    commits = [
        {
            "sha": "11111112222222",
            "commit": {"message": "feat: first commit", "author": {"name": "Alice", "date": "2026-08-22T10:00:00Z"}},
            "html_url": "https://github.com/owner/repo/commit/11111112222222",
            "author": {"login": "alice"},
        },
        {
            "sha": "33333334444444",
            "commit": {"message": "fix: second commit", "author": {"name": "Bob", "date": "2026-08-22T11:00:00Z"}},
            "html_url": "https://github.com/owner/repo/commit/33333334444444",
            "author": {"login": "bob"},
        },
    ]

    embed = create_commits_embed(
        repo_full_name="owner/repo",
        pr_number=42,
        pr_title="Add new feature",
        pr_url="https://github.com/owner/repo/pull/42",
        commits=commits,
        sender="alice",
        is_initial=True,
    )

    assert embed.title == "📦 Initial Commits (2)"
    assert "1111111" in embed.description
    assert "feat: first commit" in embed.description
    assert "3333333" in embed.description
    assert "fix: second commit" in embed.description
    assert "GitHub Commits • repo #42" in embed.footer.text
    assert embed.color.value == 0x2B86D4
    assert embed.timestamp is not None


def test_create_commits_embed_synchronize_with_overflow():
    commits = []
    for i in range(15):
        commits.append({
            "sha": f"sha{i:04d}0000000000000",
            "commit": {"message": f"commit number {i}", "author": {"name": "Dev", "date": "2026-08-22T10:00:00Z"}},
            "html_url": f"https://github.com/owner/repo/commit/sha{i:04d}",
            "author": {"login": "dev"},
        })

    embed = create_commits_embed(
        repo_full_name="owner/repo",
        pr_number=10,
        pr_title="Big PR",
        pr_url="https://github.com/owner/repo/pull/10",
        commits=commits,
        sender="dev",
        compare_url="https://github.com/owner/repo/compare/before...after",
        is_initial=False,
    )

    assert embed.title == "🔄 15 New Commits Pushed"
    assert "5 more commits" in embed.description
    assert "https://github.com/owner/repo/compare/before...after" in embed.url


@pytest.mark.asyncio
async def test_create_commits_link_view():
    view1 = create_commits_link_view(compare_url="https://github.com/owner/repo/compare/a...b", count=3)
    assert view1 is not None
    assert len(view1.children) == 1
    assert "View 3 Commits on GitHub" in view1.children[0].label

    view2 = create_commits_link_view(pr_url="https://github.com/owner/repo/pull/1", count=1)
    assert view2 is not None
    assert "View Commit on GitHub" in view2.children[0].label

    view_none = create_commits_link_view(compare_url="", pr_url="")
    assert view_none is None


def test_format_commits_log_snippet():
    commits = [
        {"sha": "1234567890", "commit": {"message": "feat: volume slider"}},
        {"sha": "abcdef1234", "commit": {"message": "fix: null reference"}},
        {"sha": "9999888877", "commit": {"message": "test: add unit test"}},
    ]

    assert format_commits_log_snippet([]) == ""
    assert format_commits_log_snippet(commits[:1]) == '`1234567` "feat: volume slider"'
    assert format_commits_log_snippet(commits[:2]) == '2 commits (`1234567` "feat: volume slider", `abcdef1` "fix: null reference")'
    assert format_commits_log_snippet(commits) == '3 commits (`1234567` "feat: volume slider", `abcdef1` "fix: null reference" +1 more)'


def test_format_pr_chat_commit_line():
    from GenHub.utils import format_pr_chat_commit_line

    mock_thread = Mock(id=1420182734986543264)

    # 1. Single commit
    c1 = [{"sha": "1a2b3c4d5e", "commit": {"message": "feat: volume slider"}, "html_url": "https://github.com/owner/repo/commit/1a2b3c4d5e"}]
    line1 = format_pr_chat_commit_line(
        "owner/repo", 50, "Add volume", "https://github.com/owner/repo/pull/50",
        c1, "undead2146", thread=mock_thread
    )
    assert line1 == '🔄 **Commit Pushed:** [#50 Add volume](<https://github.com/owner/repo/pull/50>) • [`1a2b3c4`](<https://github.com/owner/repo/commit/1a2b3c4d5e>) "feat: volume slider" • Thread: <#1420182734986543264> • By **undead2146**'
    # Ensure no naked URLs that generate embed previews
    assert "(<https://" in line1
    assert "](https://" not in line1

    # 2. Two commits
    c2 = [
        {"sha": "1111111222", "commit": {"message": "feat: first"}, "html_url": "https://github.com/owner/repo/commit/1111111222"},
        {"sha": "3333333444", "commit": {"message": "fix: second"}, "html_url": "https://github.com/owner/repo/commit/3333333444"},
    ]
    line2 = format_pr_chat_commit_line(
        "owner/repo", 50, "Title", "https://github.com/owner/repo/pull/50",
        c2, "undead2146", thread=mock_thread, compare_url="https://github.com/owner/repo/compare/111...333"
    )
    assert line2 == '🔄 **Commits Pushed (2):** [#50 Title](<https://github.com/owner/repo/pull/50>) • [`1111111`](<https://github.com/owner/repo/commit/1111111222>), [`3333333`](<https://github.com/owner/repo/commit/3333333444>) • [Diff](<https://github.com/owner/repo/compare/111...333>) • Thread: <#1420182734986543264> • By **undead2146**'

    # 3. Three+ commits
    c3 = c2 + [{"sha": "5555555666", "commit": {"message": "test: third"}, "html_url": "https://github.com/owner/repo/commit/5555555666"}]
    line3 = format_pr_chat_commit_line(
        "owner/repo", 50, "Title", "https://github.com/owner/repo/pull/50",
        c3, "undead2146", thread=mock_thread, compare_url="https://github.com/owner/repo/compare/111...555"
    )
    assert line3 == '🔄 **Commits Pushed (3):** [#50 Title](<https://github.com/owner/repo/pull/50>) • [`1111111`](<https://github.com/owner/repo/commit/1111111222>)...[`5555555`](<https://github.com/owner/repo/commit/5555555666>) (3 commits) • [Diff](<https://github.com/owner/repo/compare/111...555>) • Thread: <#1420182734986543264> • By **undead2146**'

    # 4. Fallback with empty commits and after SHA
    line4 = format_pr_chat_commit_line(
        "owner/repo", 50, "Title", "https://github.com/owner/repo/pull/50",
        [], "undead2146", thread=mock_thread, after="abcdef1234567890"
    )
    assert line4 == '🔄 **Commits Pushed:** [#50 Title](<https://github.com/owner/repo/pull/50>) • [`abcdef1`](<https://github.com/owner/repo/commit/abcdef1234567890>) • Thread: <#1420182734986543264> • By **undead2146**'


@pytest.mark.asyncio
async def test_handle_pull_request_synchronize_with_commits():
    cog = Mock()
    cog.config = Mock()
    cog.config.prs_forum_id = AsyncMock(return_value=123)
    cog.config.prs_feed_chat_id = AsyncMock(return_value=456)
    cog.config.updates_channel_id = AsyncMock(return_value=None)
    cog.config.contributor_role_id = AsyncMock(return_value=None)
    cog.config.github_token = AsyncMock(return_value="fake_token")

    mock_thread = AsyncMock()
    mock_thread.id = 789
    mock_thread.edit = AsyncMock()
    mock_thread.applied_tags = []

    mock_feed_chat = AsyncMock()

    mock_forum = Mock()
    mock_forum.available_tags = []
    mock_forum.create_tag = AsyncMock()

    def fake_get_channel(ch_id):
        if ch_id == 123:
            return mock_forum
        if ch_id == 456:
            return mock_feed_chat
        return None

    cog.bot = Mock()
    cog.bot.get_channel = Mock(side_effect=fake_get_channel)
    cog.thread_cache = {}

    handler = GitHubEventHandlers(cog)

    pr = {
        "number": 50,
        "title": "Add volume controls",
        "html_url": "https://github.com/owner/repo/pull/50",
        "user": {"login": "developer"},
        "state": "open",
    }
    data = {
        "action": "synchronize",
        "pull_request": pr,
        "before": "1111111111111111111111111111111111111111",
        "after": "2222222222222222222222222222222222222222",
        "sender": {"login": "developer"},
    }

    mock_commits = [
        {
            "sha": "2222222222222222222222222222222222222222",
            "commit": {"message": "feat: sound slider implementation", "author": {"name": "Dev"}},
            "html_url": "https://github.com/owner/repo/commit/22222222",
            "author": {"login": "developer"},
        }
    ]

    async def fake_get_or_create_thread(*args, **kwargs):
        return mock_thread, False

    handler._fetch_compare_commits = AsyncMock(return_value=(mock_commits, "https://github.com/owner/repo/compare/11111111...22222222"))
    handler.log_info = AsyncMock()

    with patch("GenHub.handlers.send_message", new_callable=AsyncMock) as mock_send, \
         patch("GenHub.handlers.get_or_create_thread", side_effect=fake_get_or_create_thread):
        await handler.handle_pull_request(data, "owner/repo")

        # Verify send_message was called with commits embed
        assert mock_send.await_count >= 1
        call_args = mock_send.call_args_list[0]
        assert call_args[0][0] == mock_thread
        assert "embed" in call_args[1]
        embed = call_args[1]["embed"]
        assert "1 New Commit Pushed" in embed.title
        assert "feat: sound slider implementation" in embed.description

        # Verify log_info recorded the commits
        assert handler.log_info.await_count >= 1
        log_line = handler.log_info.call_args_list[0][0][0]
        assert "PR Commits Pushed" in log_line
        assert "feat: sound slider" in log_line

        # Verify feed chat received clean single-line message without embeds and with thread/commit links
        assert mock_feed_chat.send.await_count >= 1
        feed_msg = mock_feed_chat.send.call_args_list[0][0][0]
        assert "Commit Pushed" in feed_msg
        assert "Thread: <#789>" in feed_msg
        assert "2222222" in feed_msg
        assert "feat: sound slider" in feed_msg
        # Verify suppress_embeds was set
        kwargs = mock_feed_chat.send.call_args_list[0][1]
        assert kwargs.get("suppress_embeds") is True


@pytest.mark.asyncio
async def test_handle_pull_request_opened_with_commits():
    cog = Mock()
    cog.config = Mock()
    cog.config.prs_forum_id = AsyncMock(return_value=123)
    cog.config.prs_feed_chat_id = AsyncMock(return_value=456)
    cog.config.updates_channel_id = AsyncMock(return_value=None)
    cog.config.contributor_role_id = AsyncMock(return_value=None)
    cog.config.github_token = AsyncMock(return_value=None)

    mock_thread = AsyncMock()
    mock_thread.id = 789
    mock_thread.edit = AsyncMock()
    mock_thread.applied_tags = []

    mock_feed_chat = AsyncMock()
    mock_forum = Mock()
    mock_forum.available_tags = []
    mock_forum.create_tag = AsyncMock()

    def fake_get_channel(ch_id):
        if ch_id == 123:
            return mock_forum
        if ch_id == 456:
            return mock_feed_chat
        return None

    cog.bot = Mock()
    cog.bot.get_channel = Mock(side_effect=fake_get_channel)
    cog.thread_cache = {}

    handler = GitHubEventHandlers(cog)

    pr = {
        "number": 51,
        "title": "Initial feature commit",
        "html_url": "https://github.com/owner/repo/pull/51",
        "user": {"login": "author_user"},
        "state": "open",
    }
    data = {
        "action": "opened",
        "pull_request": pr,
        "sender": {"login": "author_user"},
    }

    mock_commits = [
        {
            "sha": "aaaaaaa1111111",
            "commit": {"message": "feat: initial commit", "author": {"name": "Author"}},
            "html_url": "https://github.com/owner/repo/commit/aaaaaaa",
            "author": {"login": "author_user"},
        }
    ]

    async def fake_get_or_create_thread(*args, **kwargs):
        return mock_thread, True

    handler._fetch_pr_commits = AsyncMock(return_value=mock_commits)
    handler.log_info = AsyncMock()

    with patch("GenHub.handlers.send_message", new_callable=AsyncMock) as mock_send, \
         patch("GenHub.handlers.get_or_create_thread", side_effect=fake_get_or_create_thread):
        await handler.handle_pull_request(data, "owner/repo")

        # Verify send_message was called with initial commits embed
        assert mock_send.await_count >= 1
        call_args = mock_send.call_args_list[0]
        assert call_args[0][0] == mock_thread
        assert "embed" in call_args[1]
        embed = call_args[1]["embed"]
        assert "Initial Commit" in embed.title

        # Verify log_info included commit snippet
        assert handler.log_info.await_count >= 1
        log_line = handler.log_info.call_args_list[0][0][0]
        assert "PR Opened" in log_line
        assert "feat: initial commit" in log_line

        # Verify feed chat message received clean single line with thread and commit link
        assert mock_feed_chat.send.await_count >= 1
        feed_msg = mock_feed_chat.send.call_args_list[0][0][0]
        assert "PR Opened" in feed_msg
        assert "Thread: <#789>" in feed_msg
        assert "aaaaaaa" in feed_msg
        assert "feat: initial commit" in feed_msg
        kwargs = mock_feed_chat.send.call_args_list[0][1]
        assert kwargs.get("suppress_embeds") is True


@pytest.mark.asyncio
async def test_handle_push_event():
    cog = Mock()
    cog.config = Mock()
    cog.config.log_channel_id = AsyncMock(return_value=None)
    cog.config.log_level = AsyncMock(return_value="info")
    cog.bot = Mock()

    handler = GitHubEventHandlers(cog)
    handler.log_info = AsyncMock()

    push_data = {
        "ref": "refs/heads/main",
        "commits": [
            {
                "id": "1234567890abcdef",
                "message": "fix: update readme",
                "author": {"name": "Maintainer", "username": "maintainer"},
                "url": "https://github.com/owner/repo/commit/1234567890abcdef",
            }
        ],
        "compare": "https://github.com/owner/repo/compare/prev...curr",
        "sender": {"login": "maintainer"},
    }

    await handler.handle_push(push_data, "owner/repo")
    assert handler.log_info.await_count == 1
    log_line = handler.log_info.call_args_list[0][0][0]
    assert "Push to `main`" in log_line
    assert "fix: update readme" in log_line


@pytest.mark.asyncio
async def test_handle_push_event_deleted_branch():
    cog = Mock()
    cog.config = Mock()
    cog.bot = Mock()

    handler = GitHubEventHandlers(cog)
    handler.log_info = AsyncMock()

    push_data = {
        "ref": "refs/heads/feature-old",
        "deleted": True,
        "sender": {"login": "maintainer"},
    }

    await handler.handle_push(push_data, "owner/repo")
    assert handler.log_info.await_count == 1
    log_line = handler.log_info.call_args_list[0][0][0]
    assert "Branch Deleted `feature-old`" in log_line
