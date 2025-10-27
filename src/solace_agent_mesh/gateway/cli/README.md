# CLI Gateway

A simple, interactive command-line gateway for Solace Agent Mesh built using the generic gateway adapter pattern.

## Features

- **Interactive REPL** with `sam> ` prompt using `prompt_toolkit`
- **Separated Input & Output** - Your prompt stays at the bottom while responses stream above
- **Rich Terminal UI** with markdown rendering, syntax highlighting, and tables
- **Streaming Responses** - See agent responses as they're generated
- **Smart Status Bar** - Updates in place (only shown when active)
  - Shows agent thinking status
  - Displays artifact creation progress
  - Hides when idle for clean interface
- **Auto-Save Artifacts** - Artifacts are automatically saved as they're created
  - Collision handling (adds _2, _3, etc. on duplicate names)
  - Compact one-line notifications
  - Configurable download directory
- **Slash Commands**:
  - `/help` - Show available commands
  - `/artifacts` - List artifacts in the current session
  - `/download <filename>` - Manually download an artifact
  - `/exit` or `/quit` - Exit the CLI gateway

## Configuration

The CLI gateway uses minimal configuration with optional enhancements:

```yaml
gateway_adapter: solace_agent_mesh.gateway.cli.adapter.CliAdapter

adapter_config:
  default_agent_name: OrchestratorAgent    # Which agent to send requests to
  prompt_style: "sam> "                     # Optional: customize the prompt
  auto_save_artifacts: true                 # Optional: auto-save artifacts (default: true)
  artifact_download_dir: "./artifacts"      # Optional: where to save (default: current dir)
```

See `examples/gateways/cli_gateway_example.yaml` for a complete configuration example.

## Usage

1. **Start the gateway:**
   ```bash
   sam run --config examples/gateways/cli_gateway_example.yaml
   ```

2. **Interact with the agent:**
   ```
   sam> Hello, what can you help me with?
   ```

   The response will stream above with full markdown formatting, while your prompt stays at the bottom.

3. **Watch status updates:**
   ```
   ⏳ Analyzing your request...
   📄 Creating report.pdf (245 KB)...
   ```

   Status appears above the prompt and updates in place.

4. **Artifacts are auto-saved:**
   ```
   📄 report.pdf (v1, 245 KB) → ./report.pdf
   ```

   Compact notification shows when artifacts are saved.

5. **Use slash commands:**
   ```
   sam> /help
   sam> /artifacts
   sam> /download myfile.csv
   ```

6. **Exit:**
   ```
   sam> /exit
   ```
   Or press `Ctrl+D`

## User Experience Improvements

### Before vs. After

**Before:**
- Prompt mixed with streaming output
- Status messages created new lines (cluttered)
- Manual artifact downloads
- Hard to track what's happening

**After:**
- ✅ Prompt stays at bottom, output scrolls above
- ✅ Status bar updates in place, hides when idle
- ✅ Artifacts auto-save with compact notifications
- ✅ Clear separation of concerns

### Example Session

```
🚀 SAM CLI Gateway

Type your message or use /help for commands.
Press Ctrl+D or type /exit to quit.

sam> Create a data analysis report for sales.csv

[Agent response streams here with markdown formatting...]

📄 sales_analysis.csv (v1, 45 KB) → ./sales_analysis.csv
📄 sales_report.pdf (v2, 312 KB) → ./sales_report.pdf

✅ Task complete.

sam> /artifacts

┌─ Artifacts (2 found) ─────────────────────────────────────┐
│ Filename              │ Version │ Description       │ ...  │
├───────────────────────┼─────────┼───────────────────┼──────┤
│ sales_analysis.csv    │ 1       │ Cleaned sales...  │ ...  │
│ sales_report.pdf      │ 2       │ Complete anal...  │ ...  │
└───────────────────────────────────────────────────────────┘

sam> /exit
Goodbye! 👋
```

## Architecture

The CLI gateway demonstrates the generic gateway adapter pattern:

### Files

- **`adapter.py`** - `CliAdapter` implements `GatewayAdapter` interface
  - Handles lifecycle (init/cleanup)
  - Converts CLI input to `SamTask`
  - Manages live display with separated content/status/prompt
  - Streams responses with rich formatting
  - Handles status updates in a persistent status bar
  - Auto-saves artifacts with collision handling
  - Processes errors gracefully

- **`repl.py`** - `CliRepl` implements the interactive loop
  - Uses `prompt_toolkit` for better input handling
  - Reads user input asynchronously (stays at bottom)
  - Routes slash commands to handlers
  - Delegates regular messages to the adapter
  - Handles Ctrl+C and Ctrl+D gracefully

- **`utils.py`** - Console utilities and helpers
  - Rich console setup and markdown rendering
  - Artifact auto-save with collision handling
  - Compact artifact summaries
  - Size formatting utilities

### Key Implementation Details

- **Separated Layout**: Uses `Rich.Live` with a `Group` of renderables:
  - Content lines (accumulated and flushed)
  - Streaming text buffer (rendered as Markdown)
  - Status panel (only shown when `current_status` is set)

- **Auto-Save Flow**:
  1. Artifact progress shows in status: `📄 Creating report.pdf (245 KB)...`
  2. On completion: Load content, save with collision handling
  3. Clear status, add compact summary to content
  4. Display refreshes automatically

- **Collision Handling**: If `report.pdf` exists, saves as `report_2.pdf`, `report_3.pdf`, etc.

- **Session Scoping**: Each CLI invocation has a unique `session_id`

- **Default Authentication**: Uses `cli_user` - no authentication required

## Implementation Notes

- Streaming text is rendered as Markdown in real-time
- Status bar only appears when there's active status (no clutter when idle)
- `prompt_toolkit.patch_stdout()` keeps the prompt at bottom during output
- Auto-save is configurable per adapter instance
- Artifacts save to current directory by default (configurable)
- The REPL runs in a background task, allowing async operations
