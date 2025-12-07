FROM node:20-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    ripgrep \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Create workspace and config directories for node user
RUN mkdir -p /workspace /home/node/.claude && \
    chown -R node:node /workspace /home/node/.claude

# Switch to non-root user (node user already exists in base image)
USER node
WORKDIR /workspace

# Set git defaults for node user
RUN git config --global user.name "Claude Code" && \
    git config --global user.email "cc@workspace" && \
    git config --global init.defaultBranch main

ENTRYPOINT ["claude"]
