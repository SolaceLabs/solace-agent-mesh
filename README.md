<p align="center">
  <img src="./docs/static/img/logo.png" alt="Solace Agent Mesh Logo" width="100"/>
</p>
<h2 align="center">
  Solace Agent Mesh
</h2>
<h4 align="center">Open-source framework for building event driven multi-agent AI systems</h3>

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
</p>
<p align="center">
  <a href="#-key-features">Key Features</a> •
  <a href="#-quick-start-5-minutes">Quickstart</a> •
  <a href="#️-next-steps">Next Steps</a>
</p>

---

Whether you're prototyping an 🤖 AI assistant or deploying a 🌎 production-grade solution, **Solace Agent Mesh (SAM)** provides the infrastructure to:
  - Connect AI agents to real-world data sources and systems.
  - Add gateways to expose capabilities via REST, a browser-based UI, Slack, and many more.
  - Scale from local development to distributed, enterprise deployments.

![Solace Agent Mesh Overview](./docs/static/img/Solace_AI_Framework_README.png)

---

## ✨ Key Features 
- ⚙️ **[Modular, Event-Driven Architecture](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/getting-started/component-overview)** – All components communicate via events through a central event mesh, enabling loose coupling and high scalability.
- 🤖 **[Composable Agents](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/concepts/agents)** – Combine specialized AI agents to solve complex, multi-step workflows.
- 🌐 **[Flexible Interfaces](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/concepts/gateways)** – Interact with SAM via the REST API, browser UI, or [Slack Integration](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/tutorials/slack-integration).
- 🧠 **[Built-in Orchestration](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/concepts/orchestrator)** – Tasks are automatically broken down and delegated across agents by a built-in orchestrator.
- 🧩 **[Plugin-Extensible](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/concepts/plugins)** – Add your own agents, gateways, or services with minimal boilerplate.
- 🏢 **[Production-Ready](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/deployment/deploy)** – Backed by [Solace’s enterprise-grade event broker](https://solace.com/products/event-broker/) for reliability and performance.
- 🔧 **[Services](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/concepts/services)** –  File storage, memory, and embeddings, all extensible, and built-in.

---

## 🚀 Quick Start (5 minutes)

Set up Solace Agent Mesh in just a few steps.

### ⚙️ System Requirements

To run Solace Agent Mesh locally, you’ll need:

- **Python 3.10.16+**
- **pip** (comes with Python)
- **OS**: MacOS, Linux, or Windows (with [WSL](https://learn.microsoft.com/en-us/windows/wsl/))
- **LLM API key** (any major provider or custom endpoint)

### 💻 Setup Steps

```bash
# 1. (Optional) Create and activate a Python virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install the Solace Agent Mesh
pip install solace-agent-mesh

# 3. Initialize a new project
mkdir my-agent-mesh && cd my-agent-mesh
solace-agent-mesh init        # Follow the steps in the interactive init

# 4. Build and run the project
solace-agent-mesh run -b      # Shortcut for build + run
```

#### Once running:

- Open the Web UI at [http://localhost:5001](http://localhost:5001) to talk with a chat interface.
<details>
  <summary>Use the REST API directly via curl</summary>

  ```bash
  curl --location 'http://127.0.0.1:5050/api/v1/request' \
    --form 'prompt="What is the capital of France?"' \
    --form 'stream="false"'
  ```

</details>


---

## ➡️ Next Steps

Want to go further? Here are some hands-on tutorials to help you get started:

| 🔧 Integration | ⏱️ Est. Time | 📘 Tutorial |
|----------------|--------------|-------------|
| 🌤️ **Weather Agent**<br>Build an agent that gives Solace Agent Mesh  the ability to access real-time weather information.  | **~5 min** | [Weather Agent Plugin](https://github.com/SolaceLabs/solace-agent-mesh-core-plugins/tree/main/sam-geo-information) |
| 🗃️ **SQL Database Integration**<br>Enable Solace Agent Mesh to answer company-specific questions using a sample coffee company database.| **~10–15 min** | [SQL Database Tutorial](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/tutorials/sql-database) |
| 🧠 **MCP Integration**<br>Integrating a Model Context Protocol (MCP) Server into Solace Agent Mesh. | **~10–15 min** | [MCP Integration Tutorial](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/tutorials/mcp-integration) |
| 💬 **Slack Integration**<br>Chat with Solace Agent Mesh directly from Slack. | **~20–30 min** | [Slack Integration Tutorial](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/tutorials/slack-integration) |


📚 Want to explore more? Check out the full [Solace Agent Mesh documentation](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/getting-started/introduction/).

---

## 📦 Release Notes

Stay up to date with the latest changes, features, and fixes.  
See [CHANGELOG.md](CHANGELOG.md) for a full history of updates.

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
