# GenHub Cog for Redbot

A powerful Discord bot cog that integrates GitHub repositories with Discord forums, providing real-time synchronization of issues, pull requests, comments, and reviews.

## ✨ Features

- **Real-time Synchronization**: Automatically creates and updates Discord forum threads for GitHub issues and PRs
- **Smart Review Batching**: Groups review comments to prevent notification spam (2-second delay)
- **Automatic Tag Management**: Creates and manages status tags (Open/Closed/Merged) dynamically
- **Thread Recreation**: Recreates deleted threads during reconciliation
- **Multi-Repository Support**: Handle multiple GitHub repositories with proper namespacing
- **Feed Channel Announcements**: Optional announcement channels for new/closed items
- **Role Mentioning**: Configurable contributor role notifications
- **Comprehensive Logging**: Detailed console and Discord logging for debugging
- **Environment Variable Support**: Secure token management via `GENHUB_GITHUB_TOKEN`
- **Flexible Configuration**: Text commands and slash commands for easy setup
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

### Token Configuration

Set the GitHub token using the Discord configuration commands below. The token is stored persistently in the bot's configuration.

#### Text Commands

All commands are prefixed with `[p]` (your bot's prefix, e.g. `!`):

- `[p]genhub host <host>`: Set the webhook host (default: 0.0.0.0)
- `[p]genhub port <port>`: Set the webhook port (default: 8080)
- `[p]genhub secret <secret>`: Set the GitHub webhook secret
- `[p]genhub token <token>`: Set the GitHub API token (alternative to env var)
- `[p]genhub addrepo <owner/repo>`: Add an allowed repository (e.g., owner/repo)
- `[p]genhub removerepo <owner/repo>`: Remove an allowed repository
- `[p]genhub logchannel <channel_id>`: Set the log channel ID for error reporting
- `[p]genhub issuesforum <forum_id>`: Set the Issues forum channel ID
- `[p]genhub prsforum <forum_id>`: Set the Pull Requests forum channel ID
- `[p]genhub issuesfeedchat <channel_id>`: Set the Issues Feed Chat channel ID
- `[p]genhub prsfeedchat <channel_id>`: Set the PR Feed Chat channel ID
- `[p]genhub contributorrole <role_id>`: Set the Contributor role ID for mentions
- `[p]genhub reconcile [repo]`: Reconcile all forum posts (optionally filter by repo)
- `[p]genhub clearcache`: Clear the thread cache to force fresh lookups
- `[p]genhub testrepo <repo>`: Test access to a GitHub repository
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
2. Add webhook URL: `https://your-domain.com/github`
3. Set Content type to `application/json`
4. Set Secret to match your configured secret
5. Select events: **Issues**, **Pull requests**, **Issue comments**, **Pull request reviews**, **Pull request review comments**

---

## Reconciliation Process

The `reconcile` command ensures your Discord forums stay synchronized with GitHub:

- **Recreates Deleted Threads**: If you delete a forum post, reconcile will recreate it
- **Updates Tags**: Ensures all threads have correct status tags (Open/Closed/Merged)
- **Handles Missing Data**: Gracefully handles API failures and permission issues
- **Cleans Up Orphans**: Removes threads for deleted GitHub items
- **Comprehensive Logging**: Shows detailed progress and any issues encountered

### Thread Naming Convention

Threads are created with the format: `[GH] [#{number}] {title}`

### Automatic Tag Management

The bot automatically creates and manages tags:
- **Status Tags**: Open, Closed, Merged (mutually exclusive)
- **Repository Tags**: One tag per repository for filtering
- **Activity Tags**: Active (for issues with assignees)

### Review Batching System

To prevent notification spam, review comments are batched together:
- Reviews with multiple comments are grouped into a single Discord message
- 2-second delay allows all review parts to arrive before posting
- One notification per review instead of one per comment

## Supported GitHub Events

GenHub processes the following GitHub webhook events:

- **Issues**: `opened`, `closed`, `reopened`, `assigned`, `unassigned`
- **Pull Requests**: `opened`, `closed`, `reopened`, `assigned`, `unassigned`, `merged`
- **Issue Comments**: `created` (comments on issues)
- **Pull Request Reviews**: `submitted` (review body)
- **Pull Request Review Comments**: `created` (individual review comments)

Each event type creates or updates the appropriate forum thread with formatted messages and status tags.

## How It Works

### Architecture Overview

GenHub uses a modular architecture with clear separation of concerns:

1. **Webhook Server** (`webhook.py`): Receives and validates GitHub webhook events
2. **Event Handlers** (`handlers.py`): Processes different event types with business logic
3. **Thread Manager** (`utils.py`): Handles Discord forum thread lifecycle
4. **Configuration System**: Manages settings via Redbot's config system

### Event Processing Flow

```
GitHub Event → Webhook Validation → Event Routing → Thread Lookup/Creation → Message Posting
```

### Thread Management

- **Naming**: `[GH] [#{number}] {title}` format prevents conflicts
- **Caching**: In-memory cache with Redbot persistence for performance
- **Tags**: Automatic creation and management of status/repository tags
- **Recovery**: Reconciliation recreates missing threads

### Review Processing

GitHub sends review events separately, so GenHub uses a 2-second batching system:
- Review body arrives → start timer
- Review comments arrive → add to batch
- Timer expires → post all content together
- Prevents notification spam for detailed reviews

---

## Troubleshooting

### Common Issues

#### "Failed to fetch issues/PRs, status: 403 (forbidden)"

- Check your GitHub token permissions (needs `repo` scope for private repos)
- Ensure the token has access to the repository
- Verify the repository exists and is not private
- Try using `!genhub testrepo <repo>` to diagnose access issues

#### "No threads created during reconcile"

- Verify forum channels are configured correctly with `!genhub showconfig`
- Check that the bot has permission to create threads in the forums
- Ensure repository has issues/PRs to sync
- Check console logs for detailed error messages

#### "Review comments appearing separately"

- This is normal behavior - reviews are batched but may still appear as separate messages
- The 2-second delay groups comments from the same review
- Individual comments from different reviews appear separately

#### "Thread cache errors"

- Use `!genhub clearcache` to reset the thread cache
- This forces fresh lookups and can resolve stale cache issues

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
├── __init__.py           # Cog initialization and setup
├── genhub.py            # Main cog class, configuration, lifecycle
├── webhook.py           # aiohttp server for GitHub webhook reception
├── handlers.py          # GitHub event processing and business logic
├── config_commands.py   # Text-based configuration commands
├── slash_commands.py    # Discord slash command interface
├── utils.py             # Thread management, message formatting, utilities
└── info.json            # Cog metadata and dependencies

tests/                   # Comprehensive test suite
├── conftest.py         # Test configuration and fixtures
├── test_*.py          # Individual component tests
└── utils.py           # Test utilities and mock objects
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
