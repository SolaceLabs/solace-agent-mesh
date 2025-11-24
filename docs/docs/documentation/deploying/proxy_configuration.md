---
title: Proxy Configuration
sidebar_position: 550
---

# Proxy Configuration

When deploying Agent Mesh in environments with restricted network access, you may need to configure proxy settings to enable communication with external services. This guide explains how to configure HTTPS proxy settings for Agent Mesh.

## Environment Variables for Proxy Configuration

Agent Mesh respects standard proxy environment variables that are commonly used across many applications:

| Environment Variable | Description | Format | Example |
|---------------------|-------------|--------|---------|
| `HTTPS_PROXY` | Specifies the proxy server for HTTPS requests | `protocol://[username:password@]host[:port]` | `http://proxy.example.com:8080` or `https://proxy.example.com:443` |
| `REQUESTS_CA_BUNDLE` | Path to a custom CA certificate file or bundle used by requests and a number of other libraries. Use alongside SSL_CERT_FILE to maximize compatibility. | `Path to certificate` | `/path/to/certificate.crt` |
| `SSL_CERT_FILE` | Path to a custom CA certificate file or bundle used by requests and a number of other libraries. Use alongside REQUESTS_CA_BUNDLE to maximize compatibility. | `Path to certificate` | `/path/to/certificate.crt` |
| `DISABLE_SSL_VERIFY` | When set to a true value disables SSL certificate validation for outgoing LLM requests. | boolean | `true` |

These environment variables can be set at the system level or specifically for the Agent Mesh process.

## Proxy Configuration Details

If DISABLE_SSL_VERIFY is true → TLS verification is disabled (applies globally).
Else if REQUESTS_CA_BUNDLE or SSL_CERT_FILE is set → the provided file is used as the trusted CA bundle for TLS validation. Recommendation: set both REQUESTS_CA_BUNDLE and SSL_CERT_FILE to the same path to maximize compatibility, because different components/libraries may read one or the other.
Else → the system's default/trusted CA bundle is used.

## Setting Proxy Environment Variables

### Linux/macOS

For temporary settings (current terminal session only):

```bash
export HTTPS_PROXY="http://proxy.example.com:8080"
export REQUESTS_CA_BUNDLE="/path/to/certificate.pem"
export SSL_CERT_FILE="$REQUESTS_CA_BUNDLE"
```

For persistent settings, add these lines to your `~/.bashrc`, `~/.bash_profile`, or `~/.zshrc` file.

### Windows

For temporary settings (current command prompt session only):

```cmd
set HTTPS_PROXY=http://proxy.example.com:8080
set REQUESTS_CA_BUNDLE="/path/to/certificate.pem"
set SSL_CERT_FILE="/path/to/certificate.pem"
```

### Docker

When running Agent Mesh in Docker, you can set environment variables in your Docker run command:

```bash
docker run --rm \
  -e HTTPS_PROXY="http://proxy.example.com:8080" \
  -e REQUESTS_CA_BUNDLE="/etc/ssl/certs/custom-ca.pem" \
  -e SSL_CERT_FILE="/etc/ssl/certs/custom-ca.pem" \
  -v "$HOME/.mitmproxy/mitmproxy-ca.pem:/etc/ssl/certs/custom-ca.pem:ro" \
  solace/agent-mesh:latest

```

Or in your Docker Compose file:

```yaml
services:
  agent-mesh:
    image: solace/agent-mesh:latest
    environment:
      - HTTPS_PROXY=http://proxy.example.com:8080
      - REQUESTS_CA_BUNDLE=/etc/ssl/certs/custom-ca.pem
      - SSL_CERT_FILE=/etc/ssl/certs/custom-ca.pem
    volumes:
      - ./certs/mitmproxy-ca.pem:/etc/ssl/certs/custom-ca.pem:ro
....

```

### Kubernetes

For Kubernetes deployments:

Ensure configmap:
```shell
kubectl create configmap mitm-ca \
  --from-file=mitmproxy-ca.pem=./certs/mitmproxy-ca.pem \
  -n my-namespace

```

reference in deployment manifest:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: agent-mesh
  namespace: my-namespace
spec:
  replicas: 1
  selector:
    matchLabels:
      app: agent-mesh
  template:
    metadata:
      labels:
        app: agent-mesh
    spec:
      containers:
        - name: agent-mesh
          image: solace/agent-mesh:latest
          env:
            - name: HTTPS_PROXY
              value: "http://my-proxy.example.com:8080"
            - name: REQUESTS_CA_BUNDLE
              value: "/etc/ssl/certs/mitmproxy-ca.pem"
            - name: SSL_CERT_FILE
              value: "/etc/ssl/certs/mitmproxy-ca.pem"
          volumeMounts:
            - name: mitm-ca
              mountPath: /etc/ssl/certs/mitmproxy-ca.pem
              subPath: mitmproxy-ca.pem
              readOnly: true
      volumes:
        - name: mitm-ca
          configMap:
            name: mitm-ca
            items:
              - key: mitmproxy-ca.pem
                path: mitmproxy-ca.pem

```

## Certificate Bundle Merging

In some environments, especially when using forward or corporate proxies, you may need to add your internal CA to the default certifi trust bundle used by Python.
This ensures both public and internal certificates are trusted without disabling SSL verification.

```code
# Path to your custom CA certificate
CUSTOM_CA=/path/to/custom-ca.pem

# Locate the default certifi bundle
CERTIFI_BUNDLE=$(python -m certifi)

# Choose output path for the merged bundle
MERGED_BUNDLE=/tmp/combined-ca.pem

# Merge the two bundles
cat "$CERTIFI_BUNDLE" "$CUSTOM_CA" > "$MERGED_BUNDLE"

# Point Python SSL libraries to the merged file
export REQUESTS_CA_BUNDLE="$MERGED_BUNDLE"
export SSL_CERT_FILE="$MERGED_BUNDLE"

# (Optional) verify
python -c "import requests; print(requests.get('https://example.com').status_code)"

```

This augments the existing certifi CA bundle with your custom certificate while keeping the original file intact.