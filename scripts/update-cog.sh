#!/usr/bin/env bash
# GenHub Cog One-Command Updater & Verifier
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

echo -e "\033[0;36m========================================\033[0m"
echo -e "\033[0;36m  Updating GenHub Cog from GitHub       \033[0m"
echo -e "\033[0;36m========================================\033[0m"

# 1. Fetch and pull latest changes
git fetch upstream main
LOCAL_HASH=$(git rev-parse HEAD)
REMOTE_HASH=$(git rev-parse upstream/main)

if [ "$LOCAL_HASH" != "$REMOTE_HASH" ]; then
    echo -e "\033[0;33mNew commits detected. Pulling changes...\033[0m"
    git pull upstream main
else
    echo -e "\033[0;32mAlready up to date with upstream/main ($LOCAL_HASH).\033[0m"
fi

# 2. Sync files into redbot data directory
echo -e "\n\033[0;33mSyncing cog files to RedBot data...\033[0m"
sudo cp -rf "$DIR/GenHub/"* "$DIR/redbot-data/cogs/GenHub/" 2>/dev/null || true
for cog_dir in "$DIR/redbot-data/cogs/CogManager/cogs/GenHub" "$DIR/redbot-data/cogs/Downloader/lib/genhub/GenHub" "$DIR/redbot-data/cogs/RepoManager/repos/genhubcog/GenHub"; do
    if [ -d "$cog_dir" ]; then
        sudo cp -rf "$DIR/GenHub/"* "$cog_dir/" 2>/dev/null || true
    fi
done
sudo chown -R 1000:1000 "$DIR/redbot-data"
sudo chmod -R 775 "$DIR/redbot-data"

# 3. Restart the container
echo -e "\n\033[0;33mRestarting RedBot container...\033[0m"
docker restart genhubbot

# 4. Verification
echo -e "\n\033[0;33mVerifying Webhook Server Health...\033[0m"
MAX_ATTEMPTS=10
ATTEMPT=1
HEALTH="FAIL"

while [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
    sleep 2
    STATUS=$(curl -s http://localhost:8080/health || true)
    if [ "$STATUS" == "OK" ]; then
        HEALTH="OK"
        break
    fi
    ATTEMPT=$((ATTEMPT + 1))
done

if [ "$HEALTH" == "OK" ]; then
    echo -e "  \033[0;32m[OK] Webhook server is healthy (HTTP 200: OK)\033[0m"
else
    echo -e "  \033[0;31m[!] Webhook server health check timed out.\033[0m"
fi

echo -e "\n\033[0;32m========================================\033[0m"
echo -e "\033[0;32m  Update & Verification Complete!       \033[0m"
echo -e "\033[0;32m  Current Commit: $(git log -1 --oneline) \033[0m"
echo -e "\033[0;32m========================================\033[0m"
