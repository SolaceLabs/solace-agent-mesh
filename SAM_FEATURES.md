# Solace Agent Mesh (SAM) Feature Overview

## Introduction

The Solace Agent Mesh (SAM) provides a robust, enterprise-grade framework for building and deploying sophisticated AI agents. At its heart, SAM leverages the power and flexibility of Google's Agent Development Kit (ADK) for core agent logic, including LLM interaction, tool use, and conversation history management.

SAM enhances the ADK by integrating it into a scalable, event-driven architecture. It adopts the Agent-to-Agent (A2A) protocol for standardized message schemas and interaction patterns, ensuring interoperability between different components. However, instead of relying on direct HTTP calls, SAM uses an event broker for all communication. This provides a truly asynchronous, decoupled platform where agents and services can interact reliably and efficiently, even across different environments and at massive scale.

This document outlines the key features that SAM provides on top of the standard ADK library, enabling developers to build powerful, collaborative, and production-ready AI solutions.

## Feature Highlights

*   **Event-Driven A2A Protocol:** A complete, asynchronous communication protocol for all system components, built on an event broker for scalability and resilience.
*   **Dynamic Agent-to-Agent Delegation:** Agents can discover and delegate tasks to other specialized agents on the mesh as easily as calling a local tool.
*   **Advanced Artifact Management:** Go beyond basic storage with automatically generated metadata, schema inference for structured data, and support for production-grade storage backends like S3.
*   **Dynamic Content Generation ("Embeds"):** A powerful mini-language within prompts that allows for dynamic data transformation, content embedding, and on-the-fly calculations.
*   **Intelligent Content Processing:** Automatically parse and structure complex tool outputs (e.g., from MCP tools) into multiple, well-defined artifacts.
*   **Robust Configuration & Initialization:** A declarative configuration framework with built-in validation and a flexible tool-loading system simplifies agent setup and deployment.
*   **Extensible Middleware:** A pluggable middleware layer allows for custom logic to handle user-specific configurations and feature access control.
*   **Comprehensive Tool Library:** A rich set of built-in tools for data analysis, file conversion, image generation, and more, ready to be enabled in any agent.
*   **Enhanced Observability:** Advanced debugging tools, including detailed invocation logging and Datadog-compatible output, provide deep visibility into agent behavior.

## Core Architecture & Communication Layer

While the ADK provides the "brain" for an individual agent, the Solace Agent Mesh provides the "nervous system" that allows a fleet of agents to communicate and operate as a cohesive, enterprise-grade system. This is achieved through a foundational architecture built on three key pillars.

First, SAM replaces direct agent-to-agent HTTP calls with a powerful **event-driven architecture**. All communication—requests, responses, and status updates—is exchanged as messages over an event broker. This decouples every component, meaning agents don't need to know each other's network location or status. The result is a highly scalable and resilient mesh that can handle agents joining, leaving, or failing without disrupting the entire system.

Second, all communication adheres to the **A2A (Agent-to-Agent) protocol**, which provides a standardized and structured format for every interaction. This common language ensures that messages, tasks, and file attachments are handled consistently and reliably, eliminating ambiguity between different agents and services. It creates a predictable and interoperable ecosystem where any new component that "speaks A2A" can immediately participate.

Finally, SAM introduces a **managed agent lifecycle and a formal Task Execution Context**. Each agent operates as an independent, self-contained component, ensuring that one agent's workload doesn't block or slow down others. For each request an agent receives, the framework creates a dedicated "control center" that manages the task's state from start to finish. This provides robust, fine-grained control over long-running operations, cancellation signals, and streaming data—capabilities essential for complex, real-world workflows that go far beyond a single LLM turn.

## Inter-Agent Communication (A2A Delegation)

SAM transforms individual agents into a collaborative team of specialists. Instead of being limited to its own local tools, a SAM agent can dynamically discover other agents on the mesh and delegate tasks to them as if they were simple function calls. This powerful abstraction allows agents to specialize in specific domains—like data analysis, customer communication, or system monitoring—and seamlessly collaborate to solve complex problems.

Crucially, this delegation is fully asynchronous and non-blocking. When an agent delegates a task, it doesn't wait idly for the response. It can continue working on other parts of a problem or even delegate tasks to multiple other agents in parallel. The SAM framework manages this complex orchestration behind the scenes, tracking all outstanding requests, handling timeouts, and gathering all the peer responses before re-engaging the original agent with the complete set of results.

This capability moves beyond the single-agent paradigm, enabling the creation of sophisticated, multi-agent systems that can tackle complex, multi-step problems by distributing work to the most qualified specialist available on the mesh.

## Enhanced Artifact Management

