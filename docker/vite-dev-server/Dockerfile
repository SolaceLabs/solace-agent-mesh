FROM node:20-alpine

# Install basic utilities
RUN apk add --no-cache git

# Set working directory
WORKDIR /workspace

# Expose Vite dev server port
EXPOSE 5173

# Health check to verify Vite is running
HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:5173 || exit 1

# Default command: run Vite dev server
CMD ["npm", "run", "dev"]
