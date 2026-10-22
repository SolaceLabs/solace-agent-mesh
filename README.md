<!-- Copyright Solace Corporation -->
<!-- SPDX-License-Identifier: BUSL-1.1 -->

# Solace Agent Mesh

[Solace Agent Mesh](https://solace.com/products/agent-mesh/) is an agent development and runtime platform. It supports the full agent development lifecycle: build, test, deploy, monitor, and improve your agents and business process workflows. It hosts the agents you build, runs the tools they call, and coordinates everything over an event broker, with sessions, artifacts, authentication, evaluators, and observability built in.

> [!NOTE]
> **The Solace Agent Mesh source code is coming to this repository soon.**
> Until then, this repository holds Agent Mesh Desktop downloads and
> ready-to-run examples.

## Installing Agent Mesh Desktop

Agent Mesh Desktop is free, runs as a single application on your computer, and
includes the `sam` command line interface (CLI).

To install the application, run the install command for your operating system.
The command downloads the application from the
[latest release](../../releases/latest).

Agent Mesh Desktop runs on the following platforms:

- macOS 11 (Big Sur) and later
- Windows 10 and later (x86_64)
- Linux (Experimental)

On macOS and Linux:

```sh
curl -fsSL https://raw.githubusercontent.com/SolaceProducts/solace-agent-mesh/main/install/install.sh | sh
```

On Windows, in PowerShell:

```powershell
irm https://raw.githubusercontent.com/SolaceProducts/solace-agent-mesh/main/install/install.ps1 | iex
```

The script selects the download that matches your operating system and
processor. On Linux, it also selects your package format and WebKitGTK version.
Before it installs anything, the script checks the download against the SHA-256
checksum of the release asset, and verifies the Apple notarization on macOS or
the Authenticode signature on Windows.

To preview what the script does without installing, run it with `--dry-run`. On
macOS and Linux, pass the flag through `sh -s --`:

```sh
curl -fsSL https://raw.githubusercontent.com/SolaceProducts/solace-agent-mesh/main/install/install.sh | sh -s -- --dry-run
```

On Windows, set `$env:SAM_INSTALL_DRY_RUN=1` instead.

You can also download the asset for your platform from the
[latest release](../../releases/latest) and install it yourself.

To connect an LLM the first time you open the application, see
[Installing the Desktop Bundle](https://docs.solace.com/Agent-Mesh/Framework/installing/desktop.htm).

## Using the `sam` CLI

To run `sam` from a terminal, add it to your `PATH` on Windows, or create an
alias on macOS and Linux:

- **On Windows:** The installer places `sam.exe` in
  `%LOCALAPPDATA%\Programs\Solace Agent Mesh\cli`, and the install script adds
  that folder to your user `PATH`. Open a new terminal to use `sam`. If you
  install without the script, add the folder yourself.
- **On macOS:** Add an alias:
  `alias sam='"/Applications/Solace Agent Mesh.app/Contents/MacOS/sam-desktop"'`
- **On Linux:** Add an alias: `alias sam='solace-agent-mesh'`

The following examples show common `sam` commands. The `sam ai-assistance` and
`sam config` commands are Early Access, so their commands, flags, and output may
change between releases.

```sh
# Install skills that teach your AI coding assistant, such as Claude Code or
# Codex CLI, to build agents, tools, and configuration for your Agent Mesh
# version. By default, the skills are written to .agents/skills/ in the current
# directory, where Codex CLI reads them. For Claude Code, add --target claude.
sam ai-assistance skill install

# Preview a configuration change, and then apply it to a running Agent Mesh
# instance. Replace manifest.yaml with the path to your manifest.
sam config plan -m manifest.yaml
sam config apply -m manifest.yaml

# Open the Agent Mesh documentation offline
sam docs
```

For every command and flag, see the
[CLI reference](https://docs.solace.com/Agent-Mesh/Framework/reference/cli.htm).
To list the top-level commands, run `sam --help`. To see the flags of a command,
run `sam <command> --help`.

## Examples

The [`examples`](examples) directory contains use cases that you apply to Agent
Mesh with `sam config apply`. In the
[support ticket triage](examples/support-triage) use case, a customer creates a
ticket in the fictional Acme Help Desk, and Agent Mesh classifies the issue,
calculates the response deadline, drafts the first reply, escalates the ticket
if it is urgent, and writes the result back to the ticket.

The examples are for learning and evaluation, and are not production-ready.

## Moving to Production

Production use of Agent Mesh requires a Solace commercial license. Agent Mesh
Desktop is for building and testing on your own computer. For production, deploy
Agent Mesh to Kubernetes, or use Agent Mesh Cloud, a managed cloud service. For
more information, see
[Installing Kubernetes for Production](https://docs.solace.com/Agent-Mesh/Framework/installing/kubernetes/production.htm)
and [Agent Mesh Cloud](https://docs.solace.com/Agent-Mesh/Cloud/agent-mesh-manager.htm).
To discuss a production deployment with a Solace expert,
[book a demo](https://solace.com/agent-mesh-demo/).

## License

For the license that covers each part of this repository, see [`NOTICE`](NOTICE).

## Getting Help

This repository does not accept issues or pull requests. For more information,
see [`CONTRIBUTING.md`](CONTRIBUTING.md).

- To ask a question or request a feature, visit the
  [Solace Community](https://community.solace.com/c/solace-agent-mesh).
- To report a bug, email [support@solace.com](mailto:support@solace.com).
- To report a security vulnerability, email
  [support@solace.com](mailto:support@solace.com). For what to include, see
  [`SECURITY.md`](SECURITY.md).
