# Vite Dev Server Image

Containerized Vite development server for running SAM app workspaces with hot module replacement (HMR).

## Purpose

This image runs Vite dev servers for SAM apps in isolated Docker containers on the internal `sam-internal` network. Each app gets its own container with:
- Isolated environment
- Hot Module Replacement (HMR) via WebSocket
- Health checks for reliability
- Volume-mounted workspace for live code updates

## Building the Image

```bash
./build.sh
```

Or manually:
```bash
docker build -t vite-dev-server:latest .
```

## Usage in SAM Backend

The backend creates a container for each app's dev server:

```python
def start_dev_server(app_id: str, workspace_path: str, user_id: str) -> str:
    """Start containerized Vite dev server on internal Docker network"""
    container_name = f"sam-app-{user_id}-{app_id}"

    # Stop existing container if running
    subprocess.run(
        ["docker", "stop", container_name],
        capture_output=True
    )
    subprocess.run(
        ["docker", "rm", container_name],
        capture_output=True
    )

    # Start new container
    result = subprocess.run([
        "docker", "run", "-d",
        "--name", container_name,
        "--network", "sam-internal",
        "-v", f"{workspace_path}:/workspace",
        "vite-dev-server:latest"
    ], capture_output=True, text=True, check=True)

    container_id = result.stdout.strip()

    # Wait for health check to pass
    for _ in range(30):
        health = subprocess.run([
            "docker", "inspect",
            "--format", "{{.State.Health.Status}}",
            container_id
        ], capture_output=True, text=True)

        if health.stdout.strip() == "healthy":
            break
        time.sleep(1)

    return container_name
```

## Networking

Containers run on the `sam-internal` Docker network:
- **App containers**: `sam-app-{user_id}-{app_id}` (e.g., `sam-app-user123-dashboard`)
- **Backend proxy**: Routes requests from `/apps/preview/{app_id}/*` to container
- **WebSocket proxy**: Routes HMR WebSocket from `/apps/preview/{app_id}/__vite_hmr` to container

## Vite Configuration

The workspace's `vite.config.ts` must be configured for containerized environments:

```typescript
export default defineConfig({
  server: {
    host: '0.0.0.0',        // Listen on all interfaces
    port: 5173,             // Standard Vite port
    strictPort: true,       // Fail if port is in use
    hmr: {
      clientPort: 443       // HMR WebSocket through HTTPS proxy
    }
  }
})
```

## Volume Mounts

The workspace is mounted at `/workspace` in the container:
```bash
-v /path/to/workspace:/workspace
```

This allows:
- Code changes to appear instantly in the container
- Vite to detect changes and trigger HMR
- Claude Code tools to modify files that Vite watches

## Health Checks

The container includes health checks:
```dockerfile
HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:5173 || exit 1
```

This ensures:
- Backend knows when the dev server is ready
- Unhealthy containers are detected and restarted
- Preview requests don't fail before server is ready

## Lifecycle Management

**Starting a dev server:**
1. Backend receives preview request
2. Checks if container exists
3. If not, creates and starts container
4. Waits for health check to pass
5. Proxies request to container

**Stopping a dev server:**
1. User closes app or timeout expires (30 min idle)
2. Backend sends `docker stop {container_name}`
3. Container gracefully shuts down
4. Resources are released

**Updating code:**
1. Claude Code tools modify workspace files
2. Docker volume reflects changes instantly
3. Vite detects file changes
4. HMR pushes updates to browser via WebSocket
5. Preview updates without page reload

## Testing Locally

Start a test container:
```bash
docker run -d \
  --name test-vite \
  --network sam-internal \
  -v $(pwd)/test-workspace:/workspace \
  -p 5173:5173 \
  vite-dev-server:latest
```

View logs:
```bash
docker logs -f test-vite
```

Check health:
```bash
docker inspect --format='{{.State.Health.Status}}' test-vite
```

Stop container:
```bash
docker stop test-vite
docker rm test-vite
```

## Resource Limits

Consider adding resource limits in production:
```bash
docker run -d \
  --name sam-app-user123-dashboard \
  --network sam-internal \
  -v /path/to/workspace:/workspace \
  --memory="512m" \
  --cpus="0.5" \
  vite-dev-server:latest
```

## Troubleshooting

**Container won't start:**
- Check if port 5173 is available
- Verify workspace path exists and has package.json
- Check Docker logs: `docker logs {container_name}`

**HMR not working:**
- Verify `vite.config.ts` has correct `hmr.clientPort`
- Check WebSocket proxy is routing correctly
- Ensure browser can connect to HMR WebSocket

**Preview shows old code:**
- Check if Vite detected file changes (logs)
- Verify workspace volume is mounted correctly
- Try hard refresh (Ctrl+Shift+R)
