---
title: Installation
sidebar_position: 5
---

## Prepare the Enterprise Image

Download the latest enterprise docker image tarball from the [Solace Product Portal](https://products.solace.com/).

Load the image using Docker with the following command.

```bash
docker load -i solace-agent-mesh-enterprise-<tag>.tar
```

Once loaded, you can verify the image locally using the following command:

```bash
docker images
```

## Running Solace Agent Mesh Enterprise

Here are two examples of Docker run commands for both a development use case as well as a production use case:

:::tip
You may need to include `--platform linux/amd64` depending on the host machine you’re using.
:::

### Development Use Case

```bash
docker run -itd -p 8000:8000 \
  -e LLM_SERVICE_API_KEY="<YOUR_LLM_TOKEN>" \
  -e LLM_SERVICE_ENDPOINT="<YOUR_LLM_SERVICE_ENDPOINT>" \
  -e LLM_SERVICE_PLANNING_MODEL_NAME="<YOUR_MODEL_NAME>" \
  -e LLM_SERVICE_GENERAL_MODEL_NAME="<YOUR_MODEL_NAME>" \
  -e NAMESPACE="<YOUR_NAMESPACE>" \
  -e SOLACE_DEV_MODE="true" \
  --name sam-ent-dev \
solace-agent-mesh-enterprise:<tag>
```

### Production Use Case

```bash
docker run -itd -p 8000:8000 \
  -e LLM_SERVICE_API_KEY="<YOUR_LLM_TOKEN>" \
  -e LLM_SERVICE_ENDPOINT="<YOUR_LLM_SERVICE_ENDPOINT>" \
  -e LLM_SERVICE_PLANNING_MODEL_NAME="<YOUR_MODEL_NAME>" \
  -e LLM_SERVICE_GENERAL_MODEL_NAME="<YOUR_MODEL_NAME>" \
  -e NAMESPACE="<YOUR_NAMESPACE>" \
  -e SOLACE_DEV_MODE="false" \
  -e SOLACE_BROKER_URL="<YOUR_BROKER_URL>" \
  -e SOLACE_BROKER_VPN="<YOUR_BROKER_VPN>" \
  -e SOLACE_BROKER_USERNAME="<YOUR_BROKER_USERNAME>" \
  -e SOLACE_BROKER_PASSWORD="<YOUR_BROKER_PASSWORD>" \
  --name sam-ent-prod \
solace-agent-mesh-enterprise:<tag>
```

You can then access Solace Agent Mesh Enterprise UI through http://localhost:8000
