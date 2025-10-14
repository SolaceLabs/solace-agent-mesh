---
title: Installing and Configuring Agent Mesh
sidebar_position: 300
---

# Installing and Configuring Agent Mesh

Getting Agent Mesh up and running involves several key steps that prepare your development environment and configure the system for your specific needs. You'll install the framework, create your first project, configure essential settings, and connect to the language models that power your intelligent agents.

## Setting Up Your Environment

Before you can build and deploy agent meshes, you need to install the Agent Mesh framework and CLI tools on your system. The installation process includes setting up Python dependencies, configuring virtual environments, and verifying that all components work correctly. You can choose between local installation using pip or uv, or use the pre-built Docker image for containerized deployments. For complete installation instructions and system requirements, see [Installing Agent Mesh](installation.md).

## Creating Your First Project

Once you have Agent Mesh installed, you'll create and run your first project to establish a working agent mesh system. This process involves initializing a new project directory, configuring basic settings through either a web interface or command-line prompts, and starting your agent mesh with the built-in orchestrator and web gateway. The project creation process also handles essential setup tasks like environment variable configuration and component initialization. For step-by-step guidance on project creation and execution, see [Creating and Running an Agent Mesh Project](run-project.md).

## Managing System Configuration

Effective configuration management ensures consistent behavior across all components in your agent mesh deployment. The shared configuration system allows you to define common settings such as broker connections, service definitions, and environment-specific parameters in centralized files that multiple agents and gateways can reference. You'll learn how to structure configuration files, use YAML anchors for reusable settings, and manage multiple configuration environments for development, testing, and production scenarios. For comprehensive configuration guidance and best practices, see [Configuring Agent Mesh](configurations.md).

## Connecting Language Models

Language models provide the intelligence that powers your agents' reasoning, decision-making, and natural language capabilities. The system supports numerous LLM providers through a unified configuration interface, allowing you to connect with OpenAI, Anthropic, Google, Amazon, and many other services. You'll configure model-specific settings, manage API credentials securely through environment variables, and optimize model behavior for different use cases such as planning, general tasks, and specialized functions like image generation or audio transcription. For detailed provider configurations and security settings, see [Configuration Settings for LLMs](large_language_models.md).