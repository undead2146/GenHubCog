import asyncio
from unittest.mock import AsyncMock


def make_fake_forum_with_threads(threads=None, name="Issues Forum"):
    """
    Create a fake forum mock with threads and a working archived_threads async iterator.
    """
    forum = AsyncMock()
    forum.name = name
    forum.threads = threads or []

    # archived_threads must be an async iterable
    async def fake_archived_threads(limit=None):
        if False:  # ensures it's an async generator
            yield None
        for t in forum.threads:
            yield t

    forum.archived_threads = fake_archived_threads
    return forum


def make_fake_aiohttp_session(fake_json_data, status: int = 200):
    """
    Create a fake aiohttp.ClientSession replacement that yields a FakeResponse
    with the given JSON data and status code. Returns an instance that can be
    used as the return_value for patching aiohttp.ClientSession.
    """

    class FakeResponse:
        def __init__(self, data, status_code):
            self._data = data
            self.status = status_code

        async def json(self):
            return self._data

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        # return FakeResponse directly (supports 'async with session.get(...) as resp')
        def get(self, url, headers=None):
            return FakeResponse(fake_json_data, status)

    return FakeSession()
