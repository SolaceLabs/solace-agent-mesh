## If rebuilding, you must first delete the previous version:
```bash
docker stop sam-app
docker rmi meshflow-markets
docker rmi solace-agent-mesh
```

## Building
```bash
docker build --no-cache -t solace-agent-mesh .
```