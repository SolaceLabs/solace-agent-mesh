---
title: Vertex RAG Memory Service
sidebar_position: 340
---

# Vertex RAG Memory Service

## Overview

The Vertex RAG Memory Service provides persistent memory capabilities for agents using Google Cloud's Vertex AI RAG (Retrieval-Augmented Generation) infrastructure. This service enables agents to store and retrieve conversation history across sessions using advanced semantic search capabilities powered by Google's embedding models.

### Key Benefits

- **Semantic Search**: Find relevant past conversations using natural language queries rather than exact keyword matching
- **Scalable Storage**: Leverage Google Cloud's infrastructure for enterprise-scale memory management
- **Multi-Agent Memory**: Share memory across multiple agents within your deployment
- **Long-Term Persistence**: Conversation history persists indefinitely in Vertex AI RAG corpus

### Use Cases

- Customer support agents that need access to historical interactions
- Research assistants that build knowledge over time
- Multi-session workflows requiring context from previous conversations
- Enterprise deployments needing centralized memory management

---

## Prerequisites

### Google Cloud Setup

Before configuring the Vertex RAG memory service, ensure you have:

1. **Active Google Cloud Project** with billing enabled
2. **Vertex AI API** enabled in your project
3. **RAG Corpus Created** in Vertex AI
4. **Service Account** with appropriate IAM permissions

### Required IAM Permissions

Your service account must have the following roles:

- `roles/aiplatform.user` - Access Vertex AI services
- `roles/storage.objectAdmin` - Upload documents to RAG corpus (if using GCS backend)

### API Enablement

Enable the Vertex AI API in your Google Cloud project:

```bash
gcloud services enable aiplatform.googleapis.com
```

### Create RAG Corpus

Create a Vertex AI RAG corpus using the Google Cloud Console or gcloud CLI:

```bash
# Create a RAG corpus
gcloud ai rag corpora create \
  --display-name="agent-memory-corpus" \
  --location=us-central1 \
  --project=your-project-id
```

Note the corpus ID from the output - you'll need it for configuration.

---

## Configuration

### Basic Configuration

Add the Vertex RAG memory service to your `shared_config.yaml`:

```yaml
shared_config:
  - services:
    memory_service: &vertex_rag_memory
      type: "vertex_rag"
      rag_corpus: "projects/my-project/locations/us-central1/ragCorpora/my-corpus-id"
      similarity_top_k: 5
      vector_distance_threshold: 10
```

Then reference it in your agent configuration:

```yaml
apps:
  - name: my_agent
    app_module: solace_agent_mesh.agent.sac.app
    app_config:
      memory_service:
        <<: *vertex_rag_memory
```

### Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `type` | string | - | Must be `"vertex_rag"` to use this service |
| `rag_corpus` | string | None | Full resource name or just the corpus ID of your Vertex AI RAG corpus |
| `similarity_top_k` | integer | None | Maximum number of relevant conversation snippets to retrieve during search |
| `vector_distance_threshold` | float | 10.0 | Only return results with vector distance below this threshold |

### RAG Corpus Specification

The `rag_corpus` parameter accepts two formats:

**Full Resource Name** (recommended):
```yaml
rag_corpus: "projects/my-project/locations/us-central1/ragCorpora/1234567890"
```

**Corpus ID Only**:
```yaml
rag_corpus: "1234567890"
```

:::tip
Use the full resource name format for clarity and to avoid ambiguity when working with multiple projects.
:::

### Advanced Configuration

#### Tuning Retrieval Parameters

Adjust `similarity_top_k` and `vector_distance_threshold` based on your use case:

```yaml
memory_service:
  type: "vertex_rag"
  rag_corpus: "projects/my-project/locations/us-central1/ragCorpora/my-corpus"

  # For detailed context retrieval (more results, stricter similarity)
  similarity_top_k: 10
  vector_distance_threshold: 5.0

  # For focused retrieval (fewer results, looser similarity)
  # similarity_top_k: 3
  # vector_distance_threshold: 15.0
```

