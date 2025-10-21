---
title: Evaluating Agents
sidebar_position: 450
---

# Evaluating Agents

The framework includes an evaluation system that helps you test your agents' behavior in a structured way. You can define test suites, run them against your agents, and generate detailed reports to analyze the results. When running evaluations locally, you can also benchmark different language models to see how they affect your agents' responses.

At a high level, the evaluation process involves three main components:

*   **Test Case**: A `JSON` file that defines a single, specific task for an agent to perform. It includes the initial prompt, any required files (artifacts), and the criteria for a successful outcome.
*   **Test Suite**: A `JSON` file that groups one or more test cases into a single evaluation run. It also defines the environment for the evaluation, such as whether to run the agents locally or connect to a remote Agent Mesh.
*   **Evaluation Settings**: A configuration block within the test suite that specifies how to score the agent's performance. You can choose from several methods, from simple metric-based comparisons to more advanced evaluations using a language model.

This document guides you through creating test cases, assembling them into test suites, and running evaluations to test your agents.

## Creating a Test Case

A test case is a `JSON` file that defines a specific task for an agent to perform. It serves as the fundamental building block of an evaluation. You create a test case to represent a single interaction you want to test, such as asking a question, providing a file for processing, or requesting a specific action from an agent.

### Test Case Configuration

The following fields are available in the test case `JSON` file.

*   `test_case_id` (Required): A unique identifier for the test case.
*   `query` (Required): The initial prompt to be sent to the agent.
*   `target_agent` (Required): The name of the agent to which the query should be sent.
*   `category` (Optional): The category of the test case. Defaults to `Other`.
*   `description` (Optional): A description of the test case.
*   `artifacts` (Optional): A list of artifacts to be sent with the initial query. Each artifact has a `type` and a `path`.
*   `wait_time` (Optional): The maximum time in seconds to wait for a response from the agent. Defaults to `60`.
*   `evaluation` (Optional): The evaluation criteria for the test case.
    *   `expected_tools` (Optional): A list of tools that the agent is expected to use. Defaults to an empty list.
    *   `expected_response` (Optional): The expected final response from the agent. Defaults to an empty string.
    *   `criterion` (Optional): The criterion to be used by the `llm_evaluator`. Defaults to an empty string.

### Test Case Examples

Here is an example of a simple test case. It sends a greeting to an agent and checks for a standard response.

```json
{
    "test_case_id": "hello_world",
    "category": "Content Generation",
    "description": "A simple test case to check the basic functionality of the system.",
    "query": "Hello, world!",
    "target_agent": "OrchestratorAgent",
    "wait_time": 30,
    "evaluation": {
        "expected_tools": [],
        "expected_response": "Hello! How can I help you today?",
        "criterion": "Evaluate if the agent provides a standard greeting."
    }
}
```

This next example shows a more complex test case. It includes a `CSV` file as an artifact and asks the agent to filter the data in the file.

```json
{
  "test_case_id": "filter_csv_employees_by_age_and_country",
  "category": "Tool Usage",
  "description": "A test case to filter employees from a CSV file based on age and country.",
  "target_agent": "OrchestratorAgent",
  "query": "From the attached CSV, please list the names of all people who are older or equal to 30 and live in the USA.",
  "artifacts": [
    {
      "type": "file",
      "path": "artifacts/sample.csv"
    }
  ],
  "wait_time": 120,
  "evaluation": {
    "expected_tools": ["extract_content_from_artifact"],
    "expected_response": "The person who is 30 or older and lives in the USA is John Doe.",
    "criterion": "Evaluate if the agent correctly filters the CSV data."
  }
}
```

## Creating a Test Suite

The test suite is a `JSON` file that defines the parameters of an evaluation run. You use it to group test cases and configure the environment in which they run.

A common convention in the test suite configuration is to use keys ending with `_VAR`. These keys indicate that the corresponding value is the name of an environment variable from which the framework should read the actual value. This practice helps you keep sensitive information—like API keys and credentials—out of your configuration files. This convention applies to the `broker` object, the `env` object within `llm_models`, and the `env` object within the `llm_evaluator` in `evaluation_settings`.

You can run evaluations in two modes: local and remote. Both modes require a connection to a Solace event broker to function.

### Local Evaluation

