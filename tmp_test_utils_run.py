import asyncio
from types import SimpleNamespace
from unittest.mock import Mock, AsyncMock
import GenHub.utils as utils

async def main():
    print('Running quick checks for get_or_create_thread...')

    bot = Mock()
    forum = Mock()

    fake_thread = SimpleNamespace(id=999)
    forum.create_thread = AsyncMock(return_value=SimpleNamespace(thread=fake_thread))
    forum.available_tags = []
    forum.create_tag = AsyncMock(return_value=SimpleNamespace(name="repo"))

    bot.get_channel = Mock(return_value=forum)

    thread_cache = {}
    res = await utils.get_or_create_thread(
        bot, 1, "owner/repo", 7, "Title", "url", [], thread_cache
    )

    print('--- Scenario 1 ---')
    print('res is None?', res is None)
    print('res repr:', repr(res))
    print('res id:', getattr(res[0], 'id', None) if res and len(res) > 0 else None)
    print('created:', res[1] if res and len(res) > 1 else None)
    print('cache contains key:', (1, 'owner/repo', 7) in thread_cache)

    # Second scenario: cached thread object
    forum2 = Mock()
    forum2.available_tags = []
    forum2.create_tag = AsyncMock(return_value=SimpleNamespace(name="repo"))

    fake_thread2 = SimpleNamespace(id=999)
    thread_cache2 = {(1, "owner/repo", 7): fake_thread2}

    def get_channel_side(channel_id):
        if channel_id is fake_thread2:
            return fake_thread2
        return forum2

    bot.get_channel = Mock(side_effect=get_channel_side)

    res2 = await utils.get_or_create_thread(
        bot, 1, "owner/repo", 7, "T", "U", [], thread_cache2
    )
    print('--- Scenario 2 ---')
    print('res2 is fake_thread2?', res2[0] is fake_thread2 if res2 and len(res2) > 0 else False)
    print('res2 repr:', repr(res2))
    print('res2 id:', getattr(res2[0], 'id', None) if res2 and len(res2) > 0 else None)
    print('created:', res2[1] if res2 and len(res2) > 1 else None)

if __name__ == '__main__':
    asyncio.run(main())
