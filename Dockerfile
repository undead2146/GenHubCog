FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create redbot user
RUN useradd -m -s /bin/bash redbot

# Switch to redbot user
USER redbot
WORKDIR /home/redbot

# Install Red-DiscordBot
RUN pip install --user --upgrade Red-DiscordBot

# Add pip bin to PATH
ENV PATH="/home/redbot/.local/bin:${PATH}"

# Create data directory
RUN mkdir -p /home/redbot/redbot-data

# Copy GenHubCog
COPY --chown=redbot:redbot . /home/redbot/GenHubCog

# Expose webhook port
EXPOSE 8080

# Start script
COPY --chown=redbot:redbot docker-entrypoint.sh /home/redbot/
RUN chmod +x /home/redbot/docker-entrypoint.sh

ENTRYPOINT ["/home/redbot/docker-entrypoint.sh"]
