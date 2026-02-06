# Solace Agent Mesh - Evaluation Framework

This directory contains the evaluation framework for the Solace Agent Mesh. It is designed to test the functionality and performance of Solace Agent Mesh.

## How to Run Evaluations

The evaluations are run using the `sam` command-line interface after installing the project.

### Quick Start with Make

If you prefer an automated setup, you can use the provided Make command which handles environment setup and runs the evaluation. Run the command in the root of the project:

```bash
make test-eval-local
```

This command will:
- Create a Python 3.12 virtual environment
- Install the project and its dependencies
- Run the local evaluation tests

**Note:** Ensure your environment variables are exported before running this command (see [Environment Variables](#environment-variables) section below).

### Manual Setup (alternative)

Install the project and its dependencies by running the following command from the root of the project:

```bash
pip install .
```

Install the rest gateway:

```bash
pip install git+https://github.com/SolaceLabs/solace-agent-mesh-core-plugins#subdirectory=sam-rest-gateway
```

To run an evaluation test suite, use the `sam eval` command followed by the path to the test suite's JSON configuration file. For example, to run the full remote evaluation suite, execute the following command:

```bash
sam eval tests/evaluation/local_example.json
```

## Environment Variables

To run the evaluations successfully, you must configure the following environment variables. These are defined in `sam eval tests/evaluation/local_example.json` and must be exported to your environment.

### Solace Broker Connection

These variables are required to connect to the Solace message broker during the tests.

```bash
export SOLACE_BROKER_URL=<enter the URL of the Solace broker>
export SOLACE_BROKER_USERNAME=<enter the username for the broker connection>
export SOLACE_BROKER_PASSWORD=<enter the password for the broker connection>
export SOLACE_BROKER_VPN=<enter the Message VPN to connect to on the broker>
```

### LLM Evaluator Settings

For evaluations that use an LLM to judge the response, the following variables are needed:

```bash
export LLM_SERVICE_ENDPOINT=<enter the endpoint for the LLM service>
export LLM_SERVICE_API_KEY=<enter the API key for the LLM service>
```
