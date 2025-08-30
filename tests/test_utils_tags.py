import pytest
from unittest.mock import AsyncMock, Mock
from types import SimpleNamespace

from GenHub import utils

class FakeThread:
    def __init__(self, id):
        self.id = id

@pytest.mark.asyncio
async def test_get_or_create_tag_existing():
    tag = SimpleNamespace(name="Open")
    forum = Mock()
    forum.available_tags = [tag]
    forum.create_tag = AsyncMock()

    got = await utils.get_or_create_tag(forum, "Open")
    assert got is tag


@pytest.mark.asyncio
async def test_get_or_create_tag_create():
    forum = Mock()
    forum.available_tags = []
    new_tag = SimpleNamespace(name="NewTag")
    forum.create_tag = AsyncMock(return_value=new_tag)

    got = await utils.get_or_create_tag(forum, "NewTag")
    assert got is new_tag


@pytest.mark.asyncio
async def test_get_issue_tags_open_and_assignee():
    forum = Mock()
    forum.available_tags = []
    forum.create_tag = AsyncMock(side_effect=lambda name, moderated=False: SimpleNamespace(name=name))
    issue = {"state": "open", "assignees": [1]}

    tags = await utils.get_issue_tags(forum, issue)
    names = [t.name.lower() for t in tags]
    assert "open" in names
    assert "active" in names


@pytest.mark.asyncio
async def test_get_pr_tags_merged_closed_open():
    forum = Mock()
    forum.available_tags = []
    forum.create_tag = AsyncMock(side_effect=lambda name, moderated=False: SimpleNamespace(name=name))
    pr = {"state": "closed", "merged": True}
    tags = await utils.get_pr_tags(forum, pr)
    assert any(t.name.lower() == "merged" for t in tags)


@pytest.mark.asyncio
async def test_update_status_tag_replaces():
    mock_tag_repo = SimpleNamespace(name="repo")
    forum = Mock()
    forum.available_tags = [mock_tag_repo]
    forum.create_tag = AsyncMock(side_effect=lambda name, moderated=False: SimpleNamespace(name=name))

    thread = AsyncMock()
    thread.parent = forum
    thread.applied_tags = [SimpleNamespace(name="repo"), SimpleNamespace(name="Open")]
    thread.edit = AsyncMock()

    await utils.update_status_tag(thread, "Closed")
    thread.edit.assert_awaited()


@pytest.mark.asyncio
async def test_find_thread_active_and_archived():
    bot = Mock()
    forum = Mock()
    # ensure available_tags is iterable and create_tag returns real tag objects
    forum.available_tags = []
    forum.create_tag = AsyncMock(side_effect=lambda name, moderated=False: SimpleNamespace(name=name))

    # Active thread
    t = SimpleNamespace(name="「#5」Title", applied_tags=[SimpleNamespace(name="repo")], id=123)
    forum.threads = [t]

    # async generator for archived threads
    async def fake_archived_threads(limit=None):
        yield SimpleNamespace(name="「#6」Title", applied_tags=[SimpleNamespace(name="repo")], id=456)

    forum.archived_threads = fake_archived_threads
    bot.get_channel = Mock(return_value=forum)

    thread_cache = {}

    # Should find active thread
    res = await utils.find_thread(bot, 1, "owner/repo", 5, thread_cache)
    assert res.id == 123

    # Should find archived thread
    res2 = await utils.find_thread(bot, 1, "owner/repo", 6, thread_cache)
    assert res2.id == 456


@pytest.mark.asyncio
async def test_get_or_create_thread_creates_and_caches():
    bot = Mock()
    forum = Mock()

    fake_thread = SimpleNamespace(id=999)
    # Return a wrapper with .thread attribute
    forum.create_thread = AsyncMock(return_value=SimpleNamespace(thread=fake_thread))
    forum.available_tags = []
    forum.create_tag = AsyncMock(return_value=SimpleNamespace(name="repo"))

    bot.get_channel = Mock(return_value=forum)

    thread_cache = {}
    res = await utils.get_or_create_thread(
        bot, 1, "owner/repo", 7, "Title", "url", [], thread_cache
    )

    assert res == (fake_thread, True)
    assert (1, "owner/repo", 7) in thread_cache

@pytest.mark.asyncio
async def test_get_or_create_thread_creates_and_caches():
    bot = Mock()
    forum = Mock()
    forum.id = 1

    fake_thread = FakeThread(999)
    forum.create_thread = AsyncMock(return_value=SimpleNamespace(thread=fake_thread))
    forum.available_tags = []
    forum.create_tag = AsyncMock(return_value=SimpleNamespace(name="repo"))
    forum.threads = []
    async def fake_archived_threads(limit=None):
        if False:
            yield None
    forum.archived_threads = fake_archived_threads

    bot.get_channel = Mock(return_value=forum)

    thread_cache = {}
    res = await utils.get_or_create_thread(
        bot, forum.id, "owner/repo", 7, "Title", "url", [], thread_cache
    )

    # unwrap if needed
    res_unwrapped, created = res
    assert res_unwrapped is fake_thread
    assert created is True
    assert (forum.id, "owner/repo", 7) in thread_cache


@pytest.mark.asyncio
async def test_get_or_create_thread_uses_cache():
    fake_thread = FakeThread(999)

    forum = Mock()
    forum.id = 1
    forum.available_tags = []
    forum.create_tag = AsyncMock(return_value=SimpleNamespace(name="repo"))

    bot = Mock()
    bot.get_channel = Mock(return_value=forum)

    thread_cache = {
        (forum.id, "owner/repo", 7): fake_thread,
        (str(forum.id), "owner/repo", 7): fake_thread,
    }

    res = await utils.get_or_create_thread(
        bot, forum.id, "owner/repo", 7, "T", "U", [], thread_cache
    )

    res_unwrapped, created = res
    assert res_unwrapped is fake_thread
    assert created is False
    assert res_unwrapped.id == 999
