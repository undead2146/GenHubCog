# GenHub Cog for Redbot

This cog receives GitHub webhook events and routes them to the correct Discord forum post.

---

## Installation

**Option 1: Manual Install**

1. Copy the `GenHub` directory to the `cogs` directory of your Redbot instance.  
2. Load the cog using the `[p]load GenHub` command.

**Option 2: Install from GitHub Repo**

1. Add the repo to Redbot:

   ```
   !repo add genhub https://github.com/undead2146/GenHubCog/
   ```

2. Install the cog:

   ```
   !cog install genhub GenHub
   ```

3. Load the cog:

   ```
   !load GenHub
   ```

---

## Configuration

You can configure the cog using **either text commands** or the **slash command**.

### Text Commands

All commands are prefixed with `[p]` (your bot's prefix, e.g. `!`):

- `[p]genhub host <host>`: Set the webhook host (default: 0.0.0.0).
- `[p]genhub port <port>`: Set the webhook port (default: 8080).
- `[p]genhub secret <secret>`: Set the GitHub webhook secret.
- `[p]genhub addrepo <owner/repo>`: Add an allowed repository (e.g., owner/repo).
- `[p]genhub removerepo <owner/repo>`: Remove an allowed repository.
- `[p]genhub logchannel <channel_id>`: Set the log channel ID.
- `[p]genhub issuesforum <forum_id>`: Set the Issues forum channel ID.
- `[p]genhub prsforum <forum_id>`: Set the Pull Requests forum channel ID.
- `[p]genhub issuesfeedchat <channel_id>`: Set the Issues Feed Chat channel ID.
- `[p]genhub prsfeedchat <channel_id>`: Set the PR Feed Chat channel ID.
- `[p]genhub issuesopentag <tag_id>`: Set the Issues forum "Open" tag ID.
- `[p]genhub issuesclosedtag <tag_id>`: Set the Issues forum "Closed" tag ID.
- `[p]genhub prsopentag <tag_id>`: Set the PR forum "Open" tag ID.
- `[p]genhub prsclosedtag <tag_id>`: Set the PR forum "Closed" tag ID.
- `[p]genhub prsmergedtag <tag_id>`: Set the PR forum "Merged" tag ID.
- `[p]genhub contributorrole <role_id>`: Set the Contributor role ID for mentions in feed messages.
- `[p]genhub showconfig`: Show the current GenHub configuration.

### Slash Command

- `/genhubconfig`: Configure all parameters in one go (autofill options in Discord UI).

---

## Usage

Once the cog is loaded and configured, it will start listening for GitHub webhook events and route them to the appropriate Discord forum channels.  
It will also announce new/closed/reopened/merged issues and PRs in the configured feed chat channels.

---

## Testing

Follow the testing plan outlined in the PRD to ensure that the cog is working correctly.

---

## Useful Commands for Local Development

When running the cog locally for testing, you can use the following commands:

```bash
# 1. Create a Python 3.11 virtual environment
py -3.11 -m venv venv

# 2. Activate the virtual environment
venv\Scripts\activate   # (Windows PowerShell / CMD)
# or
source venv/bin/activate   # (Linux / macOS)

# 3. Start your Redbot instance with your bot name
redbot GenHubBot

# 4. Expose your local webhook port to the internet with ngrok
ngrok http 8080

```

---

## Project Structure

The `GenHub` cog directory is organized as follows:

```
GenHub/
 ├── __init__.py
 ├── genhub.py          # Main cog class
 ├── webhook.py         # aiohttp server + webhook handler
 ├── handlers.py        # GitHub event handlers
 ├── config_commands.py # Text commands ([p]genhub ...)
 ├── slash_commands.py  # Slash command (/genhubconfig)
 └── utils.py           # Helpers (send_message, resolve_tag, etc.)
```

---

## Summary

- **Installation:**  
  - Manual: Copy the `GenHub` directory to your Redbot `cogs` folder and load it.  
  - Or use the following commands to install from GitHub:

    ```
    !repo add genhub https://github.com/undead2146/GenHubCog/
    !cog install genhub GenHub
    !load GenHub
    ```

- **Configuration:** Use text or slash commands to set up webhook, repositories, channels, and tags.
- **Usage:** The cog listens for GitHub webhook events and routes them to Discord forums and feeds.
- **Development:** Use the provided commands and project structure for local testing and development.
