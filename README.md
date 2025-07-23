<p align="center">
  <img src="./docs/static/img/logo.png" alt="Solace Agent Mesh Logo" width="100"/>
</p>
<h2 align="center">
  Solace Agent Mesh
</h2>
<h3 align="center">Open-source framework for building event driven multi-agent AI systems</h3>
<h5 align="center">Star ⭐️ this repo to stay updated as we ship new features and improvements.</h5>

<p align="center">
  <a href="https://github.com/SolaceLabs/solace-agent-mesh/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/SolaceLabs/solace-agent-mesh" alt="License">
  </a>
  <a href="https://pypi.org/project/solace-agent-mesh">
    <img src="https://img.shields.io/pypi/v/solace-agent-mesh.svg" alt="PyPI - Version">
  </a>
  <a href="https://pypi.org/project/solace-agent-mesh">
    <img src="https://img.shields.io/pypi/pyversions/solace-agent-mesh.svg" alt="PyPI - Python Version">
  </a>
  <a href="https://pypi.org/project/solace-agent-mesh">
      <img alt="PyPI - Downloads" src="https://img.shields.io/pypi/dm/solace-agent-mesh?color=00C895">
  </a>
</p>
<p align="center">
  <a href="#-key-features">Key Features</a> •
  <a href="#-quick-start-5-minutes">Quickstart</a> •
  <a href="#️-next-steps">Next Steps</a>
</p>

---

The Solace Agent Mesh transforms how AI agents work together, creating a dynamic ecosystem where specialized agents communicate seamlessly, share information, and collaborate on complex tasks.

Built on Solace PubSub+ Event Broker, this framework provides a robust foundation for enterprise-grade AI solutions that scale effortlessly. The mesh creates a standardized communication layer where AI agents can:

* Delegate specialized tasks to peer agents
* Share artifacts and data across the network
* Connect with diverse user interfaces and external systems
* Execute complex, multi-step workflows with minimal coupling

Under the hood, the framework combines the Solace AI Connector (SAC) for runtime orchestration with Google's Agent Development Kit (ADK) for agent logic, LLM interaction, and tool execution—all communicating via the A2A protocol over Solace's event mesh. The result? A fully asynchronous, event-driven, and decoupled AI agent architecture ready for enterprise deployment.

---

