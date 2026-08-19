import pytest
from unittest.mock import AsyncMock, Mock
from GenHub import utils
from GenHub.utils import send_message, format_message

@pytest.mark.asyncio
async def test_send_message_splits_long_text():
    channel = AsyncMock()
    long_text = "x" * 5000
    await send_message(channel, long_text, prefix="PREFIX: ")
    assert channel.send.await_count > 1

def test_format_message_contains_fields():
    msg = format_message("🔥", "Test", "Title", "http://url", "author", "@role")
    assert "🔥" in msg
    assert "Title" in msg
    assert "author" in msg


def test_is_bot_author():
    from GenHub.utils import is_bot_author
    assert is_bot_author("coderabbitai[bot]") is True
    assert is_bot_author("deepsource-autofix[bot]") is True
    assert is_bot_author("dependabot[bot]") is True
    assert is_bot_author("random_user", {"type": "Bot"}) is True
    assert is_bot_author("human_developer", {"type": "User"}) is False
    assert is_bot_author("", {}) is False


def test_clean_github_markdown():
    from GenHub.utils import clean_github_markdown
    raw = "<!-- comment --><b>Bold text</b> and <details><summary><b>Summary Title</b></summary>Details content</details>"
    cleaned = clean_github_markdown(raw)
    assert "<!-- comment -->" not in cleaned
    assert "**Bold text**" in cleaned
    assert "**Summary Title:**" in cleaned
    assert "<details>" not in cleaned

    sample = """
    <sub>Check the box below or use the [coderabbitai](coderabbitai) plan command.</sub>
    [ ] Create Plan
    community-outpost/GenHub#267 - feat: test
    Fixes #256 as well
    """
    clean_sample = clean_github_markdown(sample, repo="community-outpost/GenHub")
    assert "<sub>" not in clean_sample
    assert "*Check the box below" in clean_sample
    assert "`coderabbitai`" in clean_sample
    assert "⬜ Create Plan" in clean_sample
    assert "[community-outpost/GenHub#267](https://github.com/community-outpost/GenHub/issues/267)" in clean_sample
    assert "[#256](https://github.com/community-outpost/GenHub/issues/256)" in clean_sample


def test_clean_github_markdown_deepsource():
    from GenHub.utils import clean_github_markdown
    raw = """
    <h2><picture><source srcset="...grade_a.svg"/><img src="...grade_a.svg"/></picture><span>DeepSource Code Review</span></h2>
    > [!IMPORTANT]
    > Some issues found as part of this review are outside of the diff.
    <h3>PR Report Card</h3>
    <table>
    <tr>
    <td><strong>Overall Grade</strong>&nbsp;&nbsp;<a href="https://deepsource.com/run/123"><picture><img src="...grade_a.svg"/></picture></a><br/><br/><strong>Focus Area:</strong> Hygiene</td>
    <td><strong>Security</strong>&nbsp;&nbsp;<img src="...grade_a.svg"/></td>
    </tr>
    </table>
    <h3>Code Review Summary</h3>
    <table>
    <tr><th>Analyzer</th><th>Status</th><th>Details</th></tr>
    <tr><td><strong>C#</strong></td><td><img src="...status_failed.svg"/></td><td><a href="https://deepsource.com/cs">Review</a> ↗</td></tr>
    <tr><td><strong>JavaScript</strong></td><td><img src="...status_passed.svg"/></td><td><a href="https://deepsource.com/js">Review</a> ↗</td></tr>
    </table>
    """
    cleaned = clean_github_markdown(raw, repo="community-outpost/GenHub")
    assert "### [A] DeepSource Code Review" in cleaned or "[A]" in cleaned
    assert "> 🟣 **Important:**" in cleaned
    assert "• **Overall Grade**: [A](https://deepsource.com/run/123)" in cleaned or "[A](https://deepsource.com/run/123)" in cleaned
    assert "• **Security**: [A]" in cleaned
    assert "❌ FAILED" in cleaned
    assert "✅ PASSED" in cleaned
    assert "• **C#** — ❌ FAILED — [Review](https://deepsource.com/cs) ↗" in cleaned


def test_clean_github_markdown_qodo():
    from GenHub.utils import clean_github_markdown
    raw = """
    <details>
    <summary> 1. <s>Community provider ID mismatches</s> <code>✓ Resolved</code> <code>🐞 Bug</code></summary>
    > <details open>
    ><summary>Description</summary>
    ><pre>The bundled Community Outpost definition is keyed as <b>community-outpost</b>.</pre>
    ></details>
    > <details>
    ><summary>Relevance</summary>
    > `••• Strong`
    > <code>[PR #198](https://github.com/community-outpost/GenHub/pull/198)</code>
    ></details>
    </details>
    """
    cleaned = clean_github_markdown(raw, repo="community-outpost/GenHub")
    assert "**1. ~~Community provider ID mismatches~~ `✓ Resolved` `🐞 Bug`:**" in cleaned or "Community provider ID mismatches" in cleaned
    assert "> **Description:**" in cleaned
    assert "The bundled Community Outpost definition is keyed as **community-outpost**." in cleaned
    assert "[PR #198](https://github.com/community-outpost/GenHub/pull/198)" in cleaned
    # Ensure no nested broken markdown links
    assert "[PR [#198]" not in cleaned