In a local evaluation, the evaluation framework brings up a local instance of Solace Agent Mesh (SAM) and runs the agents on your local machine. This mode is useful for development and testing because it allows you to iterate quickly on your agents and test cases. You can also use this mode to benchmark different language models against your agents to see how they perform.

To run a local evaluation, you need to install the `sam-rest-gateway` plugin. This plugin allows the evaluation framework to communicate with the local SAM instance. You can install it with the following command:

```bash
pip install "sam-rest-gateway @ git+https://github.com/SolaceLabs/solace-agent-mesh-core-plugins#subdirectory=sam-rest-gateway"
```

#### Local Test Suite Configuration

For a local evaluation, you must define the `agents`, `broker`, `llm_models`, and `test_cases` fields.

The `agents` field is a required list of paths to the agent configuration files. You must specify at least one agent.
```json
"agents": [ "examples/agents/a2a_agents_example.yaml" ]
```

The `broker` field is a required object containing the connection details for the Solace event broker.
```json
"broker": {
    "SOLACE_BROKER_URL_VAR": "SOLACE_BROKER_URL",
    "SOLACE_BROKER_USERNAME_VAR": "SOLACE_BROKER_USERNAME",
    "SOLACE_BROKER_PASSWORD_VAR": "SOLACE_BROKER_PASSWORD",
    "SOLACE_BROKER_VPN_VAR": "SOLACE_BROKER_VPN"
}
```

The `llm_models` field is a required list of language models to use. You must specify at least one model. The `env` object contains environment variables required by the model, such as the model name, endpoint, and API key.
```json
"llm_models": [
    {
        "name": "gpt-4-1",
        "env": {
            "LLM_SERVICE_PLANNING_MODEL_NAME": "openai/azure-gpt-4-1",
            "LLM_SERVICE_ENDPOINT_VAR": "LLM_SERVICE_ENDPOINT",
            "LLM_SERVICE_API_KEY_VAR": "LLM_SERVICE_API_KEY"
        }
    },
    {
        "name": "gemini-1.5-pro",
        "env": {
            "LLM_SERVICE_PLANNING_MODEL_NAME": "google/gemini-1.5-pro-latest",
            "LLM_SERVICE_ENDPOINT_VAR": "LLM_SERVICE_ENDPOINT_GOOGLE",
            "LLM_SERVICE_API_KEY_VAR": "LLM_SERVICE_API_KEY_GOOGLE"
        }
    }
]
```

The `test_cases` field is a required list of paths to the test case `JSON` files. You must specify at least one test case.
```json
"test_cases": [ "tests/evaluation/test_cases/hello_world.test.json" ]
```

You can also provide optional settings for `results_dir_name`, `runs`, `workers`, and `evaluation_settings`.

The `results_dir_name` field is an optional string that specifies the name of the directory for evaluation results. It defaults to `tests`.
```json
"results_dir_name": "my-local-test-results"
```

The `runs` field is an optional integer that specifies the number of times to run each test case. It defaults to `1`.
```json
"runs": 3
```

The `workers` field is an optional integer that specifies the number of parallel workers for running tests. It defaults to `4`.
```json
"workers": 8
```

The `evaluation_settings` field is an optional object that allows you to configure the evaluation. This object can contain `tool_match`, `response_match`, and `llm_evaluator` settings.
```json
"evaluation_settings": {
    "tool_match": {
        "enabled": true
    },
    "response_match": {
        "enabled": true
    },
    "llm_evaluator": {
        "enabled": true,
        "env": {
            "LLM_SERVICE_PLANNING_MODEL_NAME": "openai/gemini-2.5-pro",
            "LLM_SERVICE_ENDPOINT_VAR": "LLM_SERVICE_ENDPOINT",
            "LLM_SERVICE_API_KEY_VAR": "LLM_SERVICE_API_KEY"
        }
    }
}
```

#### Example Local Test Suite

