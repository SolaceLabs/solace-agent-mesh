FROM node:20-alpine

# Install system dependencies for Claude Code
RUN apk add --no-cache \
    git \
    ripgrep \
    curl \
    bash \
    procps-ng

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Set working directory
WORKDIR /build

# Copy SAM SDK (needed for template dependencies)
# Build context should be the repo root
COPY packages/sam-sdk /build/packages/sam-sdk

# Copy template files
COPY docker/claude-code-sam-app/template /build/template

# Move to template directory and install dependencies
WORKDIR /build/template
RUN npm install --prefer-offline --no-audit

# Replace the SDK symlink with actual files so template is self-contained
RUN rm -rf node_modules/@sam/sdk && \
    cp -r /build/packages/sam-sdk node_modules/@sam/sdk

# Validate that the template builds successfully
RUN npm run build

# Move template to final location (SDK is already inside node_modules)
WORKDIR /
RUN cp -r /build/template /template && rm -rf /build

# Create workspace directory for node user (node user exists in base image)
RUN mkdir -p /workspace /home/node/.claude && \
    chown -R node:node /workspace /home/node/.claude /template

# Switch to non-root user
USER node
WORKDIR /workspace

# Set git defaults for node user
RUN git config --global user.name "Claude Code" && \
    git config --global user.email "cc@workspace" && \
    git config --global init.defaultBranch main

# Copy workspace initialization and build scripts
COPY --chown=node:node docker/init-workspace.sh /usr/local/bin/
COPY --chown=node:node docker/build_and_version.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/init-workspace.sh /usr/local/bin/build_and_version.sh

# Set template directory for init script
ENV TEMPLATE_DIR=/template

# Add metadata
LABEL description="Pre-built React template for SAM apps with all dependencies installed"
LABEL version="1.0.0"

# Default entrypoint is Claude Code (same as other containers)
# Agent can override with --entrypoint=/usr/local/bin/init-workspace.sh to initialize workspace
ENTRYPOINT ["claude"]
