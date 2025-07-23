# Bedrock Agent SAM Plugin

The Amazon Bedrock Agent allows you to import one or multiple Amazon Bedrock agents or flows as actions to be used in your SAM project. This is useful for integrating with Amazon Bedrock's capabilities directly into your Solace Agent Mesh (SAM) project.

## Installation

Run the following command in your SAM project directory to add the Amazon Bedrock Agent plugin:

```bash
solace-agent-mesh plugin add <your-new-component-name> --plugin sam-bedrock-agent
```

This will create a new component configuration at `configs/plugins/<your-new-component-name-kebab-case>.yaml`.

## Configuration

There is 2 sections in the configuration file that must be updated.

Section one, indicated by `# 1. UPDATE REQUIRED - START #`, contains the configuration for the Amazon Bedrock Agent/Flow and the internal configuration for the Agent.


Section two, indicated by `# 2. UPDATE REQUIRED - START #`, contains the configuration for the public facing API of the Agent which will be used by other agents to interact with it.