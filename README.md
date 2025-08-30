# GenHub Cog for Redbot

A powerful Discord bot cog that integrates GitHub repositories with Discord forums, providing real-time synchronization of issues, pull requests, and discussions.

## ✨ Features

- **Real-time Synchronization**: Automatically creates and updates Discord forum threads for GitHub issues and PRs
- **Smart Thread Management**: Recreates deleted threads during reconciliation
- **Comprehensive Logging**: Detailed console and Discord logging for debugging
- **Environment Variable Support**: Secure token management via `GENHUB_GITHUB_TOKEN`
- **Flexible Configuration**: Text commands and slash commands for easy setup
- **Tag Management**: Automatic tag assignment based on issue/PR status
- **Feed Channels**: Optional announcement channels for new/updated items
- **Webhook Integration**: Receives GitHub webhook events for instant updates

---

## Installation

### Option 1: Manual Install

1. Copy the `GenHub` directory to the `cogs` directory of your Redbot instance.
2. Load the cog using the `[p]load GenHub` command.

### Option 2: Install from GitHub Repo

1. Add the repo to Redbot:

   ```bash
   !repo add genhub https://github.com/undead2146/GenHubCog/
   ```

2. Install the cog:

   ```bash
   !cog install genhub GenHub
   ```

3. Load the cog:

   ```bash
   !load GenHub
   ```

---

## Configuration

### Environment Variables (Recommended)

Set the GitHub token as an environment variable for security:
```bash
export GENHUB_GITHUB_TOKEN=your_github_token_here
```

### Discord Configuration

You can configure the cog using **either text commands** or the **slash command**.

#### Text Commands

All commands are prefixed with `[p]` (your bot's prefix, e.g. `!`):

- `[p]genhub host <host>`: Set the webhook host (default: 0.0.0.0)
- `[p]genhub port <port>`: Set the webhook port (default: 8080)
- `[p]genhub secret <secret>`: Set the GitHub webhook secret
- `[p]genhub addrepo <owner/repo>`: Add an allowed repository (e.g., owner/repo)
- `[p]genhub removerepo <owner/repo>`: Remove an allowed repository
- `[p]genhub logchannel <channel_id>`: Set the log channel ID for error reporting
- `[p]genhub issuesforum <forum_id>`: Set the Issues forum channel ID
- `[p]genhub prsforum <forum_id>`: Set the Pull Requests forum channel ID
- `[p]genhub issuesfeedchat <channel_id>`: Set the Issues Feed Chat channel ID
- `[p]genhub prsfeedchat <channel_id>`: Set the PR Feed Chat channel ID
- `[p]genhub issuesopentag <tag_id>`: Set the Issues forum "Open" tag ID
- `[p]genhub issuesclosedtag <tag_id>`: Set the Issues forum "Closed" tag ID
- `[p]genhub prsopentag <tag_id>`: Set the PR forum "Open" tag ID
- `[p]genhub prsclosedtag <tag_id>`: Set the PR forum "Closed" tag ID
- `[p]genhub prsmergedtag <tag_id>`: Set the PR forum "Merged" tag ID
- `[p]genhub contributorrole <role_id>`: Set the Contributor role ID for mentions
- `[p]genhub reconcile [repo]`: Reconcile all forum posts (optionally filter by repo)
- `[p]genhub showconfig`: Show the current GenHub configuration

#### Slash Command

- `/genhubconfig`: Configure all parameters in one go (autofill options in Discord UI)

---

## Usage

### Basic Setup

1. **Set Environment Variable**:

   ```bash
   export GENHUB_GITHUB_TOKEN=your_github_personal_access_token
   ```

2. **Configure Discord Channels**:

   ```bash
   !genhub issuesforum 1234567890123456789
   !genhub prsforum 1234567890123456789
   ```

3. **Add Repositories**:

   ```bash
   !genhub addrepo owner/repository
   ```

4. **Start Reconciliation**:

   ```bash
   !genhub reconcile
   ```

### Webhook Setup

1. In your GitHub repository settings, go to **Settings > Webhooks**
2. Add webhook URL: `https://your-domain.com/webhook`
3. Set Content type to `application/json`
4. Set Secret to match your configured secret
5. Select events: **Issues**, **Pull requests**, **Issue comments**, **Pull request review comments**

---

## Reconciliation Process

The `reconcile` command ensures your Discord forums stay synchronized with GitHub:

- **Recreates Deleted Threads**: If you delete a forum post, reconcile will recreate it
- **Updates Tags**: Ensures all threads have correct status tags
- **Handles Missing Data**: Gracefully handles API failures and permission issues
- **Comprehensive Logging**: Shows detailed progress and any issues encountered

### Example Output

```bash
🔄 Starting reconciliation... this may take a while.
🔍 Starting reconcile. Allowed repos: ['owner/repo']
🔑 Token source: ENV
✅ Token set in headers
🔄 Processing repo: owner/repo
📋 Issues forum ID: 123456789
✅ Issues forum found: Issues Forum (123456789)
🌐 Fetching issues page 1 for owner/repo
📡 Issues API response: 200
📦 Issues data received: 25 items
📝 Processing issue 1: Example Issue Title...
✅ Processed 25 issues for owner/repo
🎉 Reconciliation process finished!
```

---

## Troubleshooting

### Common Issues

#### "Failed to fetch issues/PRs, status: 403 (forbidden)"

- Check your GitHub token permissions
- Ensure the token has access to the repository
- Verify the repository exists and is not private

#### "No threads created during reconcile"

- Verify forum channels are configured correctly
- Check that the bot has permission to create threads
- Ensure repository has issues/PRs to sync

#### "Duplicate reconciliation complete messages"

- This was fixed in recent updates - only one completion message should appear

### Debug Logging

The bot provides extensive logging to help troubleshoot issues:

- **Console Logs**: Detailed progress and error information
- **Discord Logs**: Error messages sent to configured log channel
- **API Responses**: Shows GitHub API call results
- **Thread Creation**: Logs when threads are created or updated

---

## Development

### Local Testing Setup

```bash
# 1. Create Python 3.11 virtual environment
py -3.11 -m venv venv

# 2. Activate virtual environment
venv\Scripts\activate  # Windows
# or
source venv/bin/activate  # Linux/macOS

# 3. Start Redbot
redbot GenHubBot

# 4. Expose webhook port (optional)
ngrok http 8080
```

### Project Structure

```
GenHub/
├── __init__.py           # Cog initialization
├── genhub.py            # Main cog class and setup
├── webhook.py           # aiohttp server for webhooks
├── handlers.py          # GitHub event processing
├── config_commands.py   # Text-based configuration commands
├── slash_commands.py    # Discord slash commands
└── utils.py             # Helper functions and utilities
```

### Testing

Run the test suite:

```bash
python -m pytest tests/ -v
```

---

## Security Notes

- **Token Security**: Always use environment variables for GitHub tokens
- **Webhook Secrets**: Use strong, unique secrets for webhook validation
- **Permissions**: Grant minimal required Discord permissions to the bot
- **Repository Access**: Only add repositories you want to sync

---

## Support

For issues, feature requests, or contributions:

- Create an issue on the [GitHub repository](https://github.com/undead2146/GenHubCog)
- Check the troubleshooting section above
- Review the console logs for detailed error information

---

## License

This project is open source. See the repository for license details.
