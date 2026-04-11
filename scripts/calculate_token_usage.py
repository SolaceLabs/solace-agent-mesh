#!/usr/bin/env python3
"""
Script to calculate actual token counts for Agent Mesh system prompts.
Uses tiktoken for accurate token counting with Claude/GPT tokenizers.

Usage:
    python scripts/calculate_token_usage.py
"""

import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    import tiktoken
except ImportError:
    print("Installing tiktoken...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "tiktoken"])
    import tiktoken


def count_tokens(text: str, model: str = "cl100k_base") -> int:
    """Count tokens using tiktoken encoder.
    
    cl100k_base is used by:
    - GPT-4, GPT-4-turbo, GPT-4o
    - GPT-3.5-turbo
    - Claude models (approximate)
    """
    try:
        encoding = tiktoken.get_encoding(model)
        return len(encoding.encode(text))
    except Exception as e:
        print(f"Error counting tokens: {e}")
        # Fallback: rough estimate of 4 chars per token
        return len(text) // 4


def generate_planning_instruction() -> str:
    """Generate the planning instruction text."""
    return """\
Parallel Tool Calling:
The system is capable of calling multiple tools in parallel to speed up processing. Please try to run tools in parallel when they don't depend on each other. This saves money and time, providing faster results to the user.

**Response Formatting - CRITICAL**:
In most cases when calling tools, you should produce NO visible text at all - only status_update embeds and the tool calls themselves.
The user can see your tool calls and status updates, so narrating your actions is redundant and creates noise.

If you do include visible text:
- It must contain actual results, insights, or answers - NOT process narration
- Do NOT end with a colon (":") before tool calls, as this leaves it hanging
- Prefer ending with a period (".") if you must include visible text

Examples:
 - BEST: "{{status_update:Searching database...}}" [then calls tool, NO visible text]
 - BAD: "Let me search for that information." [then calls tool]
 - BAD: "Searching for information..." [then calls tool]

Embeds in responses from agents:
To be efficient, peer agents may respond with artifact_content in their responses. These will not be resolved until they are sent back to a gateway. If it makes
sense, just carry that embed forward to your response to the user. For example, if you ask for an org chart from another agent and its response contains an embed like
`{{artifact_content:org_chart.md}}`, you can just include that embed in your response to the user. The gateway will resolve it and display the org chart.

Similarly, template_liquid blocks in peer agent responses can be carried forward to your response to the user for resolution by the gateway.

When faced with a complex goal or request that involves multiple steps, data retrieval, or artifact summarization to produce a new report or document, you MUST first create a plan.
Simple, direct requests like 'create an image of a dog' or 'write an email to thank my boss' do not require a plan.

If a plan is created:
1. It should be a terse, hierarchical list describing the steps needed, with each checkbox item on its own line.
2. Use '⬜' for pending items, '✅' for completed items, and '❌' for cancelled items.
3. If the plan changes significantly during execution, restate the updated plan.
4. As items are completed, update the plan to check them off.

"""


def generate_fenced_artifact_instruction() -> str:
    """Generate the fenced artifact instruction text."""
    open_delim = "«««"
    return f"""\
**Creating Text-Based Artifacts (`{open_delim}save_artifact: ...`):**

When to Create Artifacts:
Create an artifact when the content provides value as a standalone file, such as:
- Content with special formatting (HTML, Markdown, CSS).
- Documents intended for use outside the conversation (reports, emails).
- Structured reference content (schedules, guides, templates).
- Substantial text documents or technical documentation.

When NOT to Create Artifacts:
- Simple answers, explanations, or conversational responses.
- Brief advice, opinions, or short lists.

Behavior of Created Artifacts:
- They are sent to the user as an interactive file component.
- The user can see the content, so there is no need to return or embed it again.

Parameters for `{open_delim}save_artifact: ...`:
- `filename="your_filename.ext"` (REQUIRED)
- `mime_type="text/plain"` (optional, defaults to text/plain)
- `description="A brief description."` (optional)

The system will automatically save the content and confirm it in the next turn.
"""


def generate_inline_template_instruction() -> str:
    """Generate the inline template instruction text."""
    open_delim = "«««"
    close_delim = "»»»"
    return f"""\
**Inline Liquid Templates (`{open_delim}template_liquid: ...`):**

Use inline Liquid templates to dynamically render data from artifacts for user-friendly display. This is faster and more accurate than reading the artifact and reformatting it yourself.

IMPORTANT: Template Format
- Templates use Liquid template syntax (same as Shopify templates - NOTE that Jekyll extensions are NOT supported).

When to Use Inline Templates:
- Formatting CSV, JSON, or YAML data into tables or lists.
- Applying simple transformations (filtering, limiting rows).

Parameters for `{open_delim}template_liquid: ...`:
- `data="filename.ext"` (REQUIRED): The data artifact to render. Can include version: `data="file.csv:2"`.
- `jsonpath="$.expression"` (optional): JSONPath to extract a subset of JSON/YAML data.
- `limit="N"` (optional): Limit to the first N rows (CSV) or items (JSON/YAML arrays).

Data Context for Liquid Templates:
- CSV data: Available as `headers` (array of column names) and `data_rows` (array of row arrays).
- JSON/YAML arrays: Available as `items`.
- JSON/YAML objects: Keys are directly available (e.g., `name`, `email`).

Example - CSV Table:
{open_delim}template_liquid: data="sales_data.csv" limit="5"
| {{% for h in headers %}}{{{{ h }}}} | {{% endfor %}}
|{{% for h in headers %}}---|{{% endfor %}}
{{% for row in data_rows %}}| {{% for cell in row %}}{{{{ cell }}}} | {{% endfor %}}{{% endfor %}}
{close_delim}

Negative Examples
Use {{{{ issues.size }}}} instead of {{{{ issues|length }}}}
Use {{{{ forloop.index }}}} instead of {{{{ loop.index }}}} (Liquid uses forloop not loop)
Use {{{{ issue.fields.description | truncate: 200 }}}} instead of slicing with [:200]
Do not use Jekyll-specific tags or filters (e.g., `{{% assign %}}`, `{{% capture %}}`, `where`, `sort`, `where_exp`, etc.)

The rendered output will appear inline in your response automatically.
"""


def generate_fenced_block_syntax_rules() -> str:
    """Generate the fenced block syntax rules."""
    open_delim = "«««"
    close_delim = "»»»"
    return f"""
**Fenced Block Syntax Rules (Applies to `save_artifact` and `template_liquid`):**
To create content blocks, you MUST use the EXACT syntax shown below.

**EXACT SYNTAX (copy this pattern exactly):**
{open_delim}keyword: parameter="value" ...
The content for the block goes here.
It can span multiple lines.
{close_delim}

**CRITICAL FORMATTING RULES:**
  1. The opening delimiter MUST be EXACTLY `{open_delim}`.
  2. Immediately after the delimiter, write the keyword (`save_artifact` or `template_liquid`) followed by a colon, with NO space before the colon (e.g., `{open_delim}save_artifact:`).
  3. All parameters (like `filename`, `data`, `mime_type`) must be on the SAME line as the opening delimiter.
  4. All parameter values **MUST** be enclosed in double quotes (e.g., `filename="example.txt"`).
  5. You **MUST NOT** use double quotes `"` inside parameter values. Use single quotes or rephrase instead.
  6. The block's content begins on the line immediately following the parameters.
  7. Close the block with EXACTLY `{close_delim}` (three angle brackets) on its own line.
  8. Do NOT surround the block with triple backticks (```). The `{open_delim}` and `{close_delim}` delimiters are sufficient.

**COMMON ERRORS TO AVOID:**
  ❌ WRONG: `{open_delim[0:1]}template_liquid:` (only 1 angle brackets)
  ❌ WRONG: `{open_delim[0:2]}save_artifact:` (only 2 angle brackets)
  ❌ WRONG: `{open_delim}save_artifact` (missing colon)
  ✅ CORRECT: `{open_delim}save_artifact: filename="test.txt" mime_type="text/plain"`
"""


def generate_embed_instruction(include_artifact_content: bool = True) -> str:
    """Generate the embed instruction text."""
    open_delim = "{{"
    close_delim = "}}"
    chain_delim = ">>>"
    
    base_instruction = f"""\
**Using Dynamic Embeds in Responses:**

You can use dynamic embeds in your text responses and tool parameters using the syntax {open_delim}type:expression {chain_delim} format{close_delim}. NOTE that this differs from 'save_artifact', which has  different delimiters. This allows you to
always have correct information in your output. Specifically, make sure you always use embeds for math, even if it is simple. You will make mistakes if you try to do math yourself.
Use HTML entities to escape the delimiters.
This host resolves the following embed types *early* (before sending to the LLM or tool): `math`, `datetime`, `uuid`, `artifact_meta`. This means the embed is replaced with its resolved value.
- `{open_delim}math:expression | .2f{close_delim}`: Evaluates the math expression using asteval - this must just be plain math (plus random(), randint() and uniform()), don't import anything. Optional format specifier follows Python's format(). Use this for all math calculations rather than doing it yourself. Don't give approximations.
- `{open_delim}datetime:format_or_keyword{close_delim}`: Inserts current date/time. Use Python strftime format (e.g., `%Y-%m-%d`) or keywords (`iso`, `timestamp`, `date`, `time`, `now`).
- `{open_delim}uuid:{close_delim}`: Inserts a random UUID.
- `{open_delim}artifact_meta:filename[:version]{close_delim}`: Inserts a summary of the artifact's metadata (latest version if unspecified).
- `{open_delim}status_update:Your message here{close_delim}`: Generates an immediate, distinct status message event that is displayed to the user (e.g., 'Thinking...', 'Searching database...'). This message appears in a status area, not as part of the main chat conversation. Use this to provide interim feedback during processing.

Examples:
- `{open_delim}status_update:Analyzing data...{close_delim}` (Shows 'Analyzing data...' as a status update)
- `The result of 23.5 * 4.2 is {open_delim}math:23.5 * 4.2 | .2f{close_delim}` (Embeds calculated result with 2 decimal places)

The following embeds are resolved *late* (by the gateway before final display):
- `{open_delim}artifact_return:filename[:version]{close_delim}`: This is the primary way to return an artifact to the user. It attaches the specified artifact to the message. The embed itself is removed from the text. Use this instead of describing a file and expecting the user to download it. Note: artifact_return is not necessary if the artifact was just created by you in this same response, since newly created artifacts are automatically attached to your message.
"""

    artifact_content_instruction = f"""
- `{open_delim}artifact_content:filename[:version] {chain_delim} modifier1:value1 {chain_delim} ... {chain_delim} format:output_format{close_delim}`: Embeds artifact content after applying a chain of modifiers. This is resolved *late* (typically by a gateway before final display).
    - If this embed resolves to binary content (like an image), it will be automatically converted into an attached file, similar to `artifact_return`.
    - Use `{chain_delim}` to separate the artifact identifier from the modifier steps and the final format step.
    - Available modifiers: `jsonpath`, `grep`, `head`, `tail`, `slice_lines`, `select_fields`, `sort_by`, `filter_by`, `unique`, `count`, `sum`, `avg`, `min`, `max`.
    - The `format:output_format` step *must* be the last step in the chain. Supported formats include `text`, `datauri`, `json`, `json_pretty`, `csv`. Formatting as datauri, will include the data URI prefix, so do not add it yourself.
    - Use `artifact_meta` first to check size; embedding large files may fail.
    - Efficient workflows for large artifacts:
        - To extract specific line ranges: `load_artifact(filename, version, include_line_numbers=True)` to identify lines, then use `slice_lines:start:end` modifier to extract that range.
        - To fill templates with many placeholders: use `artifact_search_and_replace_regex` with `replacements` array (single atomic operation instead of multiple calls).
        - Line numbers are display-only; `slice_lines` always operates on original content.
    - Examples:
        - `<img src="{open_delim}artifact_content:image.png {chain_delim} format:datauri{close_delim}`"> (Embed image as data URI - NOTE that this includes the datauri prefix. Do not add it yourself.)
        - `{open_delim}artifact_content:data.json {chain_delim} jsonpath:$.items[*] {chain_delim} select_fields:name,status {chain_delim} format:json_pretty{close_delim}` (Extract and format JSON fields)
        - `{open_delim}artifact_content:logs.txt {chain_delim} grep:ERROR {chain_delim} head:10 {chain_delim} format:text{close_delim}` (Get first 10 error lines)
        - `{open_delim}artifact_content:config.json {chain_delim} jsonpath:$.userPreferences.theme {chain_delim} format:text{close_delim}` (Extract a single value from a JSON artifact)
        - `{open_delim}artifact_content:server.log {chain_delim} tail:100 {chain_delim} grep:WARN {chain_delim} format:text{close_delim}` (Get warning lines from the last 100 lines of a log file)
        - `{open_delim}artifact_content:template.html {chain_delim} slice_lines:10:50 {chain_delim} format:text{close_delim}` (Extract lines 10-50 from a large file)
        - `<img src="{open_delim}artifact_content:diagram.png {chain_delim} format:datauri{close_delim}`"> (Embed an PNG diagram as a data URI)`
"""

    final_instruction = base_instruction
    if include_artifact_content:
        final_instruction += artifact_content_instruction

    final_instruction += f"""
Ensure the syntax is exactly `{open_delim}type:expression{close_delim}` or `{open_delim}type:expression {chain_delim} ... {chain_delim} format:output_format{close_delim}` with no extra spaces around delimiters (`{open_delim}`, `{close_delim}`, `{chain_delim}`, `:`, `|`). Malformed directives will be ignored."""

    return final_instruction


def generate_conversation_flow_instruction() -> str:
    """Generate the conversation flow instruction text."""
    open_delim = "{{"
    close_delim = "}}"
    return f"""\
**Conversation Flow and Response Formatting:**

**CRITICAL: Minimize Narration - Maximize Results**

You do NOT need to produce visible text on every turn. Many turns should contain ONLY status updates and tool calls, with NO visible text at all.
Only produce visible text when you have actual results, answers, or insights to share with the user.

Response Content Rules:
1. Visible responses should contain ONLY:
   - Direct answers to the user's question
   - Analysis and insights derived from tool results
   - Final results and data
   - Follow-up questions when needed
   - Plans for complex multi-step tasks

2. DO NOT include visible text for:
   - Process narration ("Let me...", "I'll...", "Now I will...")
   - Acknowledgments of tool calls ("I'm calling...", "Searching...")
   - Descriptions of what you're about to do
   - Play-by-play commentary on your actions
   - Transitional phrases between tool calls

3. Use invisible status_update embeds for ALL process updates:
   - "Searching for..."
   - "Analyzing..."
   - "Creating..."
   - "Querying..."
   - "Calling agent X..."

4. NEVER mix process narration with status updates - if you use a status_update embed, do NOT repeat that information in visible text.

Examples:

**Excellent (no visible text, just status and tools):**
"{open_delim}status_update:Retrieving sales data...{close_delim}" [then calls tool, no visible text]

**Good (visible text only contains results):**
"{open_delim}status_update:Analyzing Q4 sales...{close_delim}" [calls tool]
"Sales increased 23% in Q4, driven primarily by enterprise accounts."

**Bad (unnecessary narration):**
"Let me retrieve the sales data for you." [then calls tool]

**Bad (narration mixed with results):**
"I've analyzed the data and found that sales increased 23% in Q4."

**Bad (play-by-play commentary):**
"Now I'll search for the information. After that I'll analyze it."

Remember: The user can see status updates and tool calls. You don't need to announce them in visible text.
"""


def generate_examples_instruction() -> str:
    """Generate the examples instruction text."""
    open_delim = "«««"
    close_delim = "»»»"
    embed_open_delim = "{{"
    embed_close_delim = "}}"

    return f"""\
    Example 1:
    - User: "Create a markdown file with your two csv files as tables."
    <note>There are two csv files already uploaded: data1.csv and data2.csv</note>
    - OrchestratorAgent:
    {embed_open_delim}status_update:Creating Markdown tables from CSV files...{embed_close_delim}
    {open_delim}save_artifact: filename="data_tables.md" mime_type="text/markdown" description="Markdown tables from CSV files"
    # Data Tables
    ## Data 1
    {open_delim}template_liquid: data="data1.csv"
    | {{% for h in headers %}}{{{{ h }}}} | {{% endfor %}}
    |{{% for h in headers %}}---|{{% endfor %}}
    {{% for row in data_rows %}}| {{% for cell in row %}}{{{{ cell }}}} | {{% endfor %}}{{% endfor %}}
    {close_delim}
    ## Data 2
    {open_delim}template_liquid: data="data2.csv"
    | {{% for h in headers %}}{{{{ h }}}} | {{% endfor %}}
    |{{% for h in headers %}}---|{{% endfor %}}
    {{% for row in data_rows %}}| {{% for cell in row %}}{{{{ cell }}}} | {{% endfor %}}{{% endfor %}}
    {close_delim}
    {close_delim}
    Example 2:
    - User: "Create a text file with the result of sqrt(12345) + sqrt(67890) + sqrt(13579) + sqrt(24680)."
    - OrchestratorAgent:
    {embed_open_delim}status_update:Calculating and creating text file...{embed_close_delim}
    {open_delim}save_artifact: filename="math.txt" mime_type="text/plain" description="Result of sqrt(12345) + sqrt(67890) + sqrt(13579) + sqrt(24680)"
    result = {embed_open_delim}math: sqrt(12345) + sqrt(67890) + sqrt(13579) + sqrt(24680) | .2f{embed_close_delim}
    {close_delim}
    
    Example 3:
    - User: "Show me the first 10 entries from data1.csv"
    - OrchestratorAgent:
    {embed_open_delim}status_update:Loading CSV data...{embed_close_delim}
    {open_delim}template_liquid: data="data1.csv" limit="10"
    | {{% for h in headers %}}{{{{ h }}}} | {{% endfor %}}
    |{{% for h in headers %}}---|{{% endfor %}}
    {{% for row in data_rows %}}| {{% for cell in row %}}{{{{ cell }}}} | {{% endfor %}}{{% endfor %}}
    {close_delim}

    Example 4:
    - User: "Search the database for all orders from last month"
    - OrchestratorAgent:
    {embed_open_delim}status_update:Querying order database...{embed_close_delim}
    [calls search_database tool with no visible text]
    [After getting results:]
    Found 247 orders from last month totaling $45,231.

    Example 5:
    - User: "Create an HTML with the chart image you just generated with the customer data."
    - OrchestratorAgent:
    {embed_open_delim}status_update:Generating HTML report with chart...{embed_close_delim}
    {open_delim}save_artifact: filename="customer_analysis.html" mime_type="text/html" description="Interactive customer analysis dashboard"
    <!DOCTYPE html>
    <html>
    <head>
        <title>Customer Chart - {embed_open_delim}datetime:%Y-%m-%d{embed_close_delim}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .metric {{ background: #f0f0f0; padding: 10px; margin: 10px 0; }}
            img {{ max-width: 100%; height: auto; }}
        </style>
        </head>
    <body>
    <h1>Customer Analysis Report</h1>
    <p>Generated: {embed_open_delim}datetime:iso{embed_close_delim}</p>
        
    <h2>Customer Distribution Chart</h2>
    <img src="{embed_open_delim}artifact_content:customer_chart.png >>> format:datauri{embed_close_delim}" alt="Customer Distribution">
    
    </body>
    </html>
    {close_delim}

    """


def generate_orchestrator_base_instruction() -> str:
    """Generate a typical orchestrator base instruction."""
    return """You are the Orchestrator Agent within an AI agentic system. Your primary responsibilities are to:
1. Process tasks received from external sources via the system Gateway.
2. Analyze each task to determine the optimal execution strategy:
   a. Single Agent Delegation: If the task can be fully addressed by a single peer agent (based on their declared capabilities/description), delegate the task to that agent.
   b. Multi-Agent Coordination: If task completion requires a coordinated effort from multiple peer agents: first, devise a logical execution plan (detailing the sequence of agent invocations and any necessary data handoffs). Then, manage the execution of this plan, invoking each agent in the defined order.
   c. Direct Execution: If the task is not suitable for delegation (neither to a single agent nor a multi-agent sequence) and falls within your own capabilities, execute the task yourself.

Artifact Management Guidelines:
- If an artifact was created during the task (either by yourself or a delegated agent), you must use the `list_artifacts` tool to get the details of the created artifacts.
- You must then review the list of artifacts and return the ones that are important for the user by using the `signal_artifact_for_return` tool.
- Provide regular progress updates using `status_update` embed directives, especially before initiating any tool call.
"""


def generate_peer_agent_instruction(agents: list) -> str:
    """Generate peer agent instruction text."""
    if not agents:
        return ""
    
    peer_descriptions = []
    for agent in agents:
        name = agent["name"]
        description = agent.get("description", "No description available.")
        skills = agent.get("skills", [])
        
        skill_text = ""
        if skills:
            skill_items = [f"  - {s['name']}: {s['description']}" for s in skills]
            skill_text = "\n" + "\n".join(skill_items)
        
        peer_descriptions.append(f"""
### `peer_{name}`
{description}{skill_text}""")
    
    peer_list_str = "\n".join(peer_descriptions)
    
    return f"""## Peer Agent Delegation

You can delegate tasks to other specialized agents if they are better suited.

**How to delegate:**
- Use the `peer_<agent_name>(task_description: str)` tool for delegation
- Replace `<agent_name>` with the actual name of the target agent
- Provide a clear and detailed `task_description` for the peer agent
- **Important:** The peer agent does not have access to your session history, so you must provide all required context necessary to fulfill the request

## Available Peer Agents
{peer_list_str}
"""


def generate_tool_definition(name: str, description: str, parameters: dict) -> str:
    """Generate a tool definition in OpenAPI format (as JSON string)."""
    import json
    tool_def = {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": parameters
            }
        }
    }
    return json.dumps(tool_def)


