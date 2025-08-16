# GenHub Cog for Redbot

This cog receives GitHub webhook events and routes them to the correct Discord forum post.

## Installation

1.  Copy the `GenHub` directory to the `cogs` directory of your Redbot instance.
2.  Load the cog using the `[p]load GenHub` command.

## Configuration

Use the `[p]genhub` commands to configure the cog.

*   `[p]genhub host <host>`: Set the webhook host.
*   `[p]genhub port <port>`: Set the webhook port.
*   `[p]genhub secret <secret>`: Set the GitHub webhook secret.
*   `[p]genhub addrepo <owner/repo>`: Add an allowed repository.
*   `[p]genhub removerepo <owner/repo>`: Remove an allowed repository.
*   `[p]genhub logchannel <channel_id>`: Set the log channel ID.
*   `[p]genhub issuesforum <forum_id>`: Set the issues forum channel ID.
*   `[p]genhub prsforum <forum_id>`: Set the pull requests forum channel ID.
*   `[p]genhub showconfig`: Show the current configuration.

## Usage

Once the cog is loaded and configured, it will start listening for GitHub webhook events and route them to the appropriate Discord forum channels.

## Testing

Follow the testing plan outlined in the PRD to ensure that the cog is working correctly.