```json
{
    "agents": [
        "examples/agents/a2a_agents_example.yaml",
        "examples/agents/multimodal_example.yaml",
        "examples/agents/orchestrator_example.yaml"
    ],
    "broker": {
        "SOLACE_BROKER_URL_VAR": "SOLACE_BROKER_URL",
        "SOLACE_BROKER_USERNAME_VAR": "SOLACE_BROKER_USERNAME",
        "SOLACE_BROKER_PASSWORD_VAR": "SOLACE_BROKER_PASSWORD",
        "SOLACE_BROKER_VPN_VAR": "SOLACE_BROKER_VPN"
    },
    "llm_models": [
        {
            "name": "gpt-4-1",
            "env": {
                "LLM_SERVICE_PLANNING_MODEL_NAME": "openai/azure-gpt-4-1",
                "LLM_SERVICE_ENDPOINT_VAR": "LLM_SERVICE_ENDPOINT",
                "LLM_SERVICE_API_KEY_VAR": "LLM_SERVICE_API_KEY"
            }
        }
    ],
    "results_dir_name": "sam-local-eval-test",
    "runs": 3,
    "workers": 4,
    "test_cases": [
        "tests/evaluation/test_cases/filter_csv_employees_by_age_and_country.test.json",
        "tests/evaluation/test_cases/hello_world.test.json"
    ],
    "evaluation_settings": {
        "tool_match": {
            "enabled": true
        },
        "response_match": {
            "enabled": true
        },
        "llm_evaluator": {
            "enabled": true,
            "env": {
                "LLM_SERVICE_PLANNING_MODEL_NAME": "openai/gemini-2.5-pro",
                "LLM_SERVICE_ENDPOINT_VAR": "LLM_SERVICE_ENDPOINT",
                "LLM_SERVICE_API_KEY_VAR": "LLM_SERVICE_API_KEY"
            }
        }
    }
}
```

### Remote Evaluation

In a remote evaluation, the evaluation framework sends requests to a remote Agent Mesh instance. This mode is useful for testing agents in a production-like environment where the agents are running on a separate server. The remote environment must have a REST gateway running to accept requests from the evaluation framework. You can also use an authentication token to communicate securely with the remote SAM instance.

#### Remote Test Suite Configuration

For a remote evaluation, you must define the `broker`, `remote`, and `test_cases` fields.

The `broker` field is a required object with connection details for the Solace event broker.
```json
"broker": {
    "SOLACE_BROKER_URL_VAR": "SOLACE_BROKER_URL",
    "SOLACE_BROKER_USERNAME_VAR": "SOLACE_BROKER_USERNAME",
    "SOLACE_BROKER_PASSWORD_VAR": "SOLACE_BROKER_PASSWORD",
    "SOLACE_BROKER_VPN_VAR": "SOLACE_BROKER_VPN"
}
```

The `remote` field is a required object containing the connection details for the remote Agent Mesh instance.
```json
"remote": {
    "EVAL_REMOTE_URL_VAR": "EVAL_REMOTE_URL",
    "EVAL_AUTH_TOKEN_VAR": "EVAL_AUTH_TOKEN",
    "EVAL_NAMESPACE_VAR": "EVAL_NAMESPACE"
}
```

The `test_cases` field is a required list of paths to the test case `JSON` files. You must specify at least one test case.
```json
"test_cases": [ "tests/evaluation/test_cases/hello_world.test.json" ]
```

You can also provide optional settings for `results_dir_name`, `runs`, and `evaluation_settings`.

The `results_dir_name` field is an optional string that specifies the name of the directory for evaluation results. It defaults to `tests`.
```json
"results_dir_name": "my-remote-test-results"
```

The `runs` field is an optional integer that specifies the number of times to run each test case. It defaults to `1`.
```json
"runs": 5
```

The `evaluation_settings` field is an optional object that allows you to configure the evaluation.
```json
"evaluation_settings": {
    "tool_match": {
        "enabled": true
    },
    "response_match": {
        "enabled": true
    }
}
```

#### Example Remote Test Suite

