---
title: Offline Evaluations UI
sidebar_position: 850
---

# Offline Evaluations UI

:::warning Experimental Feature
This feature is under active development. Configuration schemas and behavior may change in future releases. Do not use in production without validating against the current release notes.
:::

Offline evaluations let you measure agent quality by sending a curated set of prompts to a deployed agent, scoring the responses, and tracking results over time. "Offline" means the inputs are prepared in advance — not sampled from live production traffic. This makes it safe to run evaluations repeatedly against the same prompt set and compare results across model changes, prompt updates, or configuration adjustments.

The Offline Evaluations UI provides a browser-based interface for managing the building blocks of this workflow: datasets of example prompts, evaluators that define how responses are scored, and experiments that combine them into reusable run configurations. For the CLI-based evaluation workflow that works with Community and Enterprise deployments alike, see [Evaluating Agents](../developing/evaluations.md).

## What Offline Evaluations Does

The Offline Evaluations UI lets you continuously measure the quality of your deployed agents without modifying their configuration or writing test suite files. You define a dataset of prompts, select or create an LLM-as-judge evaluator, combine them into an experiment that targets a specific agent, and trigger runs on demand. The platform sends each prompt to the agent through the event broker, captures the response, scores it using the evaluator, and stores the results for inspection and comparison.

The key differences from the CLI evaluation workflow are:

| Aspect | CLI Evaluations | Offline Evaluations UI |
|---|---|---|
| Interface | Command line + JSON files | Browser-based UI |
| Edition | Community and Enterprise | Enterprise only |
| Agent target | Local or remote | Deployed agents only |
| Dataset storage | JSON files in source control | Database managed by the platform |
| Result storage | Local HTML/JSON files | Database + object storage |
| Model comparison | Specify models in test suite | Per-experiment model picker |
| Activity diagram | Not available | Per-result A2A message viewer |

Use the Offline Evaluations UI when you want to measure and track agent quality over time against a live deployment, compare multiple language models against the same prompt set, or inspect the full A2A message trace for a specific result.

## Prerequisites

Before using this feature, verify that you have:

