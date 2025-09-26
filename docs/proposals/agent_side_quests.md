# Feature Proposal: Agent Side Quests

This document proposes a new "Side Quest" capability for agents within the Solace Agent Mesh (SAM) framework.

## 1. Goals

The primary goals of the Agent Side Quest feature are:

1.  **Enable Complex Sub-Task Execution:** To allow an agent to perform complex, multi-step reasoning or data processing tasks in an isolated context without polluting its primary conversation history.
2.  **Improve Context Management:** To provide a mechanism for agents to work with large artifacts or perform exploratory analysis that would otherwise consume excessive tokens, and then discard that context upon completion.
3.  **Enhance Agent Autonomy:** To empower agents to autonomously decompose complex problems into a main task and one or more "side quests," handling them sequentially or in parallel as needed.

## 2. Value to Solace Agent Mesh (SAM)

The Side Quest feature will be a significant value-add to the SAM framework for several reasons:

*   **Enhanced Agent Capabilities:** Side quests unlock more sophisticated and robust agent behaviors. An agent can now decide to "go deep" on a problem (e.g., analyze multiple large documents, run a series of data transformations) and then return to its main task with just the final result. This keeps the main conversation history clean, focused, and efficient.

*   **Improved Performance and Cost-Effectiveness:** By pruning the temporary context after a side quest is complete, we significantly reduce the number of tokens sent to the LLM in subsequent turns of the main task. This leads to faster response times and lower operational costs, especially for long-running, complex conversations.

*   **Increased Robustness and Reliability:** Complex tasks that might fail or get stuck can be isolated within a side quest. If a side quest fails, the agent can report the failure back to the main-line context and decide on an alternative strategy, rather than derailing the entire user-facing conversation.

*   **Simplified Agent Logic:** This feature provides a powerful alternative to managing complex internal state within a single agent turn. Instead of the LLM trying to juggle multiple threads of thought, it can simply delegate a sub-problem to a side quest. This is a more natural and scalable model for problem decomposition that aligns well with how LLMs reason.

## 3. High-Level Requirements

The feature must satisfy the following requirements:

1.  **Self-Initiation:** An agent must be able to programmatically initiate a side quest on itself.
2.  **Context Inheritance:** A side quest must begin with a full copy of the parent agent's conversation history up to the point of initiation.
3.  **Execution Isolation:** A side quest must execute in an isolated context. Its own intermediate steps (LLM turns, tool calls) must not affect the parent's history.
4.  **Result Return:** Upon completion, the side quest must return a final, consolidated result to the parent agent.
5.  **Automatic Cleanup:** The context, history, and any temporary resources generated during the side quest must be automatically discarded after it completes.
6.  **Parallelism:** An agent must be able to initiate multiple side quests in parallel. It must also be able to run side quests in parallel with peer agent calls.
7.  **Recursion:** A side quest must be able to initiate its own (recursive) side quests.
8.  **Artifact Pre-loading:** The initiation of a side quest must support specifying one or more artifacts to be pre-loaded directly into its initial context, saving an LLM turn.

## 4. Key Decisions

To ensure a clean and maintainable implementation, the following architectural decisions have been made:

*   **Implementation via Self-Targeted A2A Task:** The feature will be implemented by having the agent send an A2A (Agent-to-Agent) task to itself. This approach is chosen to maximize code reuse, leveraging the existing robust infrastructure for task lifecycle management, parallel execution, and asynchronous communication.

*   **Tool-Based Invocation:** The primary mechanism for an agent's LLM to trigger a side quest will be through a new built-in tool (e.g., `self_side_quest`). This provides a clean, declarative, and extensible interface for the LLM.

*   **Leveraging `RUN_BASED` Sessions:** A side quest will be implemented as a `RUN_BASED` session. The existing logic for creating a temporary session, copying history, and automatically cleaning up upon completion will be used. This avoids introducing a new, parallel session management system and ensures consistency.

*   **Artifact Loading via Initial Prompt:** To optimize performance, artifacts specified in the side quest tool call will be loaded and injected directly into the first prompt of the side quest. This avoids requiring a subsequent tool call within the quest and makes the pattern more efficient.
