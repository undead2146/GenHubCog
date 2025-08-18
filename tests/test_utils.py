import pytest
from unittest.mock import AsyncMock
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
