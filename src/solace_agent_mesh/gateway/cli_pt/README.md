# CLI Gateway (Pure prompt_toolkit)

A command-line gateway for Solace Agent Mesh built entirely with `prompt_toolkit` for maximum terminal compatibility, especially in VS Code.

## Why This Version?

This is an alternative to `gateway/cli/` that uses **only prompt_toolkit** instead of mixing Rich and prompt_toolkit. This provides:

- ✅ **Perfect VS Code compatibility** - No ANSI escape code issues
- ✅ **Built-in bottom toolbar** - Status updates without cursor manipulation
- ✅ **Simpler architecture** - One library handling all terminal I/O
- ✅ **Clean output** - Text prints above the prompt automatically via `patch_stdout()`
- ✅ **No library conflicts** - prompt_toolkit manages everything

## Comparison with `cli/`

| Feature | `cli/` (Rich + prompt_toolkit) | `cli_pt/` (pure prompt_toolkit) |
|---------|-------------------------------|--------------------------------|
| Terminal compatibility | Good in native terminals | Excellent everywhere including VS Code |
| Status display | Rich Live display (in-place updates) | Bottom toolbar (always visible) |
| Markdown rendering | Full Rich markdown | HTML formatting with colors |
| Library complexity | Two libraries (can conflict) | One library (no conflicts) |
| Output handling | Rich Live context manager | prompt_toolkit patch_stdout |

## Features

- **Interactive REPL** with `sam> ` prompt
- **Bottom Toolbar** for status updates (always visible, no flicker)
- **Clean Separation** - Output prints above, prompt stays at bottom
- **Streaming Responses** - Text streams naturally with `print_formatted_text()`
- **Auto-Save Artifacts** - Artifacts saved automatically with collision handling
- **Slash Commands**: `/help`, `/artifacts`, `/download`, `/exit`
- **Rich Table** for artifact listing (only place Rich is used, for tables)

## Configuration

```yaml
gateway_adapter: solace_agent_mesh.gateway.cli_pt.adapter.CliPtAdapter

adapter_config:
  default_agent_name: OrchestratorAgent
  prompt_style: "sam> "
  auto_save_artifacts: true
  artifact_download_dir: null  # defaults to current directory
```

See `examples/gateways/cli_pt_gateway_example.yaml` for complete example.

## Usage

```bash
sam run --config examples/gateways/cli_pt_gateway_example.yaml
```

### Example Session

```
🚀 SAM CLI Gateway (prompt_toolkit)

Type your message or use /help for commands.
Press Ctrl+D or type /exit to quit.

sam> Create a sales analysis report
I'll help you create a sales analysis report...

[Response streams here naturally...]

📄 sales_analysis.csv (v1, 45 KB) → ./sales_analysis.csv
📄 sales_report.pdf (v2, 312 KB) → ./sales_report.pdf

✅ Task complete.

⏳ Creating report.pdf (245 KB)...            ← Bottom toolbar (status)
sam> /artifacts                               ← Your prompt

┌─ Artifacts (2 found) ────────────────────┐
│ Filename           │ Version │ ...        │
├────────────────────┼─────────┼────────────┤
│ sales_analysis.csv │ 1       │ ...        │
│ sales_report.pdf   │ 2       │ ...        │
└────────────────────────────────────────────┘

sam> /exit
Goodbye! 👋
```

## Architecture

### Key Components

**`adapter.py`** - Pure prompt_toolkit implementation
- Uses `PromptSession` with `bottom_toolbar` for status
- `print_formatted_text()` for all output
- `patch_stdout()` keeps output above prompt
- Auto-saves artifacts with collision handling
- Handles all SAM adapter callbacks

**`utils.py`** - Helper functions
- `print_formatted_text()` with HTML formatting
- Auto-save with collision detection
- Size formatting utilities
- No Rich dependencies

### How It Works

1. **Bottom Toolbar**:
   - `PromptSession(bottom_toolbar=self._get_toolbar)`
   - Status updates by changing `self.current_status`
   - Toolbar refreshes automatically

2. **Output Above Prompt**:
   - `with patch_stdout()` in REPL loop
   - All `print_formatted_text()` goes above the prompt
   - Prompt stays at bottom

3. **Streaming Text**:
   ```python
   print_formatted_text(text, end="")  # No newline, streams naturally
   ```

4. **Status Updates**:
   ```python
   self.current_status = "⏳ Thinking..."  # Toolbar updates automatically
   ```

5. **Artifact Auto-Save**:
   - Progress shown in toolbar: `📄 Creating file.pdf (245 KB)...`
   - On completion: Load, save with collision handling
   - Print compact summary: `📄 file.pdf (v1, 245 KB) → ./file.pdf`

## Formatting

Uses `prompt_toolkit.formatted_text.HTML` for colored output:

```python
print_formatted_text(HTML("<ansigreen>✅ Success!</ansigreen>"))
print_formatted_text(HTML("<ansired><b>Error:</b> Something failed</ansired>"))
print_formatted_text(HTML("<ansiblue>Information</ansiblue>"))
```

Supported tags:
- `<b>bold</b>`, `<i>italic</i>`, `<u>underline</u>`
- `<ansigreen>`, `<ansired>`, `<ansiblue>`, `<ansiyellow>`, etc.

## VS Code Compatibility

This version works perfectly in VS Code terminal because:
- No cursor positioning escape codes (Rich Live display)
- No complex ANSI sequences that VS Code misinterprets
- prompt_toolkit handles all terminal interactions properly
- Bottom toolbar uses simple terminal features

## Implementation Notes

- **Single library**: Only prompt_toolkit for terminal I/O (except Rich for tables)
- **No Live display**: Uses regular printing with `patch_stdout()`
- **Bottom toolbar**: Always visible, no flicker or redraw issues
- **Streaming**: Text prints character-by-character naturally
- **Session scoped**: Each CLI run has unique session ID
- **Default auth**: Uses `cli_user` identity

## When to Use This vs `cli/`

**Use `cli_pt/` when:**
- Running in VS Code integrated terminal
- Need guaranteed terminal compatibility
- Want simpler architecture with one library
- Bottom toolbar is acceptable for status

**Use `cli/` when:**
- Running in native terminal (iTerm, Terminal.app, etc.)
- Want Rich markdown rendering
- Prefer status that appears/disappears (not always visible)
- Want more sophisticated formatting options
