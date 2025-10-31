---
title: RAG Integration
sidebar_position: 70
toc_max_heading_level: 4
---

# RAG Integration

This tutorial guides you through setting up and configuring Agent Mesh Retrieval Augmented Generation (RAG) plugin. The RAG plugin enables your agents to answer questions by retrieving information from a knowledge base of your documents.

## What is Agent Mesh RAG?

The Agent Mesh RAG plugin enhances your agents with the ability to perform retrieval-augmented generation. This means the agent can:
- **Scan** documents from various sources (local filesystem, Google Drive, etc.).
- **Preprocess** and **split** the text into manageable chunks.
- **Embed** these chunks into vectors and store them in a vector database.
- **Retrieve** relevant chunks of text based on a user's query.
- **Generate** an answer using a large language model (LLM) augmented with the retrieved information.

This allows you to build agents that can answer questions about your own private data.

## Prerequisites

Before you begin, ensure you have:
- [Installed Agent Mesh and the Agent Mesh CLI](../../installing-and-configuring/installation.md).
- [Created a new Agent Mesh project](../../installing-and-configuring/run-project.md).
- Access to a vector database (for example, Qdrant, Chroma, and Pinecone).
- Access to an LLM for generation and an embedding model.
- A directory with some documents for the agent to ingest.

## Adding the RAG Plugin

To add the RAG plugin to your Agent Mesh project, run the following command:

```sh
sam plugin add my-rag-agent --plugin sam-rag
```

Replace `my-rag-agent` with your preferred agent name. This command:
- Installs the `sam-rag` plugin.
- Creates a new agent configuration file at `configs/agents/my-rag-agent.yaml`.

## Configuring the RAG Agent

The RAG agent requires a detailed configuration. Open `configs/agents/my-rag-agent.yaml` to configure the following sections:

### Shared Configuration

Like other agents, the RAG agent needs a connection to the Solace broker and a configured LLM. This is typically done in a `shared_config.yaml` file.

```yaml
# configs/shared_config.yaml
shared_config:
  - broker_connection: &broker_connection
      dev_mode: ${SOLACE_DEV_MODE, false}
      broker_url: ${SOLACE_BROKER_URL, ws://localhost:8008}
      broker_username: ${SOLACE_BROKER_USERNAME, default}
      broker_password: ${SOLACE_BROKER_PASSWORD, default}
      broker_vpn: ${SOLACE_BROKER_VPN, default}
      temporary_queue: ${USE_TEMPORARY_QUEUES, true}

  - models:
    general: &general_model
      model: ${LLM_SERVICE_GENERAL_MODEL_NAME}
      api_base: ${LLM_SERVICE_ENDPOINT}
      api_key: ${LLM_SERVICE_API_KEY}
```

### RAG Pipeline Configuration

The RAG pipeline has several stages, each with its own configuration block within the `app_config` section of your `my-rag-agent.yaml` file.

#### 1. Scanner Configuration

The scanner discovers documents to be ingested. You can configure it to scan a local filesystem or cloud sources.

**Local Filesystem Example:**
```yaml
scanner:
  batch: true
  use_memory_storage: true
  source:
    type: filesystem
    directories:
      - "/path/to/your/documents" # Important: Replace with your actual document directory path
    filters:
      file_formats:
        - ".txt"
        - ".pdf"
        - ".md"
```

**Multi-Cloud Source Example:**
You can also configure multiple sources, including Google Drive, OneDrive, and S3.
```yaml
scanner:
  batch: true
  use_memory_storage: true
  sources:
    - type: filesystem
      directories: ["${LOCAL_DOCUMENTS_PATH}"]
    - type: google_drive
      credentials_path: "${GOOGLE_DRIVE_CREDENTIALS_PATH}"
      folders:
        - folder_id: "${GOOGLE_DRIVE_FOLDER_ID_1}"
          name: "Documents"
          recursive: true
```

#### 2. Preprocessor Configuration

The preprocessor cleans the text extracted from documents.
```yaml
preprocessor:
  default_preprocessor:
    type: enhanced
    params:
      lowercase: true
      normalize_whitespace: true
      remove_urls: true
  preprocessors:
    pdf: 
      type: document
      params:
        lowercase: true
        normalize_whitespace: true
        remove_non_ascii: true
        remove_urls: true
```

#### 3. Splitter Configuration

The splitter breaks down large documents into smaller chunks. Different splitters are available for different file types.
```yaml
splitter:
  default_splitter:
    type: recursive_character
    params:
      chunk_size: 2048
      chunk_overlap: 400
  splitters:
    markdown:
      type: markdown
      params:
        chunk_size: 2048
        chunk_overlap: 400
    pdf:
      type: token
      params:
        chunk_size: 500
        chunk_overlap: 100
```

#### 4. Embedding Configuration

This section defines the model used to create vector embeddings from the text chunks.
```yaml
embedding:
  embedder_type: "openai"
  embedder_params:
    model: "${OPENAI_EMBEDDING_MODEL}"
    api_key: "${OPENAI_API_KEY}"
    api_base: "${OPENAI_API_ENDPOINT}"
  normalize_embeddings: true
```

#### 5. Vector Database Configuration

Configure the connection to your vector database where the embeddings are stored.

**Qdrant Example:**
```yaml
vector_db:
  db_type: "qdrant"
  db_params:
    url: "${QDRANT_URL}"
    api_key: "${QDRANT_API_KEY}"
    collection_name: "${QDRANT_COLLECTION}"
    embedding_dimension: ${QDRANT_EMBEDDING_DIMENSION}
```

