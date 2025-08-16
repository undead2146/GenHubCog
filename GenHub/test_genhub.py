import asyncio
import unittest
from unittest.mock import Mock, AsyncMock, patch
import sys
import importlib.util


class TestGenHub(unittest.TestCase):
    def setUp(self):
        # Mock redbot modules before they are imported by the cog
        sys.modules['redbot.core'] = Mock()
        sys.modules['redbot.core.commands'] = Mock()
        sys.modules['redbot.core.config'] = Mock()
        sys.modules['redbot.core.bot'] = Mock()
        sys.modules['aiohttp'] = Mock()

        # Manually load the genhub module from the file
        spec = importlib.util.spec_from_file_location("genhub", "Z:\\GenHubBot\\GenHub\\genhub.py")
        genhub = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {
            'redbot.core': Mock(),
            'redbot.core.commands': Mock(),
            'redbot.core.config': Mock(),
            'redbot.core.bot': Mock()
        }):
            spec.loader.exec_module(genhub)
        self.GenHub = genhub.GenHub

        # Mock the bot instance
        self.bot = AsyncMock()
        with patch('redbot.core.config.Config', new=Mock()):
            self.cog = self.GenHub(self.bot)

        # Mock config values
        self.cog.config = AsyncMock()
        self.cog.config.allowed_repos = AsyncMock(return_value=["undead2146/GH"])
        self.cog.config.issues_forum_id = AsyncMock(return_value=1403751882589077641)
        self.cog.config.prs_forum_id = AsyncMock(return_value=1403752148361150536)
        self.cog.config.issues_feed_chat_id = AsyncMock(return_value=1500000000000000001)
        self.cog.config.prs_feed_chat_id = AsyncMock(return_value=1500000000000000002)

    def test_new_issue_thread_and_feedchat(self):
        """Test that a new issue creates a thread and announces in feed chat."""
        payload = {
            "action": "opened",
            "issue": {
                "number": 123,
                "title": "My Test Issue",
                "html_url": "http://example.com/issue/123",
                "user": {"login": "testuser"}
            }
        }

        mock_forum = AsyncMock()
        mock_forum.create_thread = AsyncMock()
        mock_feedchat = AsyncMock()
        mock_feedchat.send = AsyncMock()

        def get_channel(cid):
            if cid == 1403751882589077641:
                return mock_forum
            if cid == 1500000000000000001:
                return mock_feedchat
            return None

        self.bot.get_channel = Mock(side_effect=get_channel)

        async def run_test():
            await self.cog.handle_issue(payload)
            mock_forum.create_thread.assert_called_once_with(
                name="「#123」My Test Issue",
                content="[#123](http://example.com/issue/123)"
            )
            mock_feedchat.send.assert_called_once()
            args, _ = mock_feedchat.send.call_args
            assert "<@&1404155973576294400>" in args[0]
            assert "My Test Issue" in args[0]

        asyncio.run(run_test())

    def test_new_pr_thread_and_feedchat(self):
        """Test that a new PR creates a thread and announces in feed chat."""
        payload = {
            "action": "opened",
            "pull_request": {
                "number": 456,
                "title": "My Test PR",
                "html_url": "http://example.com/pr/456",
                "user": {"login": "pruser"}
            }
        }

        mock_forum = AsyncMock()
        mock_forum.create_thread = AsyncMock()
        mock_feedchat = AsyncMock()
        mock_feedchat.send = AsyncMock()

        def get_channel(cid):
            if cid == 1403752148361150536:
                return mock_forum
            if cid == 1500000000000000002:
                return mock_feedchat
            return None

        self.bot.get_channel = Mock(side_effect=get_channel)

        async def run_test():
            await self.cog.handle_pull_request(payload)
            mock_forum.create_thread.assert_called_once_with(
                name="「#456」My Test PR",
                content="[#456](http://example.com/pr/456)"
            )
            mock_feedchat.send.assert_called_once()
            args, _ = mock_feedchat.send.call_args
            assert "<@&1404155973576294400>" in args[0]
            assert "My Test PR" in args[0]

        asyncio.run(run_test())

    def test_comment_forwarding_format(self):
        """Test that a comment is forwarded with hyperlink formatting."""
        payload = {
            "issue": {"number": 789},
            "comment": {
                "user": {"login": "commenter"},
                "body": "This is a test comment.",
                "html_url": "http://example.com/issue/789#comment-1"
            }
        }

        mock_thread = AsyncMock()
        mock_thread.send = AsyncMock()
        self.cog.find_thread = AsyncMock(return_value=mock_thread)

        async def run_test():
            await self.cog.handle_issue_comment(payload)
            mock_thread.send.assert_called_once()
            args, _ = mock_thread.send.call_args
            assert "# **[ New comment from commenter ](http://example.com/issue/789#comment-1)**" in args[0]
            assert "This is a test comment." in args[0]
            assert "\n" in args[0]  # ensure newline not literal /n

        asyncio.run(run_test())

    def test_review_forwarding_format(self):
        """Test that a review is forwarded with hyperlink formatting."""
        payload = {
            "pull_request": {"number": 101},
            "review": {
                "user": {"login": "reviewer"},
                "body": "Looks good to me.",
                "html_url": "http://example.com/pr/101#review-1"
            }
        }

        mock_thread = AsyncMock()
        mock_thread.send = AsyncMock()
        self.cog.find_thread = AsyncMock(return_value=mock_thread)

        async def run_test():
            await self.cog.handle_pull_request_review(payload)
            mock_thread.send.assert_called_once()
            args, _ = mock_thread.send.call_args
            assert "# **[ Review from reviewer ](http://example.com/pr/101#review-1)**" in args[0]
            assert "Looks good to me." in args[0]
            assert "\n" in args[0]

        asyncio.run(run_test())


if __name__ == '__main__':
    unittest.main()
