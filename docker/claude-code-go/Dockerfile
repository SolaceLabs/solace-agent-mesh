FROM golang:1.21-alpine

# Install system dependencies
RUN apk add --no-cache \
    git \
    ripgrep \
    curl \
    nodejs \
    npm \
    bash \
    procps-ng

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Create go user (similar to node user in node image)
RUN adduser -D -s /bin/bash go

# Create workspace and config directories for go user
RUN mkdir -p /workspace /home/go/.claude && \
    chown -R go:go /workspace /home/go/.claude

# Switch to non-root user
USER go
WORKDIR /workspace

# Set git defaults for go user
RUN git config --global user.name "Claude Code" && \
    git config --global user.email "cc@workspace" && \
    git config --global init.defaultBranch main

ENTRYPOINT ["claude"]
