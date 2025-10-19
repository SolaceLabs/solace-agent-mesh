# Docker Quick Start Guide

## 🚀 Quick Commands

### Build the Image

```bash
docker build -t sam .
```

### Run the Image

```bash
# Run with default preset agents
docker run --rm -p 5002:5002 -p 8000:8000 sam

# Run with custom agents
docker run --rm -p 5002:5002 -p 8000:8000 \
  -v /path/to/agents:/agents \
  sam run /agents

# Get help
docker run --rm sam --help

# Get version
docker run --rm sam --version
```

### Development Workflow

#### Making Code Changes

```bash
# 1. Edit your code
# 2. Rebuild (fast! only rebuilds changed layers)
docker build -t sam .

# 3. Test
docker run --rm sam --version
```

#### Adding Dependencies

```bash
# 1. Edit pyproject.toml
vim pyproject.toml

# 2. Update lock file
uv lock

# 3. Rebuild
docker build -t sam .

# 4. Commit both files
git add pyproject.toml uv.lock
git commit -m "Add new dependency"
```

#### Updating All Dependencies

```bash
# Update to latest compatible versions
uv lock --upgrade

# Rebuild
docker build -t sam .

# Commit
git add uv.lock
git commit -m "Update dependencies"
```

## 📊 Build Performance

### Expected Build Times

| Scenario                         | Time       | What's Cached                         |
| -------------------------------- | ---------- | ------------------------------------- |
| **First build**                  | ~8-12 min  | Nothing                               |
| **Code change only**             | ~2-3 min   | Dependencies, npm packages            |
| **Dependency change**            | ~5-8 min   | System packages, some Python packages |
| **Fresh rebuild** (`--no-cache`) | ~10-15 min | Nothing                               |

### Cache Layers

The build is optimized with these cache layers (fastest to slowest to invalidate):

1. ✅ **System dependencies** - Cached unless Dockerfile changes
2. ✅ **uv installer** - Cached (pulled from ghcr.io)
3. ✅ **Python dependencies** - Cached until `pyproject.toml` or `uv.lock` changes
4. ✅ **Frontend builds** - Rebuilt when source changes
5. 🔄 **Source code** - Always copied fresh
6. 🔄 **Wheel build** - Rebuilt when source changes

## 🔍 Inspection Commands

### Image Information

```bash
# List images
docker images sam

# Image details
docker inspect sam

# Image layers
docker history sam

# Image size breakdown
docker system df -v | grep sam
```

### Running Container Information

```bash
# List running containers
docker ps

# Container logs
docker logs <container-id>

# Execute command in running container
docker exec -it <container-id> bash

# Container resource usage
docker stats <container-id>
```

## 🐛 Troubleshooting

### Build Issues

#### "uv.lock not found" or "out of date"

```bash
uv lock
docker build -t sam .
```

#### "Build script does not exist"

Check `.dockerignore` - ensure `.github/helper_scripts/` is not excluded

#### "docs directory not found"

Check `.dockerignore` - ensure `docs/` is not excluded

#### Frontend build fails

```bash
# Check if npm is available
docker run --rm sam which npm

# Check build logs
cat build.log  # if available
```

### Runtime Issues

#### Port already in use

```bash
# Use different ports
docker run --rm -p 5003:5002 -p 8001:8000 sam
```

#### Permission errors

```bash
# Image already runs as non-root user 'solaceai'
# If mounting volumes, ensure proper permissions
docker run --rm -v /path/to/data:/data \
  sam run /data/agents
```

#### Environment variables not set

```bash
# Pass environment variables
docker run --rm \
  -e SESSION_SECRET_KEY="your-secret" \
  -e LLM_SERVICE_ENDPOINT="https://api.example.com" \
  -e LLM_SERVICE_API_KEY="your-api-key" \
  -e LLM_SERVICE_PLANNING_MODEL_NAME="gpt-4" \
  -e LLM_SERVICE_GENERAL_MODEL_NAME="gpt-3.5-turbo" \
  -p 5002:5002 -p 8000:8000 \
  sam
```

## 🔧 Advanced Usage

### Debug Build Process

```bash
# Build with verbose output
docker build --progress=plain -t sam .

# Build specific stage
docker build --target=builder -t sam-builder .

# Build without cache
docker build --no-cache -t sam .

# Build with specific platform
docker build --platform linux/amd64 -t sam .
docker build --platform linux/arm64 -t sam .
```

### Optimize Build Cache

```bash
# Prune old build cache
docker builder prune

# Prune everything (careful!)
docker system prune -a

# Keep last 24 hours only
docker builder prune --keep-storage 10GB
```

### Development with Docker Compose

```yaml
# docker-compose.yml
version: "3.8"
services:
  sam:
    build: .
    ports:
      - "5002:5002"
      - "8000:8000"
    environment:
      - SESSION_SECRET_KEY=${SESSION_SECRET_KEY}
      - LLM_SERVICE_ENDPOINT=${LLM_SERVICE_ENDPOINT}
      - LLM_SERVICE_API_KEY=${LLM_SERVICE_API_KEY}
      - LLM_SERVICE_PLANNING_MODEL_NAME=${LLM_SERVICE_PLANNING_MODEL_NAME}
      - LLM_SERVICE_GENERAL_MODEL_NAME=${LLM_SERVICE_GENERAL_MODEL_NAME}
    volumes:
      - ./agents:/agents
    command: run /agents
```

Then run:

```bash
docker-compose up --build
```

## 📦 Multi-Platform Builds

### Build for Multiple Platforms

```bash
# Setup buildx
docker buildx create --name multiplatform --use

# Build for multiple platforms
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t sam:latest \
  --push .
```

## 🎯 Best Practices

### Do's ✅

- ✅ Always run `uv lock` after changing `pyproject.toml`
- ✅ Commit `uv.lock` to version control
- ✅ Use `.dockerignore` to exclude unnecessary files
- ✅ Test builds locally before pushing to CI
- ✅ Use specific base image tags (not `latest`)
- ✅ Run as non-root user (already configured)

### Don'ts ❌

- ❌ Don't commit `build.log` or other build artifacts
- ❌ Don't skip the lock file - it ensures reproducibility
- ❌ Don't add secrets to the Dockerfile
- ❌ Don't run as root in production
- ❌ Don't use `--no-cache` unless necessary (slow!)

## 📚 More Information

- **Full Guide**: See `DOCKER_BUILD_GUIDE.md`
- **Optimization Details**: See `DOCKER_OPTIMIZATION_SUMMARY.md`
- **Project README**: See `README.md`

---

**Happy Building!** 🚀