## ✨ Key Features 
- ⚙️ **[Modular, Event-Driven Architecture](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/getting-started/component-overview)** – All components communicate via events through a central event mesh, enabling loose coupling and high scalability.
- 🤖 **[Composable Agents](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/concepts/agents)** – Combine specialized AI agents to solve complex, multi-step workflows.
- 🌐 **[Flexible Interfaces](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/concepts/gateways)** – Interact with SAM via the REST API, browser UI, [Slack](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/tutorials/slack-integration), etc.
- 🧠 **[Orchestration Agent](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/concepts/orchestrator)** – Tasks are automatically broken down and delegated across agents by the orchestrator agent.
- 🧩 **[Plugin-Extensible](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/concepts/plugins)** – Add your own agents, gateways, or services with minimal boilerplate.
- 🏢 **[Production-Ready](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/deployment/deploy)** – Backed by [Solace's enterprise-grade event broker](https://solace.com/products/event-broker/) for reliability and performance.
- 📁 **[File Management](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/user-guide/builtin-tools/artifact-management)** – Built-in tools for managing file artifacts with automatic metadata injection and artifact handling.
- 📊 **[Data Analysis Tools](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/user-guide/builtin-tools/data-analysis-tools)** – Built-in tools for SQL queries, JQ transformations, and Plotly chart generation.
- 🔗 **[Dynamic Embeds](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/user-guide/builtin-tools/embeds)** – Include dynamic placeholders in responses that are resolved by the framework with support for modifier chains.
- 🤝 **[Agent-to-Agent Communication](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/concepts/architecture)** – Agents can discover and delegate tasks to peer agents using the A2A protocol over Solace.

---

## 🚀 Quick Start (5 minutes)

Set up Solace Agent Mesh in just a few steps.

### ⚙️ System Requirements

To run Solace Agent Mesh locally, you'll need:

- **Python 3.10.16+**
- **pip** (comes with Python)
- **OS**: MacOS, Linux, or Windows (with [WSL](https://learn.microsoft.com/en-us/windows/wsl/))
- **LLM API key** (any major provider or custom endpoint)

### 💻 Setup Steps

```bash
# 1. (Optional) Create and activate a Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install the Solace Agent Mesh
pip install solace-agent-mesh

# 3. Initialize a new project with web-based setup
mkdir my-agent-mesh && cd my-agent-mesh
sam init --gui

# 4. Run the project
sam run
```

### 🔧 Adding Agents

```bash
# Add a new agent with GUI interface
sam add agent --gui
```

Or install an existing plugin:

```bash
sam plugin add <your-component-name> --plugin <plugin-name>
```

#### Once running:

Open the Web UI at [http://localhost:8000](http://localhost:8000) to talk with a chat interface.

---

## 🏗️ Architecture Overview

Solace Agent Mesh provides a "Universal A2A Agent Host," a flexible and configurable runtime environment built by integrating Google's Agent Development Kit (ADK) with the Solace AI Connector (SAC) framework.

The system allows you to:

- Host AI agents developed with Google ADK within the SAC framework
- Define agent capabilities (LLM model, instructions, tools) primarily through SAC YAML configuration
- Utilize Solace PubSub+ as the transport for standard Agent-to-Agent (A2A) protocol communication
- Enable dynamic discovery of peer agents running within the same ecosystem
- Allow agents to delegate tasks to discovered peers via the A2A protocol over Solace
- Manage file artifacts using built-in tools with automatic metadata injection
- Perform data analysis using built-in SQL, JQ, and visualization tools
- Use dynamic embeds for context-dependent information resolution

### Key Components

- **SAC** handles broker connections, configuration loading, and component lifecycle
- **ADK** provides the agent runtime, LLM interaction, tool execution, and state management
- **A2A Protocol** enables communication between clients and agents, and between peer agents
- **Dynamic Embeds** allow placeholders in responses that are resolved with context-dependent information
- **File Management** provides built-in tools for artifact creation, listing, loading, and metadata handling

---

## ➡️ Next Steps

Want to go further? Here are some hands-on tutorials to help you get started:

| 🔧 Integration | ⏱️ Est. Time | 📘 Tutorial |
|----------------|--------------|-------------|
| 🌤️ **Weather Agent**<br>Learn how to build an agent that gives Solace Agent Mesh  the ability to access real-time weather information.  | **~15 min** | [Weather Agent Plugin](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/tutorials/custom-agent) |
| 🗃️ **SQL Database Integration**<br>Enable Solace Agent Mesh to answer company-specific questions using a sample coffee company database.| **~10–15 min** | [SQL Database Tutorial](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/tutorials/sql-database) |
| 🧠 **MCP Integration**<br>Integrating a Model Context Protocol (MCP) Servers into Solace Agent Mesh. | **~10–15 min** | [MCP Integration Tutorial](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/tutorials/mcp-integration) |
| 💬 **Slack Integration**<br>Chat with Solace Agent Mesh directly from Slack. | **~20–30 min** | [Slack Integration Tutorial](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/tutorials/slack-integration) |

📚 Want to explore more? Check out the full [Solace Agent Mesh documentation](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/getting-started/introduction/).

---

## 👥 Contributors

Solace Agent Mesh is built with the help of our amazing community.  
Thanks to everyone who has contributed ideas, code, and time to make this project better.  
👀 View the full list of contributors → [GitHub Contributors](https://github.com/SolaceLabs/solace-agent-mesh/graphs/contributors)
🤝 **Looking to contribute?** Check out [CONTRIBUTING.md](CONTRIBUTING.md) to get started and see how you can help.

---

## 📄 License

This project is licensed under the **Apache 2.0 License**.  
See the full license text in the [LICENSE](LICENSE) file.
