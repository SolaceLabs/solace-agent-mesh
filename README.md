<p align="center">
  <img src="./docs/static/img/logo.png" alt="Solace Agent Mesh Logo" width="200"/>
</p>

<h1 align="center">Solace Agent Mesh</h1>

<p align="center">
  <a href="https://github.com/SolaceLabs/solace-agent-mesh/issues/new" target="_blank">
    <img src="https://img.shields.io/badge/Create-Issue-blue?style=for-the-badge" alt="Create Issue">
  </a>
<a href="https://solacelabs.github.io/solace-agent-mesh/docs/documentation/getting-started/introduction/" target="_blank">
  <img src="https://img.shields.io/badge/View-Docs-green?style=for-the-badge" alt="View Docs">
</a>
</p>

[![License](https://img.shields.io/github/license/SolaceLabs/solace-agent-mesh)](https://github.com/SolaceLabs/solace-agent-mesh/blob/main/LICENSE)
[![GitHub issues](https://img.shields.io/github/issues/SolaceLabs/solace-agent-mesh?color=red)](https://github.com/SolaceLabs/solace-agent-mesh/issues)
[![GitHub pull requests](https://img.shields.io/github/issues-pr/SolaceLabs/solace-agent-mesh?color=red)](https://github.com/SolaceLabs/solace-agent-mesh/pulls)
[![GitHub stars](https://img.shields.io/github/stars/SolaceLabs/solace-agent-mesh?style=social)](https://github.com/SolaceLabs/solace-agent-mesh/stargazers)
[![PyPI - Version](https://img.shields.io/pypi/v/solace-agent-mesh.svg)](https://pypi.org/project/solace-agent-mesh)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/solace-agent-mesh.svg)](https://pypi.org/project/solace-agent-mesh)

---
**Solace Agent Mesh (SAM)** is an open-source framework for building multi-agent AI systems that can interact with real-world data, tools, and enterprise systems. It is powered by an event-driven backbone for communication, observability, and integration.

Whether you're prototyping an 🤖 AI assistant or deploying a 🌎 production-grade solution, SAM provides the infrastructure to:
  - Connect AI agents to real-world data sources and systems.

  - Add gateways to expose capabilities via REST, a browser-based UI, Slack, and many more.

  - Monitor and debug every interaction in real time.

  - Scale from local development to distributed, enterprise deployments.
---

## ✨ Key Features 

- ⚙️ **Modular, Event-Driven Architecture** – All components communicate via events through a central event mesh, enabling loose coupling and high scalability.
- 🤖 **Composable Agents** – Combine specialized AI agents to solve complex, multi-step workflows.
- 🌐 **Flexible Interfaces** – Interact with SAM via the REST API, browser UI, Slack, or other custom gateways.
- 🧠 **Built-in Orchestration** – Tasks are automatically broken down and delegated across agents by a built-in orchestrator.
- 📊 **Live Observability** – Monitor, trace, and debug agent interactions and workflows in real time.
- 🧩 **Plugin-Extensible** – Add your own agents, gateways, or services with minimal boilerplate.
- 🏢 **Production-Ready** – Backed by Solace’s enterprise-grade event broker for reliability and performance.

---
## 🚀 Quick Start (5 minutes)

Set up Solace Agent Mesh in just a few steps.

### ⚙️ System Requirements

To run Solace Agent Mesh locally, you'll need:

- **Python 3.11+**  

- **pip** (Python package manager)

- **Operating System**  
  - MacOS, Linux, or Windows with [WSL](https://learn.microsoft.com/en-us/windows/wsl/)

You’ll also need access to an LLM API key. We support all major providers and custom endpoints as well.  


### 💻 Setup Steps

```bash
# 1. (Optional) Create and activate a Python virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install the Solace Agent Mesh
pip install solace-agent-mesh

# 3. Initialize a new project
mkdir my-agent-mesh && cd my-agent-mesh
solace-agent-mesh init        #Follow the steps in the interactive init

# 4. Build and run the project
solace-agent-mesh run -b      # Shortcut for `build` + `run`
```

#### Once running:
 - Open the Web UI at [http://localhost:5001](http://localhost:5001) to talk with a chat interface or,
 - Send a curl request to the REST API gateway interface that is exposed by default

 ```bash
 curl --location 'http://127.0.0.1:5050/api/v1/request' \
  --form 'prompt="What is the capital of France?"' \
  --form 'stream="false"'
```

## ➡️ What’s Next?

Now that you’re up and running, here’s where to go next:

- 🤖 [Agents](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/concepts/agents) – Explore agents that provide specialized capabilities.
- 🌐 [Gateways](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/concepts/gateways) – 	Understand how gateways provide interfaces to the Solace Agent Mesh.
- 🧱 [Components Overview](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/getting-started/component-overview) – See how everything fits together: agents, orchestrators, gateways, and more
- 🧩 [Plugins](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/concepts/plugins) – Extend the functionality of the Solace Agent Mesh
- 🔧 [Services](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/concepts/services) – Learn about the services that facilitate interactions within the Solace Agent Mesh.


📚 Full documentation → [solacelabs.github.io/solace-agent-mesh](https://solacelabs.github.io/solace-agent-mesh)

---

## 📦 Release Notes

Stay up to date with the latest changes, features, and fixes.

See [CHANGELOG.md](CHANGELOG.md) for a full history of updates.

---

## 👥 Contributors

Solace Agent Mesh is built with the help of our amazing community.  
Thanks to everyone who has contributed ideas, code, and time to make this project better.

👀 View the full list of contributors → [GitHub Contributors](https://github.com/SolaceLabs/solace-agent-mesh/graphs/contributors)

---

## 📄 License

This project is licensed under the **Apache 2.0 License**.

See the full license text in the [LICENSE](LICENSE) file.