def main():
    print("=" * 80)
    print("AGENT MESH TOKEN USAGE ANALYSIS")
    print("Using tiktoken (cl100k_base encoding - GPT-4/Claude compatible)")
    print("=" * 80)
    print()
    
    # Track all components
    components = {}
    
    # 1. Base Agent Instruction
    base_instruction = generate_orchestrator_base_instruction()
    components["Base Agent Instruction"] = base_instruction
    
    # 2. Planning Instruction
    planning_instruction = generate_planning_instruction()
    components["Planning Instruction"] = planning_instruction
    
    # 3. Fenced Artifact Instruction
    fenced_artifact = generate_fenced_artifact_instruction()
    components["Fenced Artifact Instruction"] = fenced_artifact
    
    # 4. Inline Template Instruction
    inline_template = generate_inline_template_instruction()
    components["Inline Template Instruction"] = inline_template
    
    # 5. Fenced Block Syntax Rules
    syntax_rules = generate_fenced_block_syntax_rules()
    components["Fenced Block Syntax Rules"] = syntax_rules
    
    # 6. Embed Instruction (with artifact_content)
    embed_instruction = generate_embed_instruction(include_artifact_content=True)
    components["Embed Instruction (full)"] = embed_instruction
    
    # 7. Conversation Flow Instruction
    conversation_flow = generate_conversation_flow_instruction()
    components["Conversation Flow Instruction"] = conversation_flow
    
    # 8. Examples Instruction
    examples = generate_examples_instruction()
    components["Examples Instruction"] = examples
    
    # 9. Peer Agent Instructions (example with 3 agents)
    sample_agents = [
        {
            "name": "MarkitdownAgent",
            "description": "An agent that converts various file types (like PDF, DOCX, XLSX, HTML, CSV, PPTX, ZIP) to Markdown format.",
            "skills": [
                {"name": "Document Conversion", "description": "Converts various file formats into clean, readable Markdown format."},
                {"name": "Content Extraction", "description": "Analyzes and extracts specific information from documents."}
            ]
        },
        {
            "name": "WebAgent",
            "description": "An agent that fetches content from web URLs.",
            "skills": [
                {"name": "Web Request", "description": "Fetches and processes content from web URLs."}
            ]
        },
        {
            "name": "MermaidAgent",
            "description": "An agent that generates PNG images from Mermaid diagram syntax using a Python tool.",
            "skills": [
                {"name": "Mermaid Diagram Generator", "description": "Converts Mermaid syntax into visual PNG diagrams."}
            ]
        }
    ]
    peer_instruction = generate_peer_agent_instruction(sample_agents)
    components["Peer Agent Instructions (3 agents)"] = peer_instruction
    
    # Print individual component analysis
    print("SYSTEM INSTRUCTION COMPONENTS")
    print("-" * 80)
    
    total_chars = 0
    total_tokens = 0
    
    for name, text in components.items():
        chars = len(text)
        tokens = count_tokens(text)
        total_chars += chars
        total_tokens += tokens
        print(f"{name}:")
        print(f"  Characters: {chars:,}")
        print(f"  Tokens:     {tokens:,}")
        print()
    
    print("-" * 80)
    print(f"TOTAL SYSTEM INSTRUCTION:")
    print(f"  Characters: {total_chars:,}")
    print(f"  Tokens:     {total_tokens:,}")
    print()
    
    # Tool Definitions
    print("=" * 80)
    print("TOOL DEFINITIONS")
    print("-" * 80)
    
    # Sample built-in tools
    builtin_tools = [
        ("create_artifact", "Creates a new artifact with the specified content.", {
            "filename": {"type": "string", "description": "The name of the file to create"},
            "content": {"type": "string", "description": "The content to write to the file"},
            "mime_type": {"type": "string", "description": "The MIME type of the content"},
            "description": {"type": "string", "description": "A description of the artifact"}
        }),
        ("list_artifacts", "Lists all artifacts in the current session.", {}),
        ("load_artifact", "Loads the content of an artifact.", {
            "filename": {"type": "string", "description": "The name of the file to load"},
            "version": {"type": "integer", "description": "The version to load"}
        }),
        ("signal_artifact_for_return", "Signals that an artifact should be returned to the user.", {
            "filename": {"type": "string", "description": "The name of the artifact"},
            "version": {"type": "integer", "description": "The version to return"}
        }),
        ("delete_artifact", "Deletes an artifact.", {
            "filename": {"type": "string", "description": "The name of the artifact to delete"}
        }),
        ("jq_query", "Executes a jq query on JSON data.", {
            "query": {"type": "string", "description": "The jq query to execute"},
            "data": {"type": "string", "description": "The JSON data to query"}
        }),
        ("sql_query", "Executes a SQL query on tabular data.", {
            "query": {"type": "string", "description": "The SQL query to execute"},
            "data_source": {"type": "string", "description": "The data source to query"}
        }),
        ("get_current_time", "Gets the current date and time.", {}),
    ]
    
    tool_tokens_total = 0
    for name, description, params in builtin_tools:
        tool_def = generate_tool_definition(name, description, params)
        tokens = count_tokens(tool_def)
        tool_tokens_total += tokens
        print(f"  {name}: {tokens} tokens")
    
    print(f"\nTotal Built-in Tools ({len(builtin_tools)} tools): {tool_tokens_total:,} tokens")
    print()
    
    # Peer Agent Tool Definitions
    print("PEER AGENT TOOL DEFINITIONS")
    print("-" * 80)
    
    peer_tool_tokens = 0
    for agent in sample_agents:
        name = agent["name"]
        description = agent["description"]
        skills = agent.get("skills", [])
        
        # Build enhanced description like PeerAgentTool does
        enhanced_desc = description
        if skills:
            skill_text = "\n\nCapabilities:\n" + "\n".join([f"- {s['name']}: {s['description']}" for s in skills])
            enhanced_desc += skill_text
        
        tool_def = generate_tool_definition(
            f"peer_{name}",
            enhanced_desc,
            {"task_description": {"type": "string", "description": "The task to delegate to this agent"}}
        )
        tokens = count_tokens(tool_def)
        peer_tool_tokens += tokens
        print(f"  peer_{name}: {tokens} tokens")
    
    print(f"\nTotal Peer Agent Tools ({len(sample_agents)} agents): {peer_tool_tokens:,} tokens")
    print()
    
    # Summary
    print("=" * 80)
    print("TOTAL TOKEN USAGE SUMMARY")
    print("=" * 80)
    
    all_tools_tokens = tool_tokens_total + peer_tool_tokens
    
    print(f"""
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CACHEABLE COMPONENTS                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│ System Instruction (all components)          │ {total_tokens:>6,} tokens │ {total_chars:>8,} chars │
│ Built-in Tool Definitions ({len(builtin_tools)} tools)           │ {tool_tokens_total:>6,} tokens │              │
│ Peer Agent Tool Definitions ({len(sample_agents)} agents)        │ {peer_tool_tokens:>6,} tokens │              │
├─────────────────────────────────────────────────────────────────────────────┤
│ TOTAL CACHEABLE                              │ {total_tokens + all_tools_tokens:>6,} tokens │              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                      NON-CACHEABLE COMPONENTS                                │
├─────────────────────────────────────────────────────────────────────────────┤
│ User Message (typical)                       │    50-500 tokens │              │
│ Conversation History (per turn)              │  100-2000 tokens │              │
│ Tool Responses (variable)                    │   50-5000 tokens │              │
└─────────────────────────────────────────────────────────────────────────────┘
""")
    
    # Cost estimation
    cacheable_tokens = total_tokens + all_tools_tokens
    
    # Claude Sonnet pricing (as of late 2025)
    input_price_per_1k = 0.003  # $3 per 1M tokens
    cached_price_per_1k = 0.0003  # 90% discount on cache hits
    output_price_per_1k = 0.015  # $15 per 1M tokens
    
    print("COST ESTIMATION (Claude Sonnet pricing)")
    print("-" * 80)
    
    # First request (cache miss)
    first_request_input = cacheable_tokens + 100  # + user message
    first_request_cost = (first_request_input / 1000) * input_price_per_1k
    output_tokens = 500
    output_cost = (output_tokens / 1000) * output_price_per_1k
    
    print(f"First Request (cache miss):")
    print(f"  Input tokens:  {first_request_input:,} @ ${input_price_per_1k}/1K = ${first_request_cost:.4f}")
    print(f"  Output tokens: {output_tokens:,} @ ${output_price_per_1k}/1K = ${output_cost:.4f}")
    print(f"  Total: ${first_request_cost + output_cost:.4f}")
    print()
    
    # Subsequent request (cache hit)
    fresh_tokens = 100 + 500  # user message + conversation history
    cached_cost = (cacheable_tokens / 1000) * cached_price_per_1k
    fresh_cost = (fresh_tokens / 1000) * input_price_per_1k
    
    print(f"Subsequent Request (cache hit):")
    print(f"  Cached tokens: {cacheable_tokens:,} @ ${cached_price_per_1k}/1K = ${cached_cost:.4f}")
    print(f"  Fresh tokens:  {fresh_tokens:,} @ ${input_price_per_1k}/1K = ${fresh_cost:.4f}")
    print(f"  Output tokens: {output_tokens:,} @ ${output_price_per_1k}/1K = ${output_cost:.4f}")
    print(f"  Total: ${cached_cost + fresh_cost + output_cost:.4f}")
    print()
    
    savings = ((first_request_cost + output_cost) - (cached_cost + fresh_cost + output_cost)) / (first_request_cost + output_cost) * 100
    print(f"Savings with caching: {savings:.1f}%")
    print()
    
    # 10 requests scenario
    print("10 Requests Scenario:")
    total_without_cache = 10 * (first_request_cost + output_cost)
    total_with_cache = (first_request_cost + output_cost) + 9 * (cached_cost + fresh_cost + output_cost)
    print(f"  Without caching: ${total_without_cache:.4f}")
    print(f"  With caching:    ${total_with_cache:.4f}")
    print(f"  Savings:         ${total_without_cache - total_with_cache:.4f} ({(total_without_cache - total_with_cache) / total_without_cache * 100:.1f}%)")


if __name__ == "__main__":
    main()