<!-- Copyright Solace Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Examples

Each example is one use case, tested end to end against a running Agent Mesh
instance. The examples are for learning and evaluation, and are not
production-ready.

| Use case | Description | Agent Mesh features |
|---|---|---|
| [Support ticket triage](support-triage/) | Triages each new ticket in the fictional Acme Help Desk, calculates its response deadline, drafts the first reply, escalates the ticket if it is urgent, and writes the result back to the ticket. | Agents, a workflow with a switch, a workflow with a decision node and a decision model, webhook Entrypoints, an OpenAPI connector, a custom Python toolset, a custom skill, a Slack Entrypoint, and evaluations |

## How Each Example Is Organized

Each use case keeps everything that you apply to Agent Mesh in an
`agent-mesh-config/` directory. That directory is a self-contained declarative
configuration repository, in the same layout that you use for the configuration
repository of your own Agent Mesh instance. To print that layout, run
`sam config schema layout`. For more information, see
[Managing Configuration as Code (Early Access)](https://docs.solace.com/Agent-Mesh/Framework/building/declarative-config/index.htm).

Anything else in the use case, such as a demo application that represents an
external system, sits beside `agent-mesh-config/`, and the use case's README
states that it is not part of Agent Mesh.

```text
<use-case>/
├── README.md               # what the use case does, how to run it, and how it works
├── agent-mesh-config/      # everything that you apply to Agent Mesh
│   ├── manifests/          # manifests, such as local.yaml; a use case can have more than one
│   ├── models/             # one file per model resource
│   ├── agents/             # one file per resource, named after the resource
│   ├── workflows/
│   ├── connectors/
│   ├── entrypoints/
│   ├── toolsets/           # custom tool code and its metadata
│   ├── skills/             # one directory per skill
│   └── datasets/  evaluators/  experiments/   # evaluations
├── <demo-application>/     # optional: a demo application for an external system
└── media/                  # images for the README
```

Before you apply an example, complete the setup in the README of its use case.
Then run the following commands from the root of this repository:

```sh
cd examples/<use-case>
sam config plan  -m agent-mesh-config/manifests/local.yaml
sam config apply -m agent-mesh-config/manifests/local.yaml
```
