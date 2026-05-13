---
title: Model Configurations
sidebar_position: 330
---

# Model Configurations

Model Configurations provide a centralized management layer for all large language model (LLM) configurations used across your Agent Mesh deployment. Instead of scattering model credentials and settings across individual agent YAML files, Model Configurations let you define, manage, and share model setups from a single location in the Agent Mesh UI.

This approach gives your organization a clear picture of which models are in use, how they are configured, and which agents depend on them, making it easier to audit, rotate credentials, and standardize model usage across teams.

## Why Model Configurations

In a typical Agent Mesh deployment, multiple agents each need access to LLMs. Without centralized management, teams end up duplicating API keys across YAML files, losing track of which models are deployed where, and facing inconsistent configurations between agents. Model Configurations solve these problems by establishing a single source of truth for all model settings.

Benefits include:

- **Centralized credential management** - Store API keys, OAuth credentials, and cloud provider credentials in one place rather than duplicating them across agent configurations
- **Visibility** - See all configured models, their providers, and which agents use them from the UI
- **Consistency** - Ensure agents use the same model versions and parameters across your deployment
- **Simplified agent development** - Agent developers reference a model by its alias rather than managing credentials directly

## Default Models

Agent Mesh includes the following default model configurations:

### General Model

The **general** model is the default LLM used by backend services and agents that require language model capabilities. When an agent needs to reason about input, generate responses, or perform any standard LLM task, it uses the general model unless explicitly configured otherwise.

We recommend choosing a capable, well-rounded LLM that balances performance with cost for the general model. It handles the bulk of day-to-day LLM interactions across your deployment.

### Planning Model

The **planning** model is specifically used by the orchestrator, which is responsible for analyzing user requests, determining which agents to invoke, in what order, and how to combine their outputs into a coherent response. This requires more sophisticated reasoning and planning capabilities than typical agent tasks. For more information, see [Orchestrator](../components/orchestrator.md).

The planning model is separated from the general model because orchestration demands a higher level of multi-step reasoning, tool selection logic, and task decomposition. Organizations may choose to use a more capable (and potentially more expensive) model for planning while using a cost-effective model for general agent tasks.

:::info
You cannot rename or delete the default models (**general** and **planning**). They are system-level configurations that the platform depends on. You can, however, change the underlying provider, model, credentials, and parameters for each.
:::

## Initial Setup

When no model configurations have been created, the platform prompts you to set up your default models. A setup dialog appears on first use, guiding you to configure the **general** and **planning** models so that core AI features—such as chatting with AI, agent creation, and orchestration—can function properly.

If you choose to skip the setup initially, a warning banner appears across the platform indicating that no models have been configured and some features may not work as intended. You can complete the setup at any time by navigating to **Agent Mesh > Models** and creating the general and planning model configurations.

:::note
Users without administrator write permissions see a message advising them to contact an administrator to configure models.
:::

## Supported Providers

Model Configurations support the following LLM providers through the UI:

| Provider | Description | Authentication |
|----------|-------------|----------------|
| OpenAI | GPT models via OpenAI API | API Key |
| Anthropic | Claude models via Anthropic API | API Key |
| Azure OpenAI | OpenAI models hosted on Azure infrastructure | API Key, OAuth2 |
| Google AI Studio | Gemini models via Google API | API Key |
| Google Vertex AI | Models via Google Cloud Vertex AI platform | GCP Service Account |
| Amazon Bedrock | Foundation models via AWS Bedrock | AWS IAM |
| Ollama | Locally hosted open-source models | API Key, None |
| Custom | Any provider implementing the OpenAI-compatible API protocol | API Key, OAuth2, None |

### The Custom Provider

The **Custom** provider is designed for any LLM endpoint that implements the OpenAI-compatible API protocol. This includes services like Mistral, Groq, OpenRouter, Together AI, and self-hosted inference servers.

