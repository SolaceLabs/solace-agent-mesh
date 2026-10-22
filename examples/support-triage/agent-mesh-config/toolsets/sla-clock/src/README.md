<!-- Copyright Solace Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# sla-clock Toolset

The `sla-clock` toolset is a custom toolset: tool code that you write outside
Agent Mesh and deliver to Agent Mesh as configuration. Nothing in this directory
is part of Agent Mesh, and you do not change or rebuild Agent Mesh to add the
toolset. The `sam config apply` command builds the code, uploads it to Agent
Mesh with the rest of the `agent-mesh-config` directory, and waits until Agent
Mesh discovers the tool.

The code uses the Agent Mesh tool SDK for Python. You can also write a toolset
in Go. For more information, see
[Remote Tools: Python](https://docs.solace.com/Agent-Mesh/Framework/building/tools.htm#remote-tools-python)
and [Remote Tools: Go via `samtoolsdk`](https://docs.solace.com/Agent-Mesh/Framework/building/tools.htm#remote-tools-go-via-samtoolsdk).

The toolset provides one tool, `compute_response_due`, that calculates when a
support ticket must receive its first response. The tool counts the ticket's
response target in the support team's business hours and time zone, and skips
weekends and the team's holidays.

Agent Mesh registers the tool as `sla-clock__compute_response_due`. The
`ticket-intake` workflow calls it in its `respond_by` step.

## Parameters

| Parameter | Required | Description |
|---|---|---|
| `priority` | Yes | The priority of the ticket, `P1` through `P4`. |
| `created_at` | No | When the ticket was created, in ISO 8601 format with a UTC offset, such as `2026-10-09T20:30:00Z`. If you omit it, the tool uses the current time. The tool rejects a timestamp without a UTC offset. |

The tool returns `respond_by` (ISO 8601, in the support team's time zone),
`respond_by_text` (the same deadline, written for a customer), `target`, and
`support_timezone`.

## Configuration

You set the configuration in `toolsets/sla-clock.yaml`, under `spec.config`.

| Field | Default | Description |
|---|---|---|
| `support_timezone` | `America/Toronto` | The support team's IANA time zone. |
| `business_hours` | `09:00-17:00` | The opening and closing times on working days. Monday through Friday are working days. |
| `holidays` | None | A comma-separated list of dates, in `YYYY-MM-DD` format, when the support team is closed. |
| `response_targets` | `P1=1h,P2=4bh,P3=8bh,P4=24bh` | The first-response target for each priority. `h` means clock hours, and `bh` means business hours. |

## Building and Testing

The `sam config apply` command builds and uploads the toolset. To build it for
your computer and check that Agent Mesh can discover the tool, run the following
command from the `agent-mesh-config` directory:

```sh
sam toolset validate sla-clock
```

To work on the code with autocompletion, install the package into a virtual
environment:

```sh
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python -m sla_clock --schema
```

The tool uses the `sam-tool-sdk` package, the Agent Mesh tool SDK for Python.
The `tzdata` package supplies the time zone data, so the tool does not depend on
the operating system's time zone database.
