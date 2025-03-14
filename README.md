# Solace Agent Mesh

[![License](https://img.shields.io/github/license/SolaceLabs/solace-agent-mesh)](https://github.com/SolaceLabs/solace-agent-mesh/blob/main/LICENSE)
[![GitHub issues](https://img.shields.io/github/issues/SolaceLabs/solace-agent-mesh?color=red)](https://github.com/SolaceLabs/solace-agent-mesh/issues)
[![GitHub pull requests](https://img.shields.io/github/issues-pr/SolaceLabs/solace-agent-mesh?color=red)](https://github.com/SolaceLabs/solace-agent-mesh/pulls)
[![GitHub stars](https://img.shields.io/github/stars/SolaceLabs/solace-agent-mesh?style=social)](https://github.com/SolaceLabs/solace-agent-mesh/stargazers)
[![PyPI - Version](https://img.shields.io/pypi/v/solace-agent-mesh.svg)](https://pypi.org/project/solace-agent-mesh)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/solace-agent-mesh.svg)](https://pypi.org/project/solace-agent-mesh)

- [Solace Agent Mesh](#solace-agent-mesh)
   * [Installation](#installation)
   * [Quick Start](#quick-start)
   * [Why Use Solace Agent Mesh?](#why-use-solace-agent-mesh)
   * [Next Steps](#next-steps)
   * [Contributing](#contributing)
   * [Authors](#authors)
   * [Release Notes](#release-notes)
   * [License](#license)

The Solace Agent Mesh (SAM) is an open-source platform that tackles a fundamental challenge in modern AI development: while powerful AI models are readily available, the real complexity lies in connecting them to the data and systems where they can provide value. Data is often siloed across databases, SaaS platforms, APIs, and legacy systems, making it difficult to build AI applications that operate seamlessly across these boundaries. SAM provides a flexible foundation for AI applications where multiple agents can collaborate, each bringing their own specialized capabilities and data access. Whether you're an AI enthusiast experimenting with new models, or an enterprise developer building production systems, SAM gives you the tools to:

- Connect AI agents to real-world data sources and systems.
- Add SAM Gateways to provide event-based integrations or interactive UI connections.
- Monitor and debug AI interactions in real-time.
- Deploy solutions that scale from prototype to production.

Rather than trying to be a monolithic AI platform, SAM focuses on being an excellent integration layer. It brings together specialized agents - whether they're using local databases, accessing cloud APIs, or interfacing with enterprise systems - and helps them collaborate to solve complex problems.

Built on event-driven architecture technology from Solace, SAM provides the robust foundation needed for both experimental and production deployments.

![Solace Agent Mesh Overview](./docs/static/img/Solace_AI_Framework_With_Broker.png)

## Installation

1. [Optional] Set up Python Virtual Environment using `virtualenv` and activate it

```sh
## Install virtualenv if not already installed
python3 -m pip install --user virtualenv
## Setup python virtual environment
python3 -m venv venv
## Activate virtual environment:
### MacOS/Linux:
source venv/bin/activate
### Windows:
venv/Scripts/activate
```

2. The following command installs the Solace Agent Mesh CLI in your environment:

```sh
pip install solace-agent-mesh
```

3. Run the following SAM CLI command (`solace-agent-mesh` or `sam`) to verify your installation:

```sh
solace-agent-mesh --version
```

## Quick Start

To get started with Solace Agent Mesh, follow these steps:

1. **Install the CLI**: Ensure `solace-agent-mesh` is installed.
2. **Create a Project**:  
    Follow the prompts to create your project.

   ```sh
   mkdir my-agent-mesh && cd my-agent-mesh
   solace-agent-mesh init
   ```

   _Enable the REST API interface when prompted._

3. **Build the Project**:

   ```sh
   solace-agent-mesh build
   ```

4. **Run the Project**:

   ```sh
   solace-agent-mesh run -e
   ```

   _(Use `-eb` to combine build and run steps.)_

5. **Connect to the Web Interface**:

   Open the web interface at [http://127.0.0.1:5001](http://127.0.0.1:5001) or with the port specified during `init`.

6. **Send a REST Request**:

   Try the system by sending a request to the REST API gateway interface.

   ```sh
   curl --location 'http://localhost:5050/api/v1/request' \
   --header 'Authorization: Bearer None' \
   --form 'prompt="What is the capital of France?"' \
   --form 'stream="false"'
   ```

Learn about [Agents](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/concepts/agents) and [Gateways](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/concepts/gateways) to add more functionalities to your project.

For full details, see the [Quick Start Guide](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/getting-started/quick-start).

## Why Use Solace Agent Mesh?

Building production-ready AI applications presents unique challenges. While it's relatively easy to create AI prototypes, deploying them in enterprise environments requires solving complex problems around integration, scalability, and observability. The Solace Agent Mesh addresses these challenges through:

- **Composable Architecture**: Start with a small number of agents and gateways. You can add more over time.

- **Add Agents to Increase Capabilities**: Each new agent adds more capabilities to the system. Adding a new agent isn't additive - it is exponential. With each agent being able to enhance all other agents as they collaborate for more and more complex tasks.

- **Add Gateways to Increase Use Cases**: Each new gateway opens up new use cases for the system. A new gateway can provide a new interface to the system, with a different system purpose and response rules.
- **Event-Driven Design**: Built on proven event-driven architecture principles, providing complete decoupling of components. This makes the system highly flexible and resilient, while enabling real-time monitoring of every interaction.

- **Enterprise-Ready**: Designed from the ground up for production deployments that incorporates the experience from Solace in building mission-critical distributed systems.

## Next Steps

Check [Solace Agent Mesh Documentation](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/getting-started/introduction) to learn more about the Solace Agent Mesh.

|                                                                                                                                                  |                                                                                    |
| ------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| [Components Overview](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/getting-started/component-overview) | Learn about the components that make up the Solace Agent Mesh.                     |
| [Gateways](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/concepts/gateways)                             | Understand how gateways provide interfaces to the Solace Agent Mesh.               |
| [Agents](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/concepts/agents)                                 | Explore the agents that provide specialized capabilities in the Solace Agent Mesh. |
| [Services](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/concepts/services)                             | Learn about the services that facilitate interaction within the Solace Agent Mesh. |
| [Plugins](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/concepts/plugins)                               | Discover the plugins that extend the functionality of the Solace Agent Mesh.       |

## Contributing

Contributions are encouraged! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct, and the process for submitting pull requests to us.

You can report any issues by opening an issue on the GitHub repository.

## Authors

See the list of [contributors](https://github.com/SolaceLabs/solace-agent-mesh/graphs/contributors) who participated in this project.

## Release Notes

Check out the [CHANGELOG](CHANGELOG.md) for details on changes in each release.

## License

The Solace Agent Mesh is licensed under the Apache-2.0 license.

See the [LICENSE](LICENSE) file for details.
