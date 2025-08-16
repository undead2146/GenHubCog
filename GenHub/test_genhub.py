import asyncio
import unittest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
import sys
import importlib.util

class TestGenHub(unittest.TestCase):
    def setUp(self):
        # Mock redbot modules before they are imported by the cog
        sys.modules['redbot.core'] = MagicMock()
        sys.modules['redbot.core.commands'] = MagicMock()
        sys.modules['redbot.core.config'] = MagicMock()
        sys.modules['redbot.core.bot'] = MagicMock()
        sys.modules['aiohttp'] = MagicMock()

        # Manually load the genhub module from the file
        spec = importlib.util.spec_from_file_location("genhub", "Z:\\GenHubBot\\GenHub\\genhub.py")
        genhub = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'redbot.core': MagicMock(), 'redbot.core.commands': MagicMock(), 'redbot.core.config': MagicMock(), 'redbot.core.bot': MagicMock()}):
            spec.loader.exec_module(genhub)
        self.GenHub = genhub.GenHub

        # Mock the bot instance
        self.bot = AsyncMock()
        # We need to patch the config to prevent it from being a coroutine
        with patch('redbot.core.config.Config', new=Mock()):
             self.cog = self.GenHub(self.bot)

        # Mock the config object
        self.cog.config = AsyncMock()
        self.cog.config.allowed_repos = AsyncMock(return_value=["community-outpost/GenHub"])
        self.cog.config.issues_forum_id = AsyncMock(return_value=1403751882589077641)
        self.cog.config.prs_forum_id = AsyncMock(return_value=1403752148361150536)

    def test_repository_filtering_allowed(self):
        """Test that a payload from an allowed repo is processed."""
        payload = {
            "repository": {"full_name": "community-outpost/GenHub"},
            "action": "opened",
            "issue": {
                "number": 123,
                "title": "Test Issue",
                "html_url": "http://example.com/issue/123"
            }
        }
        headers = {"X-GitHub-Event": "issues"}
        request = Mock(headers=headers)

        # We need to run the async function in a test
        async def run_test():
            self.cog.handle_issue = AsyncMock()
            await self.cog.process_payload(request, payload)
            self.cog.handle_issue.assert_called_once_with(payload)

        asyncio.run(run_test())

    def test_repository_filtering_denied(self):
        """Test that a payload from a non-allowed repo is ignored."""
        payload = {
            "repository": {"full_name": "some/other-repo"}
        }
        headers = {"X-GitHub-Event": "issues"}
        request = Mock(headers=headers)
        
        async def run_test():
            self.cog.handle_issue = AsyncMock()
            await self.cog.process_payload(request, payload)
            self.cog.handle_issue.assert_not_called()

        asyncio.run(run_test())

    def test_new_issue_thread_creation(self):
        """Test that a new issue creates a new thread."""
        payload = {
            "action": "opened",
            "issue": {
                "number": 123,
                "title": "My Test Issue",
                "html_url": "http://example.com/issue/123"
            }
        }
        
        mock_forum = AsyncMock()
        mock_forum.create_thread = AsyncMock()
        self.bot.get_channel = Mock(return_value=mock_forum)

        async def run_test():
            await self.cog.handle_issue(payload)
            
            # Verify that a thread is created with the correct name and content
            mock_forum.create_thread.assert_called_once_with(
                name="「#123」My Test Issue",
                content="[#123](http://example.com/issue/123)"
            )

        asyncio.run(run_test())

    def test_comment_forwarding(self):
        """Test that a new comment is forwarded to the correct thread."""
        payload = {
            "issue": {"number": 456},
            "comment": {
                "user": {"login": "testuser"},
                "body": "This is a test comment."
            }
        }

        mock_thread = AsyncMock()
        mock_thread.send = AsyncMock()
        
        async def run_test():
            # Mock find_thread to return our mock thread
            self.cog.find_thread = AsyncMock(return_value=mock_thread)
            await self.cog.handle_issue_comment(payload)

            # Verify the message sent to the thread
            self.cog.find_thread.assert_called_once_with(1403751882589077641, 456)
            mock_thread.send.assert_called_once_with(
                "💬 New comment from @testuser:\nThis is a test comment."
            )

        asyncio.run(run_test())

if __name__ == '__main__':
    unittest.main()