When using the Custom provider:
- Provide the API base URL of your endpoint
- The model name is automatically prefixed with `openai/` if no prefix is present, telling LiteLLM to use the OpenAI-compatible request format
- Authentication can be API Key, OAuth2, or None depending on your endpoint

For example, to connect to Groq:
- **Provider**: Custom
- **API Base**: `https://api.groq.com/openai/v1`
- **Model Name**: `openai/llama-3.3-70b-versatile`
- **Auth Type**: API Key

## Creating a Model Configuration

To create a new model configuration from the UI:

1. From Agent Mesh, navigate to **Models**
2. Click **Add Model**
3. Fill in the configuration form:

| Field | Required | Description |
|-------|----------|-------------|
| **Display Name** | Yes | A unique alias used to reference this model (such as `coding-model` or `claude-fast`) |
| **Description** | Yes | A human-readable description of what this model is used for |
| **Model Provider** | Yes | Select from the supported providers list |
| **API Base URL** | Varies | Required for Azure OpenAI, Ollama, and Custom providers |
| **Authentication Type** | Yes | The authentication method for the provider |
| **Auth Credentials** | Varies | Provider-specific credentials (API key, OAuth2 settings, AWS IAM, and so on) |
| **Model Name** | Yes | The specific model to use. The drop-down list fetches available models from the provider using your credentials. If the fetch fails, you can type the model name manually |
| **Max Input Tokens** | No | The model's maximum input token limit. Drives the chat context-usage indicator shown below the chat input. Check the model provider's documentation for the current value for this model version. Leave blank to fall back to the agent's `shared_config.yaml` value, then to the platform's built-in model registry for well-known models |

4. Optionally expand **Advanced Settings** to configure:

| Parameter | Description | Default |
|-----------|-------------|---------|
| **Temperature** | Controls randomness in responses (0-2). Lower values produce more deterministic output | Provider default |
| **Max Tokens** | Maximum number of tokens in the response | Provider default |
| **Prompt Caching Strategy** | Controls how system prompts and tool definitions are cached across LLM requests to reduce costs and latency. Cached content is reused by the provider instead of being reprocessed on each request. Options: **5 minutes** (short-lived cache), **1 hour** (extended cache), or **Disabled** (no caching). Not all providers support prompt caching—when unsupported, this setting is ignored | 5 minutes |

   You can also add **vendor-specific LLM parameters** as custom key-value pairs. These are passed directly to the provider's API, allowing you to configure provider-specific options not covered by the preceding common settings (such as `top_p`, `frequency_penalty`, and `seed`). For available parameters, see your provider's API documentation.

5. Use **Test Connection** to verify your credentials and model access before saving
6. Click **Save** to create the configuration

## Viewing, Editing, and Deleting Models

### Viewing Details

Click any model in the Models list to view its details. This shows the model's current configuration including provider, authentication type, and advanced settings.

### Editing

To edit a model, either use the context menu on the model card or click the **Edit** button at the top when viewing model details. All fields can be modified except the display name of the two default models (general and planning).

After saving changes, any agents using this model configuration automatically receive the updated settings through the platform's dynamic configuration system.

### Deleting

To delete a model configuration, select **Delete** from the context menu on the model card. Deleting a model has the following impact on dependent agents:

- **Code-based agents** that reference the deleted model will no longer function correctly
- **Agents managed by the platform** (such as agents created through Agent Builder) will be undeployed and moved to an inactive state

:::warning
The **general** and **planning** default models cannot be deleted. They are required for core platform functionality.
:::

## Using Model Configurations in Agents

### Agent Builder Agents

Agents created through the Agent Builder UI automatically use Model Configurations. When you create or edit an agent in the Agent Builder, you select a model configuration by its alias. The agent dynamically retrieves the full model credentials and parameters from the platform at runtime.

### YAML-Based Agents (Pro Code)

For agents defined in YAML configuration files, you can opt into Model Configurations by using the `model_provider` field instead of the traditional `model` field.

