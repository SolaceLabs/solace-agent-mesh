# Solace Agent Mesh - Mermaid Plugin

A plugin for the Solace Agent Mesh that generates diagrams from Mermaid.js syntax.

## Overview

This plugin provides a `draw_mermaid_diagram` tool that allows an agent to generate PNG diagrams by sending Mermaid syntax to a running `mermaid-server` instance.

## Installation
To install the SAM Mermaid plugin, run the following command in your SAM project directory:

```bash
solace-agent-mesh plugin add <your-new-component-name> --plugin sam-mermaid
```
This will create a new component configuration at `configs/plugins/<your-new-component-name-kebab-case>.yaml`.

## Configuration

To use this plugin, you need to configure an agent and provide the URL of your `mermaid-server`.

**Set Environment Variable**:
    You must set the `MERMAID_SERVER_URL` environment variable to point to your running instance of [mermaid-server](https://github.com/TomWright/mermaid-server).

```bash
export MERMAID_SERVER_URL="http://localhost:8080"
```


## Usage

Once the agent is configured and running, you can ask it to draw diagrams.

**Example Prompt:**

"Draw a flowchart for a simple login process."

The LLM will then call the `draw_mermaid_diagram` tool with the appropriate Mermaid syntax, and the tool will generate a PNG image artifact.