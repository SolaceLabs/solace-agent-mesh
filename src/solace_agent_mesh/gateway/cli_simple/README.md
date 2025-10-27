# Simple CLI Gateway - Getting Started Example

**The simplest possible gateway implementation** - perfect for learning the adapter pattern.

## Why This Example?

This is a minimal "Hello World" gateway with:
- ✅ **Single file** - Just `adapter.py` (~150 lines)
- ✅ **No dependencies** - Pure Python + Pydantic
- ✅ **Easy to understand** - Clear, commented code
- ✅ **Fully functional** - Actually works end-to-end

Use this as a starting point to understand how gateway adapters work,
then move to more sophisticated examples like `cli_pt/` or `slack/`.

## What It Does

```
=== SAM Simple CLI Gateway ===
Type your message and press Enter.
Type /exit or press Ctrl+D to quit.

sam> Hello, what's 2+2?
⏳ Processing your request...

Hello! 2 + 2 = 4

✅ Task complete.

sam> Create a report
⏳ Analyzing request...
📄 Creating report.txt...
✅ Artifact created: report.txt (v1)
   A sample report document

Here's your report...

✅ Task complete.

sam> /exit

Goodbye!
```

## Configuration

```yaml
gateway_adapter: solace_agent_mesh.gateway.cli_simple.adapter.SimpleCliAdapter

adapter_config:
  default_agent_name: OrchestratorAgent  # Which agent to talk to
```

See `examples/gateways/cli_simple_gateway_example.yaml` for complete config.

## Usage

```bash
sam run --config examples/gateways/cli_simple_gateway_example.yaml
```

## Code Walkthrough

### Required Methods

Every `GatewayAdapter` must implement these 5 methods:

#### 1. **`extract_auth_claims()`** - Who is the user?
```python
async def extract_auth_claims(self, external_input: Dict, ...) -> AuthClaims:
    return AuthClaims(id="cli_user", source="cli")
```
Returns user identity. Simple version uses default user.

#### 2. **`prepare_task()`** - Convert input to SamTask
```python
async def prepare_task(self, external_input: Dict, ...) -> SamTask:
    text = external_input.get("text", "")
    return SamTask(
        parts=[self.context.create_text_part(text)],
        session_id=self.session_id,
        target_agent=self.config.default_agent_name,
        is_streaming=True,
    )
```
Transforms your platform's input format into the standard `SamTask` format.

#### 3. **`handle_update()`** - Process agent responses
```python
async def handle_update(self, update: SamUpdate, context: ResponseContext):
    for part in update.parts:
        if isinstance(part, SamTextPart):
            print(part.text, end="", flush=True)  # Stream text
        elif isinstance(part, SamFilePart):
            print(f"\n📄 File: {part.name}")  # Show file info
        elif isinstance(part, SamDataPart):
            # Handle status updates, artifact progress, etc.
            ...
```
Called repeatedly as the agent streams its response.

#### 4. **`handle_task_complete()`** - Task finished
```python
async def handle_task_complete(self, context: ResponseContext):
    print("\n\n✅ Task complete.\n")
```
Called once when the agent finishes.

#### 5. **`handle_error()`** - Something went wrong
```python
async def handle_error(self, error: SamError, context: ResponseContext):
    print(f"\n❌ Error: {error.message}\n")
```
Called if there's an error.

## What's Simplified

This example intentionally skips:
- ❌ Fancy formatting (no Rich, no colors, just plain text)
- ❌ Artifact auto-save (just shows artifact info)
- ❌ Markdown rendering (shows raw text)
- ❌ Multiple commands (just /exit)
- ❌ Bottom toolbars or status bars
- ❌ Complex UI layouts

All these features are shown in the more complete examples (`cli_pt/`, `slack/`).

## Architecture

```
User Input → prepare_task() → Agent → handle_update() → User Output
                                    ↓
                              handle_task_complete()
```

**That's it!** The generic gateway framework handles:
- A2A protocol complexity
- Message routing
- Session management
- Artifact storage
- Authentication flow

You just implement platform-specific I/O.

## Next Steps

Once you understand this example, explore:
- **`cli_pt/`** - Full-featured CLI with Rich markdown, auto-save, and more
- **`slack/`** - Production-ready Slack gateway with buttons, threading, etc.
- **`webhook/`** - HTTP webhook gateway for integrations

## Learning Exercise

Try modifying this example to:
1. Add colored output (add `from rich.console import Console`)
2. Save artifacts to a folder (add file I/O in `handle_update`)
3. Add a `/help` command (add command handling)
4. Support file uploads (handle files in `prepare_task`)

Each addition teaches you more about the framework! 🚀