```json
{
    "broker": {
        "SOLACE_BROKER_URL_VAR": "SOLACE_BROKER_URL",
        "SOLACE_BROKER_USERNAME_VAR": "SOLACE_BROKER_USERNAME",
        "SOLACE_BROKER_PASSWORD_VAR": "SOLACE_BROKER_PASSWORD",
        "SOLACE_BROKER_VPN_VAR": "SOLACE_BROKER_VPN"
    },
    "remote": {
        "EVAL_REMOTE_URL_VAR": "EVAL_REMOTE_URL",
        "EVAL_AUTH_TOKEN_VAR": "EVAL_AUTH_TOKEN",
        "EVAL_NAMESPACE_VAR": "EVAL_NAMESPACE"
    },
    "results_dir_name": "sam-remote-eval-test",
    "runs": 1,
    "test_cases": [
        "tests/evaluation/test_cases/filter_csv_employees_by_age_and_country.test.json",
        "tests/evaluation/test_cases/hello_world.test.json"
    ],
    "evaluation_settings": {
        "tool_match": {
            "enabled": true
        },
        "response_match": {
            "enabled": true
        },
        "llm_evaluator": {
            "enabled": true,
            "env": {
                "LLM_SERVICE_PLANNING_MODEL_NAME": "openai/gemini-2.5-pro",
                "LLM_SERVICE_ENDPOINT_VAR": "LLM_SERVICE_ENDPOINT",
                "LLM_SERVICE_API_KEY_VAR": "LLM_SERVICE_API_KEY"
            }
        }
    }
}
```

## Evaluation Settings

The `evaluation_settings` block in the test suite `JSON` file allows you to configure how the evaluation is performed. Each enabled setting provides a score from 0 to 1, which contributes to the overall score for the test case.

### `tool_match`

The `tool_match` setting compares the tools the agent used with the `expected_tools` defined in the test case. This is a simple, direct comparison and does not use a language model for the evaluation. It is most effective when the agent's expected behavior is straightforward and there is a clear, correct sequence of tools to be used. In more complex scenarios where multiple paths could lead to a successful outcome, this method may not be the best way to evaluate the agent's performance.

### `response_match`

The `response_match` setting compares the agent's final response with the `expected_response` from the test case. This comparison is based on the ROUGE metric, which evaluates the similarity between two responses by comparing their sequence of words. This method does not use a language model for the evaluation and does not work well with synonyms, so it is most effective when the expected answer is consistent. For more information about the ROUGE metric, see the [official documentation](https://pypi.org/project/rouge-metric/).

### `llm_evaluator`

The `llm_evaluator` setting uses a language model to evaluate the entire lifecycle of a request within the agent mesh. This includes the initial prompt, all tool calls, delegation between agents, artifact inputs and outputs, and the final message output. The evaluation is based on a `criterion` you provide in the test case, which defines what a successful outcome looks like. This is the most comprehensive evaluation method because it considers the full context of the request's execution.

## Running Evaluations

After you create your test cases and test suite, you can run the evaluation from the command line using the `sam eval` command.

### Command

```bash
sam eval <PATH> [OPTIONS]
```

The command takes the path to the evaluation test suite `JSON` file as a required argument.

### Options

*   `-v`, `--verbose`: Enable verbose output to see detailed logs during the evaluation run.
*   `-h`, `--help`: Show a help message with information about the command and its options.

### Example

```bash
sam eval tests/evaluation/local_example.json --verbose
```

## Interpreting the Results

After an evaluation run is complete, the framework stores the results in a directory. The path to this directory is `results/` followed by the `results_dir_name` you specified in the test suite.

### Results Directory

The results directory has the following structure:

```
<results_dir_name>/
├── report.html
├── stats.json
└── <model_name>/
    ├── full_messages.json
    ├── results.json
    └── <test_case_id>/
        └── run_1/
            ├── messages.json
            ├── summary.json
            └── test_case_info.json
        └── run_2/
            ├── ...
```

*   **`report.html`**: An `HTML` report that provides a comprehensive overview of the evaluation results. It includes a summary of the test runs, a breakdown of the results for each test case, and detailed logs for each test run. This report is the primary tool for analyzing the results of an evaluation.
*   **`stats.json`**: A `JSON` file containing detailed statistics about the evaluation run, including scores for each evaluation metric.
*   **`<model_name>/`**: A directory for each language model tested (or a single `remote` directory for remote evaluations).
    *   **`full_messages.json`**: A log of all messages exchanged during the evaluation for that model.
    *   **`results.json`**: The raw evaluation results for each test case.
    *   **`<test_case_id>/`**: A directory for each test case, containing a `run_n` subdirectory for each run of the test case. These directories contain detailed logs and artifacts for each run.

### HTML Report

The `report.html` file provides a comprehensive overview of the evaluation results. It includes a summary of the test runs, a breakdown of the results for each test case, and detailed logs for each test run. This report is the primary tool for analyzing the results of an evaluation. You can open this file in a web browser to view the report.