SAM elevates the ADK's basic file storage into a sophisticated, intelligent artifact management system. Where the standard ADK provides a simple way to save a file, SAM enriches this process, making artifacts more discoverable, understandable, and ready for enterprise use.

First, every artifact saved in SAM is automatically paired with a **rich metadata file**. This acts like a digital label, capturing not just the file's name and type, but also a description of its contents, its origin, and other custom details. This ensures that both users and other agents can understand an artifact's purpose and context without having to inspect its contents manually.

For structured data like CSV, JSON, or YAML files, SAM goes a step further by performing **automatic schema inference**. When an agent saves a data file, the framework intelligently analyzes its structure—such as column headers in a CSV or the key-value layout of a JSON object—and includes this schema in the metadata. This gives the LLM a "table of contents" for the data, enabling it to write accurate queries and transformations in subsequent steps without first needing to load and read the entire file.

Finally, SAM provides **pluggable, production-grade storage backends**. Instead of being limited to the ADK's default in-memory storage (where files are lost on restart), SAM supports persistent storage on a local filesystem or in enterprise cloud object stores like Amazon S3. This makes artifacts durable and reliable, turning them from temporary outputs into managed, long-term assets for your AI applications.

## Dynamic Content & Prompt Engineering ("Embeds")

SAM introduces a powerful mini-language, called "Embeds," that can be used directly within an agent's text responses and tool arguments. This feature, denoted by special `&laquo;...&raquo;` delimiters, allows an agent to go beyond static text and dynamically generate content on the fly, fundamentally enhancing what's possible in a single LLM response.

#### Basic Embeds

At its simplest, an embed allows an agent to perform a quick calculation or insert dynamic information. The syntax is `&laquo;type:expression&raquo;`. For example, instead of outputting a potentially incorrect calculation, the agent can output an embed that the framework resolves before sending the final message to the user.

*   **Math:** `The total cost is &laquo;math: (19.99 * 3) + 5.50&raquo; USD.`
    *   *Result:* The total cost is 65.47 USD.
*   **Date/Time:** `Report generated on &laquo;datetime:%Y-%m-%d %H:%M&raquo;.`
    *   *Result:* Report generated on 2023-10-27 14:30.
*   **Artifact Metadata:** `Here is the summary for &laquo;artifact_meta:quarterly_report.csv&raquo;`
    *   *Result:* The embed is replaced with a formatted summary of the `quarterly_report.csv` artifact's metadata, including its description, size, and column headers.

#### Chained Embeds for Data Transformation

The true power of embeds is unlocked with the `artifact_content` type, which allows an agent to load an artifact and apply a series of transformations to it using a **modifier chain**. This enables complex data manipulation without needing multiple, separate tool calls.

The syntax uses `>>>` to chain modifiers together, ending with a `format` step:
`&laquo;artifact_content:filename.ext >>> modifier1:value >>> ... >>> format:output_format&raquo;`

For example, imagine an agent needs to list the names of all active users from a `users.json` file. Instead of calling three separate tools, it can construct a single embed:

`&laquo;artifact_content:users.json >>> jsonpath:$.users[?(@.active==true)] >>> select_cols:name >>> format:text&raquo;`

This single directive instructs the framework to:
1.  Load the content of `users.json`.
2.  Apply a `jsonpath` modifier to filter for objects where the "active" key is true.
3.  Apply a `select_cols` modifier to the result, keeping only the "name" field.
4.  Format the final list of names as plain text for the user.

#### Templating with Mustache

The modifier chain includes a powerful `apply_to_template` modifier. This allows an agent to first create a Mustache template artifact (e.g., `report_template.html`) and then, in a subsequent step, use an embed to render structured data (like JSON or CSV) into that template. This separates content from presentation, enabling the creation of sophisticated, consistently formatted reports, emails, or other documents.

For example, an agent could render a CSV file into an HTML table using a template:
`&laquo;artifact_content:sales_data.csv >>> apply_to_template:table_template.html >>> format:text&raquo;`

#### Embeds in Tool Parameters

This dynamic capability extends to tool parameters. An agent can use an embed directly as an argument in a tool call, streamlining the workflow and making the agent's reasoning more direct. For example, instead of first loading a JSON file with chart data and then calling a charting tool in a second step, an agent can do it all at once:

`create_chart_from_plotly_config(config_content="&laquo;artifact_content:chart_data.json&raquo;", ...)`

The framework resolves the `artifact_content` embed first, loading the file's content, and then passes the resulting JSON string directly to the `create_chart_from_plotly_config` tool.

#### Recursive Embeds for Document Inclusion

