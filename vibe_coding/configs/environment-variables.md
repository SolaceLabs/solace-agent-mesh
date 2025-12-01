# Environment Variables

Complete reference of environment variables used in Agent Mesh.

## Core Variables

```bash
# Namespace
export NAMESPACE="myorg/prod"

# Solace Broker
export SOLACE_BROKER_URL="tcp://localhost:55555"
export SOLACE_BROKER_USERNAME="default"
export SOLACE_BROKER_PASSWORD="default"
export SOLACE_BROKER_VPN="default"
```

## LLM Providers

```bash
# OpenAI
export OPENAI_API_KEY="sk-..."

# Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."

# Google Gemini
export GEMINI_API_KEY="..."

# AWS Bedrock
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_REGION="us-west-2"
```

## Storage

```bash
# Database
export DATABASE_URL="postgresql://user:pass@localhost:5432/db"

# S3
export S3_BUCKET_NAME="my-bucket"
export AWS_REGION="us-west-2"

# Google Cloud
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
export GCS_BUCKET_NAME="my-bucket"
```

## Gateway

```bash
# WebUI
export WEBUI_SESSION_SECRET_KEY="your-secret-key"

# Logging
export LOGGING_CONFIG_PATH="configs/logging_config.yaml"
```

## Related Documentation

- [Shared Configuration](./shared-configuration.md)
- [Broker Configuration](./broker-configuration.md)
- [Model Configuration](./model-configuration.md)
- [Service Configuration](./service-configuration.md)