def test_clean_github_markdown_tables_and_callouts():
    from GenHub.utils import clean_github_markdown
    raw = """
    | Severity | Count |
    |---|---|
    | CRITICAL | 0 |
    | SUGGESTION | 11 |

    > [!WARNING]
    > Review limit reached!

    > [!NOTE]
    > This is a note.
    """
    cleaned = clean_github_markdown(raw)
    assert "• **CRITICAL**: 0" in cleaned
    assert "• **SUGGESTION**: 11" in cleaned
    assert "> ⚠️ **Warning:**" in cleaned
    assert "> Review limit reached!" in cleaned
    assert "> 📝 **Note:**" in cleaned
    assert "> This is a note." in cleaned


def test_create_comment_embed():
    from GenHub.utils import create_comment_embed
    embed = create_comment_embed(
        author="coderabbitai[bot]",
        body="<!-- hide -->**Review** body with #100",
        url="https://github.com/test/1",
        is_bot=True,
        is_review=True,
        extra_count=5,
        created_at="2026-08-19T01:15:00Z",
        repo="community-outpost/GenHub",
    )
    assert "Review" in embed.description
    assert "coderabbitai[bot]" in embed.author.name
    assert "5" in embed.footer.text
    assert embed.timestamp is not None
    assert "[#100](https://github.com/community-outpost/GenHub/issues/100)" in embed.description




@pytest.mark.asyncio
async def test_send_message_prefix_too_long_and_split():
    channel = AsyncMock()
    prefix = "x" * 2100
    content = "y" * 10
    await send_message(channel, content, prefix=prefix)
    channel.send.assert_awaited()


@pytest.mark.asyncio
async def test_get_role_mention_none_and_missing():
    from GenHub import utils
    guild = Mock()
    guild.get_role = Mock(return_value=None)
    result = utils.get_role_mention(guild, None)
    assert result == ""
    result = utils.get_role_mention(guild, 123)
    assert result == ""


@pytest.mark.asyncio
async def test_get_or_create_tag_exception():
    from GenHub import utils
    forum = Mock()
    forum.available_tags = []
    forum.create_tag = AsyncMock(side_effect=Exception("fail"))
    tag = await utils.get_or_create_tag(forum, "X")
    assert tag is None


@pytest.mark.asyncio
async def test_update_status_tag_no_new_tag(monkeypatch):
    from GenHub import utils
    thread = AsyncMock()
    thread.parent = Mock()
    async def fake_get_or_create_tag(forum, name): return None
    monkeypatch.setattr(utils, "get_or_create_tag", fake_get_or_create_tag)
    await utils.update_status_tag(thread, "Open")
    # should not call edit
    thread.edit.assert_not_awaited()


@pytest.mark.asyncio
async def test_find_thread_archived_found():
    from GenHub import utils
    forum = AsyncMock()
    tag = Mock()
    tag.name = "repo"
    forum.available_tags = [tag]
    t = Mock()
    t.name = "[GH] [#1] Test"
    t.applied_tags = [tag]
    async def fake_archived_threads(limit=None):
        yield t
    forum.archived_threads = fake_archived_threads
    forum.threads = []  # <-- Add this to make it iterable
    bot = Mock()
    bot.get_channel = Mock(return_value=forum)
    result = await utils.find_thread(bot, 1, "owner/repo", 1, {})
    assert result == t


@pytest.mark.asyncio
async def test_send_message_splits_remainder():
    channel = AsyncMock()
    prefix = "PRE:"
    content = "x" * 2100
    await utils.send_message(channel, content, prefix=prefix)
    assert channel.send.await_count > 1


@pytest.mark.asyncio
async def test_utils_send_message_edge_cases():
    channel = AsyncMock()
    # prefix longer than 2000
    await utils.send_message(channel, "short", prefix="x"*2100)
    # content exactly 2000
    await utils.send_message(channel, "y"*2000, prefix="PRE:")


@pytest.mark.asyncio
async def test_utils_get_or_create_thread_forum_none():
    bot = Mock()
    bot.get_channel = Mock(return_value=None)
    res = await utils.get_or_create_thread(bot, 1, "owner/repo", 1, "t", "u", [], {})
    assert res == (None, False)


@pytest.mark.asyncio
async def test_utils_find_thread_forum_none():
    bot = Mock()
    bot.get_channel = Mock(return_value=None)
    res = await utils.find_thread(bot, 1, "owner/repo", 1, {})
    assert res is None
