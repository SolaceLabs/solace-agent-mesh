# Artifact Return Embed Resolution - Implementation Checklist

## 1. Type Definitions & Constants

### 1.1 ResolutionMode Enum
- [ ] `src/solace_agent_mesh/common/utils/embeds/types.py`
  - [ ] `ResolutionMode` enum exists with three values
  - [ ] `A2A_MESSAGE_TO_USER = auto()`
  - [ ] `TOOL_PARAMETER = auto()`
  - [ ] `RECURSIVE_ARTIFACT_CONTENT = auto()`

### 1.2 Embed Type Registration
- [ ] `src/solace_agent_mesh/common/utils/embeds/constants.py`
  - [ ] `"artifact_return"` added to `LATE_EMBED_TYPES` set

## 2. Core Embed Resolution Logic

### 2.1 Main evaluate_embed Function
- [ ] `src/solace_agent_mesh/common/utils/embeds/resolver.py` - `evaluate_embed()`
  - [ ] Added `resolution_mode: "ResolutionMode"` parameter
  - [ ] `artifact_return` handler checks `resolution_mode == ResolutionMode.A2A_MESSAGE_TO_USER`
  - [ ] Returns signal tuple: `(None, "SIGNAL_ARTIFACT_RETURN", {"filename": filename, "version": version})`
  - [ ] In non-A2A_MESSAGE_TO_USER modes, returns original embed text unchanged
  - [ ] Parses expression as `filename:version` format

### 2.2 resolve_embeds_in_string Function
- [ ] `src/solace_agent_mesh/common/utils/embeds/resolver.py` - `resolve_embeds_in_string()`
  - [ ] Added `resolution_mode: "ResolutionMode"` parameter to signature
  - [ ] Return type includes placeholder: `List[Tuple[int, Any, str]]`
  - [ ] Creates unique placeholder: `f"__EMBED_SIGNAL_{uuid.uuid4().hex}__"`
  - [ ] Appends placeholder to `resolved_parts`
  - [ ] Stores `(start, resolved_value, placeholder)` in `signals_found`

### 2.3 resolve_embeds_recursively_in_string Function
- [ ] `src/solace_agent_mesh/common/utils/embeds/resolver.py` - `resolve_embeds_recursively_in_string()`
  - [ ] Added `resolution_mode: "ResolutionMode"` parameter
  - [ ] Passes `resolution_mode` to recursive `resolver_func` calls

### 2.4 Artifact Content Chain Handler
- [ ] `src/solace_agent_mesh/common/utils/embeds/resolver.py` - `_evaluate_artifact_content_embed_with_chain()`
  - [ ] Added `resolution_mode: "ResolutionMode"` parameter
  - [ ] Binary content signal handling when `current_format == DataFormat.BYTES` and `resolution_mode == ResolutionMode.A2A_MESSAGE_TO_USER`
  - [ ] Returns `(None, "SIGNAL_INLINE_BINARY_CONTENT", {bytes, mime_type, name})`
  - [ ] Passes `resolution_mode=ResolutionMode.RECURSIVE_ARTIFACT_CONTENT` to recursive calls

## 3. Gateway-Side Resolution

### 3.1 Main Signal Processing
- [ ] `src/solace_agent_mesh/gateway/base/component.py` - `_resolve_embeds_and_handle_signals()`
  - [ ] Calls `resolve_embeds_in_string()` with `resolution_mode=ResolutionMode.A2A_MESSAGE_TO_USER`
  - [ ] Extracts `signals_with_placeholders` from resolution result
  - [ ] Creates `placeholder_map` from signals
  - [ ] Uses regex to split text by placeholders: `re.split(split_pattern, resolved_text)`

### 3.2 SIGNAL_ARTIFACT_RETURN Handler
- [ ] `src/solace_agent_mesh/gateway/base/component.py` - `_resolve_embeds_and_handle_signals()`
  - [ ] Detects `signal_type == "SIGNAL_ARTIFACT_RETURN"`
  - [ ] Extracts `filename` and `version` from `signal_data`
  - [ ] Calls `load_artifact_content_or_metadata()` with `load_metadata_only=True`
  - [ ] On success: creates `FilePart` using `a2a.create_file_part_from_uri()`
  - [ ] On error: creates error `TextPart`
  - [ ] Appends result to `new_parts`

### 3.3 SIGNAL_INLINE_BINARY_CONTENT Handler
- [ ] `src/solace_agent_mesh/gateway/base/component.py` - `_resolve_embeds_and_handle_signals()`
  - [ ] Detects `signal_type == "SIGNAL_INLINE_BINARY_CONTENT"`
  - [ ] Renames `signal_data["bytes"]` to `signal_data["content_bytes"]`
  - [ ] Creates `FilePart` using `a2a.create_file_part_from_bytes()`
  - [ ] Appends to `new_parts`

### 3.4 Whitespace Cleanup
- [ ] `src/solace_agent_mesh/gateway/base/component.py` - `_resolve_embeds_and_handle_signals()`
  - [ ] Checks if fragment is whitespace-only
  - [ ] Checks if previous fragment was placeholder
  - [ ] Checks if next fragment is placeholder
  - [ ] Drops fragment if all three conditions true