**Chroma Example:**
```yaml
vector_db:
  db_type: "chroma"
  db_params:
    host: "${CHROMA_HOST}"
    port: "${CHROMA_PORT}"
    collection_name: "${CHROMA_COLLECTION}"
```

#### 6. LLM Configuration

Configure the LLM that is used to generate answers based on the retrieved context.
```yaml
llm:
  load_balancer:
    - model_name: "gpt-4o"
      litellm_params:
        model: "openai/${OPENAI_MODEL_NAME}"
        api_key: "${OPENAI_API_KEY}"
        api_base: "${OPENAI_API_ENDPOINT}"
```

#### 7. Retrieval Configuration

This defines how many document chunks are retrieved to answer a query.
```yaml
retrieval:
  top_k: 7
```

### Environment Variables

The RAG agent relies heavily on environment variables. Here are some of the most important ones you'll need to set in your `.env` file:

```bash
# Solace Connection
SOLACE_BROKER_URL=ws://localhost:8008
SOLACE_BROKER_VPN=default
SOLACE_BROKER_USERNAME=default
SOLACE_BROKER_PASSWORD=default
NAMESPACE=my-org/dev

# LLM and Embedding Models
OPENAI_API_KEY="your-openai-api-key"
OPENAI_API_ENDPOINT="your-openai-api-endpoint"
OPENAI_MODEL_NAME="model name. E.g., gpt-4o"
OPENAI_EMBEDDING_MODEL="embedding model name. E.g., text-embedding-3-small"

# Vector Database (Qdrant example)
QDRANT_URL="Qdrant url"
QDRANT_API_KEY="API key"
QDRANT_COLLECTION="my-rag-collection"
QDRANT_EMBEDDING_DIMENSION=1536 # Depends on your embedding model

# Scanner
DOCUMENTS_PATH="./my_documents" # Relative path to your documents folder
```

Create a directory named `my_documents` in your project root and place some text or markdown files inside it.

## Running the RAG Agent

Once you have configured your agent and set the environment variables, you can run it:

```sh
sam run configs/agents/my-rag-agent.yaml
```

When the agent starts, it begins scanning the documents in the configured source, processing and ingesting them into your vector database. This process may take some time, depending on the number and size of your documents.

## Testing the RAG Agent

Once your agent is running, you can test its retrieval capabilities and ingest new documents.

### Ingesting Documents

There are two primary ways to ingest documents into your RAG agent's knowledge base:

#### Option 1: Automatic Scanning (Batch Ingestion)

This method uses the configured `scanner` component. The agent automatically ingests documents from the directories specified in your configuration upon startup.

**Step 1: Create a Document**

First, create a simple text file named `sam_features.txt` and add some content to it. For example:

```text
Agent Mesh is a powerful framework for building AI agents.
Key features of Agent Mesh include:
- A flexible plugin architecture.
- Integration with various LLMs and vector databases.
- Scalable gateways for different communication protocols.
- An event-driven design based on Solace event broker.
```

**Step 2: Place the Document in the Scanned Directory**

In the "Environment Variables" section, we configured `LOCAL_DOCUMENTS_PATH` to point to a directory (e.g., `./my_documents`).

Create this directory in your project's root folder if you haven't already, and move your `sam_features.txt` file into it.

```sh
mkdir -p my_documents
mv sam_features.txt my_documents/
```

**Step 3: Run the Agent to Trigger Ingestion**

If your agent is already running, you'll need to restart it to trigger the batch scan. If it's not running, start it now:

```sh
sam run configs/agents/my-rag-agent.yaml
```

You will see logs indicating that the file is being processed. Once the agent is running and the initial scan is complete, the document is successfully ingested and ready for retrieval.

#### Option 2: Manual Upload via Gateway

You can also ingest documents dynamically by uploading them directly through a gateway, like the Web UI. This is useful for adding single documents without restarting the agent. The RAG agent exposes a tool for this purpose.

**Step 1: Start the RAG Agent and Web UI**

Ensure both your RAG agent and the Web UI gateway are running.

**Step 2: Upload a Document in the Web UI**

1.  Open the Web UI (usually at http://localhost:8000, or check your gateway configuration for the correct URL) and start a chat with your RAG agent.
2.  Use the file attachment button to select a document from your local machine.
3.  Send a prompt along with the file, instructing the agent to ingest it. For example:
    > "Please ingest the attached document into your knowledge base."

The RAG agent uses its `built-in` ingest_document tool to process the file you uploaded. The file goes through the same preprocessing, splitting, and embedding pipeline as the documents from the automatic scan.

**Step 3: Confirm Ingestion**

After the agent confirms that the document has been ingested, you can immediately ask questions about its content.


### Querying the Knowledge Base

You can interact with your RAG agent through any gateway, such as the Web UI gateway.

1.  Make sure you have a Web UI gateway running (or add one to your project).
2.  Open the Web UI (usually at `http://localhost:8000`).
3.  Start a conversation with `my-rag-agent`.
4.  Ask a question related to the content of the documents you provided during the initial scan.

For example, if you have a document about product features, you could ask:
> "What are the key features of Product X?"

The agent searches its knowledge base, finds the relevant information, and generates an answer based on the content of your documents.

## Troubleshooting

- **Connection Errors**: Double-check all your URLs, API keys, and credentials for your LLM and vector database.
- **Ingestion Issues**: Check the agent logs for errors during the scanning, preprocessing, or embedding stages. Ensure the file formats are supported and the paths are correct.
- **No Answers**: If the agent can't answer, it might be because the information is not in the documents, or the `top_k` retrieval setting is too low.