- Agent Mesh Enterprise installed and running. For installation instructions, see [Installing Agent Mesh Enterprise](installation.md).
- At least one agent deployed and reachable through the event broker.
- The Platform Service running with a database configured. SQLite works for development; use PostgreSQL for production. For database configuration guidance, see [Installing Agent Mesh Enterprise](installation.md).
- Object storage configured if you want to persist execution data and artifact snapshots beyond the local filesystem. See [Storage Configuration](#storage-configuration) below.

## Storage Configuration

The evaluation execution service stores execution data and agent-produced artifact snapshots in object storage. Two backends are available, selected automatically based on environment variables.

:::warning
The evaluation execution service assumes a single active instance at a time. Running multiple replicas of the Platform Service may cause one instance to mark another's in-progress runs as failed. Set `replicas: 1` (or the equivalent in your deployment platform) for the Platform Service.
:::

### Object Storage

| Environment Variable | Required | Default | Description |
|---|---|---|---|
| `EVAL_DATA_BUCKET_NAME` | No | — | S3, GCS, or Azure Blob container name. When set, the service uses cloud object storage. |
| `OBJECT_STORAGE_FS_ROOT` | No | `<cwd>/tmp/eval-storage` | Filesystem root used when `EVAL_DATA_BUCKET_NAME` is not set. Ignored when a bucket is configured. Defaults to a `tmp/eval-storage` directory relative to the process working directory. |

:::warning
The local filesystem backend is suitable for development only. Data stored under the default `tmp/eval-storage` path is not replicated and will be lost if the container restarts without a persistent volume. Set `EVAL_DATA_BUCKET_NAME` for any deployment where you want to retain execution traces and artifact snapshots.
:::

### Dataset Generation Tuning

These variables control how the service generates datasets using the orchestrator agent.

| Environment Variable | Default | Description |
|---|---|---|
| `EVAL_DATASET_GEN_AGENT` | `OrchestratorAgent` | The agent that receives dataset and example generation requests. Override this if your deployment uses a different orchestrator name. |
| `EVAL_DATASET_GEN_TIMEOUT` | `180` | Seconds to wait for the orchestrator to respond during AI-assisted dataset generation. Increase this value if you are generating large datasets. |

### Run Execution Tuning

These variables control how long the service waits for and manages individual evaluation runs.

| Environment Variable | Default | Description |
|---|---|---|
| `EVAL_AGENT_TIMEOUT_SECONDS` | `480` | Maximum seconds to wait for the target agent to respond to a single example prompt. |
| `EVAL_EXAMPLE_BUDGET_SECONDS` | `600` | Total budget per example, including the agent timeout and scoring time. |
| `EVAL_WATCHDOG_INTERVAL_SECONDS` | `120` | Interval at which the watchdog checks for stale or stuck runs. |
| `EVAL_SCORING_THREADS` | `8` | Thread pool size for parallel LLM-as-judge scoring calls. |

## Reports

The Reports page is the entry point for the Evaluations section. It shows a paginated table of all run groups — one row per time you clicked "Run" on an experiment. From this page you can:

- See the status, start time, duration, and result count for each run group.
- Select a run group row to open the experiment report for that run.
- Filter the run group list by experiment name or target agent.

A run group corresponds to one trigger of a specific experiment. If the experiment targets multiple language model configurations, each configuration produces one run within the group.

Each run group preserves a snapshot of the experiment and evaluator definitions taken when you triggered the run, so editing the experiment afterward does not change historical scores. If you edit the experiment after a run is triggered, the run group is marked with an "outdated configuration" indicator on the Reports page — a signal that the live experiment no longer matches the configuration used to produce these results. Trigger a fresh run to compare against the current configuration.

The watchlist section at the top of the Reports page shows score trend charts for up to five agents you pin. Select agents to watch from the Edit Watchlist dialog, which appears when you click the edit control. Each agent's chart shows one series per experiment that targets it, plotting the primary evaluator score over time. Use the watchlist to spot regressions across deploys or model changes.

## Experiment Lab

The Experiment Lab contains three tabs — Datasets, Evaluators, and Experiments — where you manage the building blocks of evaluations.

### Datasets {#datasets}

A dataset gives your agents a benchmark for experiments. It contains a set of prompts — optionally paired with expected responses — that are sent to the agent during a run. Add examples manually or upload a file to get started, then use the dataset across as many experiments as you need.

Each prompt is called an example. You can optionally include an expected response with each example; evaluators that use the `{{Expected Response}}` placeholder will compare the agent's output against it.

#### Creating a dataset manually

1. Navigate to the Experiment Lab and select the Datasets tab.
2. Click New Dataset.
3. Enter a name (maximum 255 characters) and optional description (maximum 1,000 characters).
4. Save the dataset.
5. Open the dataset and add examples individually by clicking Add Example, or import them in bulk using the import button.

#### Importing examples

The import endpoint accepts two formats.

For CSV, the file must have a `prompt` column. The `expected_response` column is optional. Rows with an empty `prompt` are skipped. A dataset holds a maximum of 100 examples; rows beyond this limit are dropped, and the import result reports the `dropped` count.

```csv
prompt,expected_response
"What is the capital of France?","Paris"
"Summarize this quarter's sales trends.",
```

For JSON, the body must be an array of objects. Each object must have a `prompt` field. The `expected_response` field is optional.

```json
[
  { "prompt": "What is the capital of France?", "expected_response": "Paris" },
  { "prompt": "Summarize this quarter's sales trends." }
]
```

#### AI-assisted dataset generation

The "Generate" option creates a dataset populated by the orchestrator agent based on the target agent's metadata. Select a target agent, specify the number of examples (1–100), and optionally provide a focus hint that the orchestrator treats as a hard requirement for every generated example.

:::warning
The orchestrator generates examples without calling the target agent. It uses the target agent's description, system prompt, and skill metadata. If the agent's metadata is sparse, the generated examples may not reflect the agent's actual capabilities. Review all generated examples before running an experiment.
:::

#### Exporting examples

You can export all examples in a dataset as CSV or JSON. Use the export button on the dataset detail page and select the format. The exported file includes the `sequence_number`, `prompt`, and `expected_response` fields.

### Evaluators {#evaluators}

An evaluator defines how the agent's response is scored. Define your criteria, and an LLM automatically scores every agent response in your experiments against the provided dataset — giving you clear, actionable insight into how well your agents are performing.

Two types are available.

#### Heuristic evaluators

Heuristic evaluators are built-in and cannot be created or deleted through the UI. They are seeded by the platform at startup. Available heuristic types are:

- `rouge`: Weighted ROUGE F1 score (20% R1, 30% R2, 50% RL) measuring text overlap with the expected response.
- `levenshtein`: Normalized edit-distance similarity (0.0–1.0) comparing the response to the expected response.
- `valid_json`: Returns 1.0 if the response is valid JSON, 0.0 otherwise.
- `json_diff`: Recursive structural similarity (0.0–1.0) between two JSON objects.

Heuristic evaluators that use an expected response produce a score of 0.0 when the example has no expected response.

System-seeded evaluators cannot be modified or deleted. The name column shows which evaluators are system-seeded.

#### LLM-as-judge evaluators

LLM-as-judge evaluators use a language model to assign a score based on a prompt template you write. To create one:

1. Navigate to Evaluators on the Experiment Lab tab and click New Evaluator.
2. Enter a name and description.
3. Select the language model configuration the evaluator should use.
4. Write a prompt template. The template must contain the `{{Response}}` placeholder. You can also use `{{Prompt}}` and `{{Expected Response}}`.
5. Define the scoring choices. Each entry maps a natural-language outcome description (for example, "Factually correct and complete") to a numeric score between 0.0 and 1.0. You must define between two and 26 choices. The platform presents them to the LLM as letters (A, B, C…) and maps the returned letter back to the numeric score.
6. Save the evaluator.

:::warning
The `{{Response}}` placeholder must be present in the prompt template. Saving without it will produce a validation error.
:::

The following template demonstrates the default structure:

```
You are evaluating an AI assistant's response for quality and correctness.

User input: {{Prompt}}
Agent response: {{Response}}
Reference answer (if provided): {{Expected Response}}

Assess the response considering accuracy, completeness, and adherence to the reference answer.
```

##### Writing evaluation criteria {#writing-evaluation-criteria}

The criteria field is the rubric the judge LLM applies. It becomes the user-facing portion of the judge prompt; the platform wraps it with a fixed system prompt that instructs the judge to score content, not engage with it, and to return a structured JSON response.

Three variables are available to insert into the criteria:

| Variable | What it resolves to |
|---|---|
| `{{Prompt}}` | The original input sent to the agent for this example. |
| `{{Response}}` | The agent's response text. Required — saving without it produces a validation error. |
| `{{Expected Response}}` | The reference answer from the dataset example, if one was provided. Resolves to `[None]` when the example has no expected response. |

If the agent produced text artifacts during the run (Markdown, JSON, CSV, source code), they are automatically appended to the judge prompt after your criteria text. The judge evaluates their content directly. Binary artifacts (images, PDFs) appear as filename-only references that the judge cannot read.

**Writing effective criteria:**

- **Be specific about what correct looks like.** Vague instructions like "Is the response good?" produce inconsistent scores. Instead, describe the rubric: "Does the response include all required SQL clauses? Is the returned data accurate given the user's question?"
- **Match the variables you use to what you have.** If your dataset examples do not have expected responses, do not reference `{{Expected Response}}` — it will always resolve to `[None]` and confuse the judge.
- **Describe the full range of quality.** Your criteria text pairs with the choice score labels you define below. Writing criteria that naturally maps to those labels (for example, calling out "complete", "partial", and "missing") makes the judge's scoring more consistent.
- **Keep it focused on one dimension per evaluator.** An evaluator that tries to assess accuracy, tone, and format simultaneously produces scores that are hard to act on. Create separate evaluators for separate concerns and attach all of them to the experiment.

##### Choice scores {#choice-scores}

Choice scores map natural-language outcome labels to numeric scores. The judge LLM picks one label per evaluation; its associated score becomes the numeric result for that example.

**How it works:** The platform presents your labels to the judge as lettered options `(A)`, `(B)`, `(C)`… in the order they are defined. The judge returns a letter; the platform maps it back to the label and then to the score. The label (not the letter) is stored in the result for the audit trail.

**Score values:** Scores are entered as percentages (0–100%) in the form and stored internally as 0.0–1.0. Scores at or above 50% are marked as **passed**; scores below 50% are marked as **failed**.

The default set ships three choices as a starting point:

| Label | Score |
|---|---|
| Fail | 0% |
| Partial | 50% |
| Pass | 100% |

**Defining your own choices:**

- **Keep labels short and distinct.** The judge reads your labels when it reasons about which to pick. Short, unambiguous labels like "Correct", "Partially correct", and "Incorrect" are easier for the judge to distinguish than long descriptions that overlap.
- **Order choices from best to worst or worst to best** and keep the order consistent across evaluators. The judge sees them as `(A)`, `(B)`, `(C)`… and a consistent ordering reduces scoring variance.
- **Use a spread of score values.** If all choices cluster near 0% or 100%, the average scores across a dataset will compress into a narrow band that makes it hard to see improvements over time. A spread like 0%, 50%, 100% or 0%, 33%, 67%, 100% gives the trend charts useful range.
- **Minimum 2, maximum 26 choices.** You can reorder choices by dragging the grip handle on the left.

### Experiments

An experiment combines a dataset, a target agent, one or more language model configurations, and one or more evaluators into a reusable configuration you can trigger repeatedly to produce comparable results.

#### Creating an experiment

1. Navigate to the Experiment Lab and select the Experiments tab, then click New Experiment.
2. Enter a name and description.
3. Select the target agent from the dropdown.
4. Select the dataset to use.
5. Select one or more evaluators (up to three). Designate one as the primary evaluator; its score is used for the watchlist trend chart and for the "outdated configuration" indicator on the Reports page.
6. Select one or more model configurations (up to three). Each configuration produces a separate run within the same run group when you trigger the experiment.
7. Optionally expand **Advanced Options** to set runs per example (1–5, default 2). Higher values reduce variance by running each example multiple times and averaging the scores.
8. Save the experiment.

#### Triggering a run

Open an experiment and click Run. You can optionally enter a run name to identify the trigger (for example, a version tag or deployment date). The platform creates one pending run per model configuration. The execution service picks up pending runs in order and begins executing them.

When you trigger a run, the platform snapshots the experiment configuration and the full definitions of every attached evaluator onto the run. Subsequent edits to the experiment — including changes to the dataset, evaluators, model configurations, or runs per example — apply only to future runs; previously triggered runs continue to score against their snapshot, so historical results stay reproducible.

You can cancel a run while it is pending or in progress. Cancellation is not immediate — the execution service marks the run as cancelled after the current example finishes.

#### Run statuses

| Status | Meaning |
|---|---|
| `pending` | The run has been created and is waiting for the execution service to pick it up. |
| `running` | The execution service is actively sending examples to the agent. |
| `completed` | All examples finished without errors. |
| `completed_with_warnings` | All examples finished, but at least one returned an error response. Results are available for inspection. |
| `failed` | The run encountered an unrecoverable error. |
| `cancelled` | A user cancelled the run before it completed. |

## Viewing Results

Select a run group from the Reports table to open the experiment report. The report shows a grid of examples as rows and model configurations as columns. Each cell displays the evaluator score for that example–model pair.

Click an example row to open the example inspector side panel. The panel shows:

- The prompt sent to the agent.
- The expected response (if defined on the example).
- A responses table with one column per model and one row per trial. Expand a trial row to see the agent's response, any artifacts it produced, and LLM-as-a-Judge reasoning per evaluator.

### Viewing full details and the activity diagram

The inspector header has an **Open Full Details** button that opens the example on a dedicated full-page view. The full-page view shows the same prompt, expected response, and one Run card per trial. Each model column in a Run card has a network icon button in its header. Clicking it opens a side panel with two tabs:

- **Files** — artifacts produced by the agent for that specific run and model, with the same preview and download behavior as the main inspector.
- **Activity** — the captured A2A event stream rendered as a flow chart, showing the message flow between the orchestrator, the target agent, and any peer agents involved in producing the response.

If no task events were captured for a result, the Activity tab shows an "Activity diagram unavailable" message.

### Exporting results

You can export the results for a completed run as CSV or JSON. Navigate to the run group, expand the run you want to export, and use the export button. Both formats include the prompt, expected response, agent response, duration, and a score and pass/fail per evaluator for each example. The JSON export additionally includes the evaluator reasoning for each score.

### Deleting artifacts

Individual artifacts can be deleted from the Files tab in the activity panel. Deleting an artifact removes the stored bytes from object storage and removes the entry from the result's artifact list. The result row itself is preserved — scores and reasoning remain visible after an artifact is deleted.

## Troubleshooting

### Run stays "pending" and never starts

The execution service is not running or failed to connect to the broker. Check the Platform Service logs for `[EvalExecutionService] Started`. If this line is absent, verify the Platform Service can connect to the Solace broker.

### Run completes but results show no score

LLM-as-judge scoring failures do not fail the run — the platform stores the result with an empty score and continues. Open a result, expand the evaluator score section, and check the reasoning field. If reasoning is empty, the LLM call failed silently. Verify that the model configuration assigned to the evaluator is active and reachable from the Platform Service.

### AI-assisted dataset generation fails

**Invalid JSON response:** The orchestrator's model produced output the platform could not parse. Reduce the number of requested examples and retry, or switch to a model with stronger instruction-following.

**Timeout:** The orchestrator did not respond within `EVAL_DATASET_GEN_TIMEOUT` seconds. Increase this value (300–600 seconds for large datasets), or generate a smaller batch and append additional examples in a second pass.

### Run shows "completed_with_warnings"

At least one example timed out or returned an error from the agent. Open the result inspector for an errored example and check `errorMessage`. If many examples error, consider increasing `EVAL_AGENT_TIMEOUT_SECONDS` or reducing the experiment's concurrent load.

### Artifact downloads return 404

The artifact was stored on the local filesystem and the container was restarted, or the artifact was explicitly deleted. Set `EVAL_DATA_BUCKET_NAME` to a persistent object storage bucket to prevent data loss on restart.

### Cannot delete an experiment or dataset

An active (`pending` or `running`) run is blocking deletion. Cancel all active runs from the experiment detail page, then retry the deletion.

## Related Topics

- [Evaluating Agents](../developing/evaluations.md) — CLI-based evaluation workflow for Community and Enterprise deployments.
- [Installing Agent Mesh Enterprise](installation.md) — Installation and database configuration.
- [Setting Up RBAC](rbac-setup-guide.md) — Configure the `sam:evaluations:read`, `sam:evaluations:write`, and `sam:evaluations:execute` permission scopes to control who can access the Evaluations UI.
- [Model Configurations](../installing-and-configuring/model_configurations.md) — Create and manage the model configurations you assign to experiments and LLM-as-judge evaluators.
