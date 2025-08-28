# MCP Gateway File Handling Implementation Plan

## Overview

This document outlines the implementation strategy for bidirectional file handling in the Solace Agent Mesh (SAM) MCP Gateway. The approach enables seamless file exchange between MCP clients (like Claude Desktop) and SAM agents while working within the constraints of both the MCP protocol and existing SAM infrastructure.

## Background Research

### MCP Protocol Analysis

**File Handling Limitations in MCP:**
- The Model Context Protocol (MCP) specification has no standardized file upload mechanism
- All data exchange occurs through JSON-RPC messages, limiting file transfers to text-based encoding
- Base64 encoding is the only viable option for binary data, but has significant limitations for large files
- Community discussion (GitHub modelcontextprotocol/modelcontextprotocol#1197) acknowledges these limitations as a known issue requiring future protocol development

**MCP Protocol Capabilities:**
- Tools can accept complex parameters including `list[dict]` structures
- Resources can provide binary data as base64-encoded blobs  
- Resource metadata and annotations can provide client hints about content
- No direct file transfer protocol exists - everything must flow through JSON-RPC

### FastMCP Framework Analysis

**Complex Parameter Support (FastMCP Documentation):**
- Confirmed support for complex tool parameters including nested objects
- `list[dict[str, str]]` parameters are fully supported and automatically serialized/deserialized
- Example from docs: `files: list[dict[str, str]]` parameter type works seamlessly
- This enables combining file data with agent messages in a single tool call

**Resource System Capabilities:**
- Dynamic resource templates with parameterized URIs (e.g., `artifact://{app}/{user}/{session}/{filename}`)
- Custom metadata via `meta` parameter for client hints
- Resource annotations for behavioral hints (`readOnlyHint`, `idempotentHint`)
- Size and content warnings can be embedded in resource descriptions and metadata

### SAM Ecosystem Analysis

**HTTP SSE Gateway File Handling Pattern:**
- Uses FastAPI's `UploadFile` for receiving multipart form data
- Integrates with SAM's artifact service via `save_artifact_with_metadata`
- Creates `artifact://` URIs that become `FilePart` objects in A2A messages
- Supports file versioning, metadata storage, and access control
- Handles both text and binary files with proper MIME type detection

**A2A Protocol Integration:**
- Agent-to-Agent messages support `FilePart` objects alongside `TextPart`
- Files are referenced by `artifact://` URIs rather than embedding content
- Existing agents already handle file references through the artifact service
- Authentication and session management are handled at the gateway level

## Strategic Approach

### Core Design Principles

1. **Protocol Compliance**: Work within MCP's JSON-RPC limitations using base64 encoding
2. **SAM Integration**: Leverage existing artifact service and A2A infrastructure  
3. **Client Intelligence**: Provide metadata hints to help clients make smart decisions about large files
4. **Atomic Operations**: Combine file upload with agent task submission in single tool calls
5. **Security**: Maintain OAuth authentication and proper access control

### File Size Management Strategy

**The Token Consumption Problem:**
Base64 encoding creates a ~33% size overhead, and large files can consume massive amounts of LLM context tokens. A 10MB file becomes ~13MB of base64, potentially consuming 50,000+ tokens.

**Solution - Smart Resource Metadata:**
- Embed file size information in resource metadata using FastMCP's `meta` parameter
- Include estimated token counts for text-based files
- Provide client warnings through resource descriptions and annotations
- Enable clients to make informed decisions about reading vs downloading files

## Implementation Architecture

### Phase 1: Client to SAM (File Upload + Agent Tasks)

**Unified Tool Pattern:**
Each agent that can process files gets a dedicated MCP tool that accepts both message and files in a single call:

```python
@mcp.tool
async def data_analyst_agent(
    message: str,
    files: list[dict[str, str]] = None,  # Supported by MCP/FastMCP
    ctx: Context
) -> str:
```

**File Processing Flow:**
1. Client encodes files as base64 and includes in tool call parameters
2. Gateway decodes files and saves to SAM's artifact service using existing `save_artifact_with_metadata` pattern
3. Artifact URIs are generated and included in A2A message as `FilePart` objects
4. Agent receives files through standard A2A infrastructure
5. Gateway returns agent response to MCP client

**Key Benefits:**
- Single atomic operation (no separate upload step)
- Leverages proven HTTP SSE gateway patterns
- Files immediately available to target agent
- Maintains session and user context automatically

### Phase 2: SAM to Client (File Download from Agents)

**Dynamic Resource Template:**
Files created by agents are exposed as MCP resources using parameterized URIs:

```python
@mcp.resource("artifact://{app_name}/{user_id}/{session_id}/{filename}")
async def get_agent_artifact(...) -> bytes:
```

**File Discovery Pattern:**
- Agents create files through existing artifact service
- Files become available as MCP resources automatically
- `list_agent_artifacts` tool provides file metadata including size warnings
- Clients can discover and selectively download files

**Smart Size Management:**
Resources include comprehensive metadata to help clients decide whether to read content:
- File size in bytes and estimated token count
- `large_file_warning` flag for files exceeding thresholds
- Recommendations in resource descriptions
- `auto_read_safe` boolean for client automation

### Phase 3: Authentication & Security Integration

**OAuth Integration:**
- Builds on existing OAuth implementation from MCP_OAUTH_INTEGRATION.md
- File access inherits user authentication and permissions
- Artifact service access control ensures users only see their own files
- Session-based file isolation maintains privacy

**Security Considerations:**
- File size limits to prevent abuse
- MIME type restrictions where appropriate
- Secure file name validation
- Integration with SAM's existing audit logging

## Technical Implementation Details

### Configuration Schema

Extend the MCP Gateway app configuration to include file handling parameters:

```yaml
app_config:
  # File handling limits
  max_file_size_mb: 100
  allowed_mime_types: ["*/*"]  # or restrict as needed
  large_file_threshold_tokens: 10000
  max_auto_read_size_bytes: 1048576  # 1MB
  
  # Integration settings
  enable_file_tools: true
  enable_artifact_resources: true
```

### Error Handling Strategy

**Upload Validation:**
- File size enforcement before processing
- MIME type validation against allowed types
- Filename sanitization and security checks
- Base64 decoding error handling

**Download Protection:**
- Authentication verification for each resource access
- Session validation and ownership checks
- Graceful handling of missing or corrupted files
- Clear error messages for client debugging

### Performance Considerations

**Memory Management:**
- Files are processed in memory during base64 decode/encode cycles
- Large files require significant temporary memory allocation
- Consider streaming implementations for future enhancements

**Token Efficiency:**
- Provide size estimates to help clients avoid context overflow
- Enable selective file processing (metadata vs full content)
- Support chunked reading for future protocol enhancements

## Integration Points

### With Existing SAM Infrastructure

**Artifact Service:**
- Reuse `save_artifact_with_metadata` and `load_artifact_content_or_metadata` helpers
- Leverage existing versioning and metadata capabilities
- Maintain compatibility with current agent file handling patterns

**A2A Protocol:**
- Files become `FilePart` objects in agent messages
- No changes required to existing agent implementations
- Gateway handles translation between MCP and A2A formats

**Authentication:**
- OAuth user context flows through to artifact service
- Session management maintains user isolation
- Permissions inherit from existing access control patterns

### With MCP Ecosystem

**Client Compatibility:**
- Standard MCP tool calls with complex parameters
- Resource discovery through standard `list_resources()` calls
- Metadata available through standard MCP resource properties
- No special client modifications required for basic functionality

**Advanced Client Features:**
- Smart clients can read `_fastmcp` metadata for size warnings
- File info tools provide enhanced discovery capabilities
- Resource annotations guide client behavior decisions

## Success Criteria

### Functional Requirements

**Phase 1 (Upload):**
- [ ] MCP clients can attach files to agent tool calls
- [ ] Files are properly stored in SAM's artifact service
- [ ] Agent receives files through standard A2A `FilePart` objects
- [ ] Authentication and session context properly maintained
- [ ] File size and type validation enforced

**Phase 2 (Download):**
- [ ] Agent-generated files automatically become MCP resources
- [ ] Clients can discover available files through resource listing
- [ ] File content accessible through standard `read_resource()` calls
- [ ] Size warnings prevent accidental context consumption
- [ ] Large file metadata enables smart client decisions

**Phase 3 (Production Ready):**
- [ ] OAuth authentication secures all file operations
- [ ] Audit logging tracks file access and transfers
- [ ] Performance acceptable for typical file sizes
- [ ] Error handling provides clear client feedback
- [ ] Documentation enables easy client integration

### Non-Functional Requirements

**Security:**
- All file access requires proper authentication
- Users can only access their own files
- File uploads respect configured size and type limits
- No sensitive information leaked through error messages

**Performance:**
- File operations complete within reasonable time bounds
- Memory usage stays within acceptable limits
- Large files don't crash or hang the gateway
- Multiple concurrent file operations handled gracefully

**Usability:**
- Clear warnings for large files that may consume excessive context
- Intuitive file discovery and access patterns
- Helpful error messages for common failure scenarios
- Minimal complexity for basic use cases

## Future Enhancements

### Protocol Evolution
- Monitor MCP specification development for native file handling
- Implement streaming file transfers when protocol supports it
- Add chunked file processing for very large files
- Support file range requests for partial content access

### Advanced Features
- File thumbnail generation for images
- Content indexing and search capabilities
- File sharing between users (with proper permissions)
- Integration with external file storage systems
- Automatic file compression for large uploads

## Conclusion

This implementation plan provides a comprehensive strategy for adding bidirectional file handling to the SAM MCP Gateway while respecting the constraints of both the MCP protocol and SAM's existing architecture. By leveraging FastMCP's complex parameter support, SAM's artifact service, and intelligent resource metadata, we can deliver a robust file handling solution that enhances the agent interaction experience without requiring protocol modifications or breaking existing functionality.

The phased approach allows for incremental implementation and testing, while the size-aware resource strategy addresses the critical challenge of token consumption in LLM contexts. This solution positions the MCP Gateway to provide file handling capabilities that match or exceed those available through other SAM interfaces while maintaining the security and scalability characteristics of the broader platform.