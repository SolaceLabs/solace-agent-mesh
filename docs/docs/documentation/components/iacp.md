# Inter-Agent Communication Protocol (IACP)

IACP is a lightweight, open protocol (CC BY 4.0) for structured agent-to-agent communication. It complements the [MCP (Model Context Protocol)](https://modelcontextprotocol.io) by providing the agent↔agent layer that MCP's agent↔tool model doesn't address.

## Where IACP Fits in the SAM Stack

```
┌──────────────────────────────────────────┐
│              Agent A                     │
│  ┌────────┐  ┌──────────────────────┐   │
│  │  MCP   │  │       IACP           │   │
│  │ (tools)│  │  (agent messaging)   │   │
│  └────────┘  └──────────┬───────────┘   │
└─────────────────────────┼───────────────┘
                          │ IACP message
┌─────────────────────────┼───────────────┐
│              Agent B    │               │
│  ┌──────────────────────┴───────────┐   │
│  │       IACP + MCP                 │   │
│  │  (receive + execute + respond)   │   │
│  └──────────────────────────────────┘   │
└──────────────────────────────────────────┘
```

**MCP** handles agent↔tool (filesystem, APIs, databases).  
**IACP** handles agent↔agent (handoff, coordination, trust).  
Together they form a complete agent communication stack.

## Key Capabilities

### 1. Structured Handoff

When Agent A delegates work to Agent B, IACP provides:

- **Context transfer** — full task state, not just a text prompt
- **Verifiable acceptance** — Agent B cryptographically signs receipt
- **Audit trail** — every handoff is logged and verifiable

### 2. Cryptographic Identity

Each agent has an Ed25519 keypair. Agents verify each other's identity before accepting work — no more "trust whoever connects."

### 3. Capability Discovery

Before delegating, Agent A can ask Agent B: "What can you do?" Agent B responds with a signed capability manifest.

## Integration with SAM

SAM agents already communicate via A2A and MCP. IACP adds:

| Layer | Without IACP | With IACP |
|-------|-------------|-----------|
| Identity | Agent name string | Ed25519 public key |
| Trust | Implicit (same mesh) | Cryptographic (cross-mesh) |
| Handoff | A2A task send | Signed context transfer |
| Audit | Logs only | Immutable audit trail |
| Discovery | Static config | Dynamic capability manifest |

## Getting Started

The IACP specification is open source (CC BY 4.0):

- **Spec:** https://workswithagents.com/specs/iacp.md
- **Python SDK:** `pip install works-with-agents`
- **Reference implementation:** 6 languages (Python, TypeScript, Go, C#, Rust, Shell)

## Further Reading

- [Identity Protocol](https://workswithagents.com/specs/identity.md) — Ed25519 agent identity
- [Handoff Protocol](https://workswithagents.com/specs/handoff.md) — Context transfer with verification
- [Coordination Protocol](https://workswithagents.com/specs/coordination.md) — Multi-agent leader election
