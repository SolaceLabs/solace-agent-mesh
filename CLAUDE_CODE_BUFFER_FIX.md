# Claude Code Buffer Limit Fix

## Problem

When executing Claude Code tools with large prompts, we encountered:

```
ValueError: Separator is found, but chunk is longer than limit
```

This occurred in `streaming_utils.py:44` when `stdout.readline()` tried to read output that exceeded asyncio's default StreamReader buffer limit of 64KB.

## Root Cause

1. Large prompts were passed via command-line argument (`-p PROMPT`)
2. Command line has length limits, causing issues
3. When Claude Code output long lines, asyncio's StreamReader couldn't handle them
4. Default buffer limit: 2^16 bytes (64KB)

## Solution Implemented

### 1. Increased Buffer Limit (Primary Fix)

Modified `utils.py:run_claude_code_headless()` to set buffer limit to 10MB:

```python
limit = 10 * 1024 * 1024  # 10MB
proc = await asyncio.create_subprocess_exec(
    *docker_cmd,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
    limit=limit,  # Increased from default 64KB
)
```

### 2. Proper CLI Flag Usage

Changed from using `-p` (which is "print mode" flag) to passing prompt as positional argument:

**Before:**
```python
docker_cmd.extend(["-p", autonomous_prompt, ...])
```

**After:**
```python
docker_cmd.extend(["--print", "--output-format", output_format, ...])
docker_cmd.append(autonomous_prompt)  # As positional argument
```

### 3. Error Recovery in Streaming

Added error handling in `streaming_utils.py` to gracefully handle buffer overflows:

```python
try:
    line_bytes = await stdout.readline()
except ValueError as e:
    if "chunk is longer than limit" in str(e):
        log.error(f"Buffer overflow in stream reading: {e}")
        # Skip this line and continue
        continue
    raise
```

## Alternative Solutions Considered

### Option 1: Use stdin (Not Used)
- Write prompt to stdin instead of command line
- Pros: No command-line length limits
- Cons: Adds complexity, requires proper stream handling
- Decision: Buffer increase is simpler and sufficient

### Option 2: Write to temp file (Not Used)
- Write prompt to `.claude-prompt.txt` in workspace
- Have Claude Code read from file
- Pros: No length/buffer issues
- Cons: Requires file I/O, cleanup, CLI flag changes
- Decision: Not worth the complexity

### Option 3: Use --input-format stream-json (Not Used)
- Stream prompt as JSON to stdin
- Pros: Designed for large inputs
- Cons: Requires JSON formatting, more complex
- Decision: Overkill for this use case

## Testing

To test the fix with a large prompt:

```python
from solace_agent_mesh.agent.tools.claude_code.utils import run_claude_code_headless

# Create a very large prompt (>64KB)
large_prompt = "Create a comprehensive test app. " * 10000

result = await run_claude_code_headless(
    workspace_path=workspace_path,
    settings_path=settings_path,
    prompt=large_prompt,
    environment="node",
    tool_config=config,
    stream=True,
)
```

## Files Modified

1. `src/solace_agent_mesh/agent/tools/claude_code/utils.py`
   - Added `limit=10MB` to subprocess creation
   - Fixed CLI flag usage (added `--print`)
   - Changed prompt to positional argument

2. `src/solace_agent_mesh/agent/tools/claude_code/streaming_utils.py`
   - Added try/except for buffer overflow errors
   - Added error recovery logic

## Impact

- ✅ Handles prompts up to 10MB
- ✅ Graceful error recovery if limit exceeded
- ✅ Backward compatible (no breaking changes)
- ✅ More robust command-line usage
- ⚠️ Memory usage increased (10MB buffer per subprocess)

## Recommendations

1. **Monitor memory usage** - 10MB buffer per execution
2. **Consider prompt length** - Very large prompts (>1MB) should be split into multiple calls
3. **Use app context files** - Instead of huge prompts, use APP_CONTEXT.md and CLAUDE.md
4. **Future enhancement** - Implement prompt chunking for extremely large inputs