### 3.5 Other Signals Handler
- [ ] `src/solace_agent_mesh/gateway/base/component.py` - `_resolve_embeds_and_handle_signals()`
  - [ ] Non-file signals added to `other_signals` list
  - [ ] Calls `_handle_resolved_signals()` for `other_signals`

### 3.6 Content Modification Detection
- [ ] `src/solace_agent_mesh/gateway/base/component.py` - `_resolve_embeds_and_handle_signals()`
  - [ ] Compares `new_parts != original_parts`
  - [ ] Updates message/artifact parts if changed
  - [ ] Returns `content_modified or bool(other_signals)`

### 3.7 Event Processing Integration
- [ ] `src/solace_agent_mesh/gateway/base/component.py` - `_process_parsed_a2a_event()`
  - [ ] Passes `resolution_mode=ResolutionMode.A2A_MESSAGE_TO_USER` to embed resolution

## 4. Tool Parameter Resolution

### 4.1 ADK Tool Wrapper
- [ ] `src/solace_agent_mesh/agent/adk/tool_wrapper.py` - `ADKToolWrapper.__call__()`
  - [ ] Passes `resolution_mode=ResolutionMode.TOOL_PARAMETER` to `resolve_embeds_in_string()`
  - [ ] Applied to both positional args and kwargs resolution

### 4.2 MCP Tool Wrapper
- [ ] `src/solace_agent_mesh/agent/adk/embed_resolving_mcp_toolset.py` - `EmbedResolvingMCPTool._resolve_embeds_recursively()`
  - [ ] Passes `resolution_mode=ResolutionMode.TOOL_PARAMETER` to `resolve_embeds_in_string()`

## 5. Agent-Side Early Resolution

### 5.1 Agent Component
- [ ] `src/solace_agent_mesh/agent/sac/component.py` - `_resolve_early_embeds_and_handle_signals()`
  - [ ] Passes `resolution_mode=ResolutionMode.TOOL_PARAMETER` to `resolve_embeds_in_string()`
  - [ ] Removes placeholder from resolved text: `resolved_text.replace(placeholder, "")`

## 6. Recursive Artifact Content Resolution

### 6.1 Template Modifier
- [ ] `src/solace_agent_mesh/common/utils/embeds/modifiers.py` - `_apply_template()`
  - [ ] Passes `resolution_mode=ResolutionMode.RECURSIVE_ARTIFACT_CONTENT` to `resolve_embeds_recursively_in_string()`

### 6.2 Artifact Router
- [ ] `src/solace_agent_mesh/gateway/http_sse/routers/artifacts.py` - `get_latest_artifact()`
  - [ ] Passes `resolution_mode=ResolutionMode.RECURSIVE_ARTIFACT_CONTENT` to `resolve_embeds_recursively_in_string()`
- [ ] `src/solace_agent_mesh/gateway/http_sse/routers/artifacts.py` - `get_specific_artifact_version()`
  - [ ] Passes `resolution_mode=ResolutionMode.RECURSIVE_ARTIFACT_CONTENT` to `resolve_embeds_recursively_in_string()`

### 6.3 WebUI Component
- [ ] `src/solace_agent_mesh/gateway/http_sse/component.py` - early embed resolution
  - [ ] Passes `resolution_mode=ResolutionMode.TOOL_PARAMETER` to `resolve_embeds_in_string()`

## 7. Signal Tuple Structure

### 7.1 Consistent Signal Format
- [ ] All signal returns use format: `(None, "SIGNAL_TYPE", data_dict)`
- [ ] `SIGNAL_ARTIFACT_RETURN` data: `{"filename": str, "version": str}`
- [ ] `SIGNAL_INLINE_BINARY_CONTENT` data: `{"bytes": bytes, "mime_type": str, "name": str}`
- [ ] `SIGNAL_STATUS_UPDATE` data: `str` (status text)

## 8. Edge Cases & Error Handling

### 8.1 artifact_return in Wrong Mode
- [ ] Returns original embed text unchanged when not in `A2A_MESSAGE_TO_USER` mode
- [ ] Logs warning about unsupported context

### 8.2 Artifact Not Found
- [ ] Creates error `TextPart` with descriptive message
- [ ] Logs exception details

### 8.3 Placeholder Preservation
- [ ] Placeholders remain in text until final processing
- [ ] Unique UUIDs prevent collisions
- [ ] Placeholders removed/replaced in final step

## 9. Integration Points

### 9.1 All resolve_embeds_in_string Calls
- [ ] Every call includes `resolution_mode` parameter
- [ ] Mode matches the calling context (gateway/tool/recursive)

### 9.2 All evaluate_embed Calls
- [ ] Every call includes `resolution_mode` parameter
- [ ] Parameter passed through from parent resolver

### 9.3 Signal Handling Chain
- [ ] Signals captured at resolution point
- [ ] Placeholders preserve position in text
- [ ] Final processing converts to appropriate parts
- [ ] Non-file signals delegated to `_handle_resolved_signals()`

---

## Verification Notes

- Check that `resolution_mode` is passed consistently through all call chains
- Verify placeholder regex pattern handles special characters correctly
- Confirm whitespace cleanup doesn't remove intentional spacing
- Test with multiple consecutive `artifact_return` embeds
- Test with mixed text and `artifact_return` embeds
- Verify error handling doesn't break message flow