#### The `model` Field (Traditional Approach)

The `model` field accepts either a YAML anchor reference or an inline dictionary containing all LLM settings directly in the agent configuration:

```yaml
# Using a YAML anchor from shared_config.yaml
app_config:
  model: *general_model

# Or inline configuration
app_config:
  model:
    model: gpt-4o
    api_base: https://api.openai.com/v1
    api_key: ${OPENAI_API_KEY}
    temperature: 0.1
```

This approach embeds credentials directly in the YAML (typically via environment variables). It works well for simple deployments but requires managing credentials across multiple files.

#### The `model_provider` Field (Dynamic Approach)

The `model_provider` field references a model configuration stored in the platform. The agent retrieves the full configuration at runtime. You can reference a model by either its **alias** or its **model ID**:

```yaml
# Using the alias
app_config:
  model_provider:
    - general

# Using the model ID (preferred)
app_config:
  model_provider:
    - abc123-def456
```

:::tip
Using the **model ID** is preferred over the alias. If the model's display name (alias) is changed later, agents referencing the alias will break, while agents referencing the model ID will continue to work.
:::

To switch a YAML agent from inline model configuration to using Model Configurations:

1. Create the model configuration in the UI with an alias (such as `fast-model`)
2. Replace the `model` field in your agent YAML with `model_provider`:

```yaml
# Before: inline model config
app_config:
  model:
    model: gpt-4o
    api_key: ${OPENAI_API_KEY}

# After: referencing a Model Configuration
app_config:
  model_provider:
    - fast-model
```

:::info
The `model_provider` field accepts an alias or model ID in a form of a list. When `model_provider` is present, it takes precedence over the `model` field.
:::

#### Key Differences: `model` vs `model_provider`

| Aspect | `model` | `model_provider` |
|--------|---------|-------------------|
| **Configuration source** | Inline YAML or YAML anchor | Platform database (via UI) |
| **Credential management** | Environment variables in YAML | Centralized in the UI |
| **Runtime behavior** | Resolved at startup from env vars | Dynamically fetched from platform service |
| **Configuration updates** | Requires redeployment | Agents receive updates automatically |
| **Best for** | Simple deployments, CI/CD pipelines | Multi-agent deployments, teams, credential rotation |

## Context Usage Indicator

The chat UI shows a per-session context-usage indicator below the chat input. It tracks how much of the model's context window has been consumed by the current session and helps users anticipate when auto-compaction will kick in or decide when to compact/compress manually.

The indicator is only rendered when the model's context window is known. The platform resolves the limit in the following order:

1. **Model Configuration** — the `Max Input Tokens` value set in the Models UI, matched first by model name, then by alias.
2. **Agent-reported value** — if the agent's model configuration in `shared_config.yaml` sets `max_input_tokens`, that value is stamped on each completed task and used when no UI override exists:

   ```yaml
   planning: &planning_model
     model: ${LLM_SERVICE_PLANNING_MODEL_NAME}
     api_base: ${LLM_SERVICE_ENDPOINT}
     api_key: ${LLM_SERVICE_API_KEY}
     max_tokens: 32000
     max_input_tokens: 200000  # surfaces on the context-usage indicator
   ```

3. **Built-in model registry** — for well-known models, the platform's model-info lookup provides the context window automatically.

If none of these resolve, the indicator is hidden rather than displayed against a guessed limit. Set `Max Input Tokens` explicitly in the Models UI whenever you connect a Custom provider or a model the registry does not recognize, and check the provider's documentation for the current value — providers publish this per model and can change it over time.

## Next Steps

- For details on LLM provider configuration options and prompt caching, see [Configuring LLMs](./large_language_models.md)
- For information about shared configuration and YAML anchors, see [Configuring Agent Mesh](./configurations.md)
- To learn about building agents, see [Creating Agents](../developing/create-agents.md)
