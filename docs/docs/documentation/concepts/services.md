---
title: Services
sidebar_position: 50
---

# Services

Solace Agent Mesh comes with a series of built-in system-wide services that provide essential capabilities for the system to operate efficiently and securely. These services are designed to be used by all or specific components within the system to perform common tasks such as file management, history management, LLM handling, and more.

:::tip[In one sentence]
Services are essentially system-wide task specific capabilities.
:::

Some services are extensible and the user can implement their own version by extending the base service classes.

## File Service

The File service is a global service that provides short-term file storage capabilities for Solace Agent Mesh. This service enables efficient handling of large files within the system without overloading the PubSub+ event broker or the LLM context.

For more information, see [File Service](../user-guide/advanced/services/file-service.md).

## History Service

The History service is a global service that provides flexible memory storage capabilities for Solace Agent Mesh. This service enables components to store and retrieve session histories, and the system's internal states.

For more information, see [History Service](../user-guide/advanced/services/history-service.md).

## LLM Service

The LLM service is a global service that provides access to large language models (LLMs) for Solace Agent Mesh. This service encapsulates all the configuration and management of LLMs, allowing components to focus on using the models for generating responses.

For more information, see [LLM Service](../user-guide/advanced/services/llm-service.md).

## Embedding Service

The Embedding service is a global service that provides access to text/image/multi-modal embeddings models for Solace Agent Mesh. This service encapsulates all the configuration and management of embeddings, allowing components to focus on using the models for generating responses.

For more information, see [Embedding Service](../user-guide/advanced/services/embedding-service.md).