**Parameter Guidelines**:

- **similarity_top_k**:
  - Lower (3-5): Faster responses, most relevant results only
  - Higher (10-20): More comprehensive context, slower retrieval

- **vector_distance_threshold**:
  - Lower (5.0): Only highly similar conversations returned
  - Higher (15.0): More diverse results, may include less relevant content
  - Default (10.0): Balanced approach for most use cases

---

## Environment Variables

### Required Authentication

Set the Google Cloud authentication environment variable:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

### Optional Project Configuration

While not strictly required for memory service, these variables are useful when using other Google Cloud services:

```bash
export GOOGLE_CLOUD_PROJECT="your-project-id"
export GOOGLE_CLOUD_LOCATION="us-central1"
```

---

## How It Works

### Memory Storage Flow

1. **Session Events Captured**: Agent conversations are tracked as session events
2. **JSON Serialization**: Events are converted to JSON with metadata (author, timestamp, content)
3. **Document Upload**: Session data is uploaded to Vertex AI RAG corpus as text documents
4. **Embedding Generation**: Vertex AI automatically generates embeddings for semantic search
5. **Storage**: Documents are stored with display names in format: `{app_name}.{user_id}.{session_id}`

### Memory Retrieval Flow

1. **Query Submission**: Agent submits natural language query to find relevant past conversations
2. **Semantic Search**: Vertex AI performs vector similarity search across all stored sessions
3. **Filtering**: Results are filtered by app_name and user_id to ensure data isolation
4. **Ranking**: Results are ranked by vector distance (similarity score)
5. **Response**: Relevant conversation snippets are returned to the agent

---

## Usage Examples

### Example 1: Basic Agent with Memory

```yaml
apps:
  - name: customer_support_agent
    app_module: solace_agent_mesh.agent.sac.app
    app_config:
      namespace: "mycompany/prod"
      agent_name: "CustomerSupportAgent"
      instruction: "You are a helpful customer support agent with access to conversation history."

      model: "gemini-1.5-pro"

      memory_service:
        type: "vertex_rag"
        rag_corpus: "projects/myproject/locations/us-central1/ragCorpora/12345"
        similarity_top_k: 7
        vector_distance_threshold: 8.0

      session_service:
        type: "sql"
        database_url: "postgresql://user:pass@host:5432/sessions"
        default_behavior: "PERSISTENT"
```

### Example 2: Multi-Agent Memory Sharing

Configure multiple agents to share the same RAG corpus:

```yaml
shared_config:
  - services:
    # Shared memory service
    shared_memory: &shared_memory
      type: "vertex_rag"
      rag_corpus: "projects/myproject/locations/us-central1/ragCorpora/shared-corpus"
      similarity_top_k: 5

apps:
  - name: researcher_agent
    app_config:
      memory_service:
        <<: *shared_memory

  - name: analyst_agent
    app_config:
      memory_service:
        <<: *shared_memory
```

All agents will have access to conversation history across the shared corpus.

### Example 3: Environment-Specific Configuration

Use environment variables for flexible deployment:

```yaml
memory_service:
  type: "vertex_rag"
  rag_corpus: "${VERTEX_RAG_CORPUS}"
  similarity_top_k: ${VERTEX_RAG_TOP_K, 5}
  vector_distance_threshold: ${VERTEX_RAG_THRESHOLD, 10.0}
```

Set variables per environment:

```bash
# Production
export VERTEX_RAG_CORPUS="projects/prod-project/locations/us-central1/ragCorpora/prod-corpus"
export VERTEX_RAG_TOP_K=10

# Development
export VERTEX_RAG_CORPUS="projects/dev-project/locations/us-central1/ragCorpora/dev-corpus"
export VERTEX_RAG_TOP_K=3
```