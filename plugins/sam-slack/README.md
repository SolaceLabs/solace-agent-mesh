# Slack SAM Plugin

This plugin allows you to interact with Slack channels and messages through the Solace Agent Mesh framework. It provides a way to send and receive messages and handle events from Slack.

## Installation

Once the plugin is installed (e.g., from PyPI or a local wheel file):
```bash
sam plugin add <your-new-component-name> --plugin sam-slack
```
This will create a new component configuration at `configs/plugins/<your-new-component-name-kebab-case>.yaml`.