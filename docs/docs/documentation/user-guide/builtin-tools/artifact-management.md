---
title: Artifact Management Tools
sidebar_position: 10
---

# Artifact Management Tools

This guide details how agents utilize built-in tools to manage file artifacts and their associated metadata. The system employs an explicit, metadata-aware methodology wherein the agent maintains full control over the lifecycle of artifacts, including their creation, listing, loading, and return.

## The Metadata-Aware Workflow

Rather than automatically bundling all created artifacts in the final response, the agent follows a structured workflow:

1.  **Create & Describe**: The agent invokes the `create_artifact` tool to persist a file. Rich metadata, such as descriptions, sources, and inferred schemas, is stored alongside the artifact.
2.  **Inject & Inform**: This metadata is automatically injected into the conversation history, providing the agent with immediate context regarding the new file.
3.  **List & Discover**: The agent can call `list_artifacts` at any point to retrieve a summary of all available artifacts and their associated metadata.
4.  **Load & Analyze**: The agent can use `load_artifact` to read the content of a text-based artifact or inspect the detailed metadata of any artifact (for example, to ascertain the schema of a CSV file).
5.  **Return on Request**: To transmit an artifact to the user or a calling application, the agent must explicitly invoke `signal_artifact_for_return`. Artifacts are not returned automatically.

## Configuration

The file management tools are encapsulated within the `artifact_management` tool group.

### Enabling the Tools
Enable the tool group within the agent's `app_config.yml`:
```yaml
# In your agent's app_config:
tools:
  - tool_type: builtin-group
    group_name: "artifact_management"
```

### Configuring Artifact Return Behavior
The `artifact_handling_mode` setting in your `app_config` dictates the behavior when `signal_artifact_for_return` is called:

- `ignore` (Default): The request is logged, but no artifact is transmitted.
- `embed`: The artifact content is base64-encoded and embedded within the `TaskArtifactUpdateEvent` payload. This is suitable for smaller files.
- `reference`: A URI pointing to the artifact is sent in the event payload. This approach requires a separate service to host the file at the specified URI.

```yaml
# In your agent's app_config:
artifact_handling_mode: "reference"
```

## Tool Reference

### `create_artifact`
Creates a new file artifact and its corresponding metadata.

- **Parameters**:
    - `filename` (str): The designated name for the artifact (for example, "report.pdf").
    - `content` (str): The file content. For binary file types (for example, images, PDFs), this content **must be base64-encoded**.
    - `mime_type` (str): The standard MIME type of the content (for example, "text/plain", "image/png").
    - `metadata` (dict, optional): A dictionary containing custom metadata (for example, `{"description": "Monthly sales data"}`).
- **Returns**: A dictionary confirming the successful persistence of the artifact.
- **Key Feature**: Upon successful execution of this tool, a summary of the artifact's metadata is **automatically injected into the conversation history**, informing the agent of the new file's context.

---

### `list_artifacts`
Lists all available artifacts within the current session.

- **Parameters**: None.
- **Returns**: A list of file objects, each containing the `filename`, available `versions`, and a `metadata_summary` for the latest version.

---

### `load_artifact`
Loads the content or detailed metadata of a specific version of an artifact.

- **Parameters**:
    - `filename` (str): The name of the artifact to be loaded.
    - `version` (int): The specific version number of the artifact to load.
    - `load_metadata_only` (bool, optional): If `True`, the tool returns the complete, detailed metadata dictionary instead of the artifact's content. This is useful for inspecting schemas or other metadata fields.
- **Returns**:
    - If `load_metadata_only=False`: The artifact's content (for text-based files) or a basic information dictionary (for binary files).
    - If `load_metadata_only=True`: The complete metadata dictionary for the specified artifact version.

---

### `signal_artifact_for_return`
Instructs the system to transmit a specific artifact version to the caller.

- **Parameters**:
    - `filename` (str): The name of the artifact to be returned.
    - `version` (int): The specific version number of the artifact to return.
- **Returns**: A dictionary confirming that the request has been received.
- **Note**: This tool functions as a signal. The actual transmission of the artifact is handled by the system in accordance with the configured `artifact_handling_mode`.

## Key Concepts
- **Explicit Control**: Agents possess full, explicit control over the entire artifact lifecycle.
- **Metadata-Driven Context**: The automatic injection and summarization of metadata are fundamental to providing agents with situational awareness.
- **Signaled Return**: Artifacts are transmitted to the user only upon an explicit request from the agent via the `signal_artifact_for_return` tool.
- **Synergy with Embeds**: These tools can be used in conjunction with [Dynamic Embeds](embeds.md), such as `«artifact_meta:report.csv»`, for more efficient file handling.
