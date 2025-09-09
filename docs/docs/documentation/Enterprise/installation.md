---
title: Installation
sidebar_position: 5
---

:::info [warning]
This linked docker image MUST NOT be run on any machine other than that of a Solace employee. 
Solace does not yet have a formal licensing agreement process fleshed out to safely share SAM Enterprise images with customers and/or install and run them in a customer environment
:::

## Prepare the Enterprise Image

Download the latest enterprise docker image .tar from from the Solace Product Portal.

Load the image using Docker with the following command. Note this may take some time due to image size.  

```bash
docker load -i solace-agent-mesh-enterprise-<tag>.tar
```

Once loaded, you can verify the image locally using the following command:

```bash
docker images
```

## Run the Enterprise Image

Execute the following command:

```bash
docker run -itd -p 8000:8000 \
  -e LLM_SERVICE_API_KEY="<YOUR_LLM_TOKEN>" \
  -e LLM_SERVICE_ENDPOINT="<YOUR_LLM_SERVICE_ENDPOINT>" \
  -e LLM_SERVICE_PLANNING_MODEL_NAME="<YOUR_MODEL_NAME>" \
  -e LLM_SERVICE_GENERAL_MODEL_NAME="<YOUR_MODEL_NAME>" \
  -e NAMESPACE="<YOUR_NAMESPACE>" \
  -e SOLACE_DEV_MODE="true" \
solace-agent-mesh-enterprise:<tag>
```