The power of embeds is further amplified through recursion. A text-based artifact, such as a Markdown report, can itself contain embed directives. When this report is embedded into another response (e.g., `&laquo;artifact_content:monthly_summary.md&raquo;`), the framework first resolves all the embeds *within* `monthly_summary.md`. This allows for the creation of complex, composite documents where a main report can dynamically include the latest data from other files—such as embedding a table from a CSV or a chart's metadata—ensuring the final document is always up-to-date.

#### Fenced Artifact Creation

SAM extends this concept to allow the LLM to create new artifacts directly within its response stream using a special fenced block syntax. The agent can simply "write" the file content inside this block, and the framework will automatically parse and save it as a new artifact.

For example, to create a simple Python script, the agent would output:

<pre>
&laquo;&laquo;&laquo;save_artifact: filename="hello.py" mime_type="text/x-python" description="A simple Python script."&raquo;&raquo;&raquo;
def main():
    print("Hello, World!")

if __name__ == "__main__":
    main()
&raquo;&raquo;&raquo;
</pre>

The framework handles the extraction and saving of this content seamlessly. This feature transforms prompt engineering, enabling agents to perform complex data manipulation and content composition tasks more naturally and efficiently, leading to richer and more dynamic outputs.

## Advanced ADK Lifecycle Customization (Callbacks)

SAM enhances the standard ADK by inserting custom logic at critical moments in an agent's lifecycle—before it thinks, after it calls a tool, and before it responds. This is achieved through a series of "callbacks" that act like intelligent checkpoints, adding powerful new capabilities that are not available in the ADK by default.

*   **Intelligent Content Processing:** When an agent uses an external tool (like an MCP tool) that returns complex data, SAM doesn't just pass back a raw JSON file. A custom callback intercepts the response, intelligently parses its contents, and automatically saves each part as a distinct, properly typed artifact. For example, a single response containing a report and three images becomes four separate artifacts: one Markdown file for the text and three individual image files, each with its own metadata. This makes the output immediately useful and understandable for both the LLM and the user.

*   **Dynamic Instruction Injection:** An agent's capabilities can change in real-time as new peer agents are discovered or as user permissions change. SAM's callbacks dynamically inject up-to-date instructions into the LLM's system prompt just before it generates a response. This ensures the agent is always aware of the tools it can use and the peers it can delegate to at that exact moment.

*   **Proactive History Repair:** To prevent the LLM from getting confused by incomplete interactions, SAM includes a self-healing mechanism. If a tool is called but fails to return a response, a callback automatically inserts a synthetic error message into the conversation history. This "history repair" ensures the conversation remains coherent and prevents the agent from getting stuck waiting for a response that will never arrive.

*   **Capability Filtering:** For security and personalization, a callback filters the list of tools presented to the LLM based on the current user's permissions, which are resolved at runtime. This ensures that users can only see and invoke tools they are authorized to use, providing a critical layer of access control.

*   **Automatic Continuation:** LLMs have a limit on how much text they can generate in a single response. If an agent's response is cut off by this limit, a SAM callback detects the interruption and automatically re-prompts the LLM to continue generating from where it left off. This process is seamless to the end-user, allowing the agent to produce long, detailed documents or code blocks that would otherwise be impossible.

## Configuration & Initialization Framework

SAM provides a robust and declarative framework that simplifies how agents are defined, configured, and launched. This eliminates boilerplate code and ensures that agents start up reliably and predictably.

First, every agent is defined through a single, comprehensive **declarative configuration file**. This file acts as the agent's blueprint, specifying everything from its name and the AI model it uses, to which tools it has access to and how it connects to other enterprise services. SAM validates this entire configuration at startup, catching errors early and preventing misconfigured agents from running.

Based on this configuration, SAM handles the complex setup process automatically. It generates all the necessary **event broker topic subscriptions** required for the agent to communicate on the mesh. Developers don't need to know the low-level details of the A2A protocol; the framework ensures the agent is listening on the correct channels for requests, peer responses, and discovery messages.

The framework also features a flexible **configuration-driven tool loading** system. In the agent's configuration file, developers can enable tools from various sources: a pre-built library of common functions (e.g., data analysis, image generation), custom Python functions, or entire toolsets from external systems. This makes it easy to assemble agents with different specializations and to enable or disable capabilities without changing any code.

Finally, SAM provides a hook for custom **agent initialization logic**. Developers can specify a function to be run when the agent starts, which is perfect for setting up connections to proprietary databases, loading specialized models, or preparing any other custom resources the agent's tools will need to perform their tasks.


## Security & Configuration Middleware

*To be detailed in a future section.*

## Rich Built-in Tool Library

*To be detailed in a future section.*

## Observability & Debugging

*To be detailed in a future section.*
