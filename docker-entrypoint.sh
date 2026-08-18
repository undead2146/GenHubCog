#!/bin/bash
set -e

echo "Starting RedBot with GenHubCog..."

# Set environment variables
export GENHUB_GITHUB_TOKEN="${GENHUB_GITHUB_TOKEN}"

# Ensure data directory exists
mkdir -p /home/redbot/redbot-data

# Check if instance is configured
if [ ! -f /home/redbot/.config/Red-DiscordBot/config.json ]; then
    echo "Configuring RedBot instance..."

    # Create config directory
    mkdir -p /home/redbot/.config/Red-DiscordBot

    # Create instance configuration
    cat > /home/redbot/.config/Red-DiscordBot/config.json << EOF
{
    "GenHubBot": {
        "DATA_PATH": "/home/redbot/redbot-data",
        "COG_PATH_APPEND": "cogs",
        "CORE_PATH_APPEND": "core",
        "STORAGE_TYPE": "JSON",
        "STORAGE_DETAILS": {}
    }
}
EOF

    echo "Instance configured"
fi

# Ensure core settings exist
if [ ! -f /home/redbot/redbot-data/core/settings.json ]; then
    echo "Creating core settings..."
    mkdir -p /home/redbot/redbot-data/core

    cat > /home/redbot/redbot-data/core/settings.json << EOF
{
    "0": {
        "GLOBAL": {
            "schema_version": 3
        },
        "CORE__PACKAGES": ["GenHub"]
    }
}
EOF

    echo "Core settings created"
fi

# Ensure GenHub cog is up to date in cogs directory
mkdir -p /home/redbot/redbot-data/cogs/GenHub
cp -r /home/redbot/GenHubCog/GenHub/* /home/redbot/redbot-data/cogs/GenHub/

# Start RedBot
echo "Starting RedBot instance..."
exec redbot GenHubBot --dev --no-prompt --token "${DISCORD_BOT_TOKEN}" --prefix "!" --load-cogs GenHub
