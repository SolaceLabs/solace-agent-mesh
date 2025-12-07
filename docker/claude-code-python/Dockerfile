FROM python:3.11-slim

# Install system dependencies including Node.js for Claude Code CLI
RUN apt-get update && apt-get install -y \
    git \
    ripgrep \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js (required for Claude Code CLI)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Install common Python development tools
RUN pip install --no-cache-dir \
    pytest \
    black \
    flake8 \
    mypy

# Create python user (similar to node user in node image)
RUN useradd -m -s /bin/bash python

# Create workspace and config directories for python user
RUN mkdir -p /workspace /home/python/.claude && \
    chown -R python:python /workspace /home/python/.claude

# Switch to non-root user
USER python
WORKDIR /workspace

# Set git defaults for python user
RUN git config --global user.name "Claude Code" && \
    git config --global user.email "cc@workspace" && \
    git config --global init.defaultBranch main

ENTRYPOINT ["claude"]
