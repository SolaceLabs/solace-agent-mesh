---
title: Projects
sidebar_position: 270
---

# Projects

Projects are a powerful organizational feature in Agent Mesh that enable users to group related chat sessions, manage artifacts and maintain context across multiple conversations. They provide a workspace-like environment for managing AI interactions around specific topics, tasks, or domains.

:::tip[In one sentence]
Projects are organizational containers that group related chat sessions and knowledge artifacts together, enabling better context management and collaboration across multiple AI conversations.
:::

## Key Features

1. **Session Organization**: Group related chat sessions under a single project for better organization and context management.

2. **Knowledge Management**: Store and manage files, documents, and other artifacts that can be referenced across all sessions within a project.

3. **Custom Instructions**: Define project-specific instructions (system prompt) that apply to all chat sessions within the project, ensuring consistent AI behavior.

4. **Default Agent Configuration**: Set a default agent for the project, streamlining the chat creation process.

5. **Soft Delete**: Projects and sessions can be safely deleted with the ability to recover them if needed (logical delete).

6. **Search Capabilities**: Search chat titles within a project or across all projects to quickly find relevant conversations.

7. **Session Mobility**: Move chat sessions between projects to reorganize your work as needs evolve.

## How Projects Work

Projects provide a hierarchical structure for organizing your AI interactions. Each project contains:

- **Project Metadata**: Name, description, system prompt, and default agent configuration
- **Chat Sessions**: Multiple conversation threads that inherit project settings
- **Project Knowledge**: Files and documents accessible across all sessions

## Project Components

### Project Metadata

Each project contains the following metadata:

- **Name**: A descriptive name for the project (required)
- **Description**: Optional detailed description of the project's purpose
- **System Prompt**: Custom instructions that apply to all chat sessions in the project
- **Default Agent**: The agent that will be used by default for new sessions in this project
- **Created/Updated Timestamps**: Automatic tracking of project creation and modification times

### Chat Sessions

Projects can contain multiple chat sessions, each representing a separate conversation thread. Sessions within a project:

- Inherit the project's instructions (if defined)
- Use the project's default agent (if specified)
- Can access project-level artifacts
- Can be moved between projects
- Can be searched and filtered

### Knowledge (Artifacts)

Projects support two types of knowledge artifacts:

1. **Project-Level Knowledge**: Files attached to the project itself (shown in the "Knowledge" section), accessible by all sessions
2. **Session-Level Artifacts**: Files attached to specific chat sessions within the project

Knowledge artifacts can include:
- Documents (PDF, DOCX, TXT, MD)
- Images (PNG, JPG, GIF)
- Code files
- Data files (JSON, CSV, YAML)
- Any other file type supported by the system

## Configuration

### Disabling Projects

Projects require SQL database persistence to function. Configure persistence in your `shared_config.yaml`:

```yaml
session_service:
  type: sql
  database_url: "sqlite:///./data/sessions.db"
```

Projects are enabled by default when persistence is configured. To disable the feature:

```yaml
# Disable projects explicitly
projects:
  enabled: false
```

### Feature Flag Control

You can also control projects via feature flags:

```yaml
frontend_feature_enablement:
  projects: false  # Disable projects
  taskLogging: true
```

:::note[Configuration Priority]
The feature flag resolution follows this priority:
1. **Persistence Check**: If persistence is disabled, projects are disabled (non-negotiable)
2. **Explicit Config**: `projects.enabled` setting
3. **Feature Flag**: `frontend_feature_enablement.projects` setting
4. **Default**: Enabled (if persistence is enabled and no explicit disable)
:::

### Soft Delete Pattern

Projects and sessions use a soft delete pattern for data preservation:

- Deleted items are marked with `deleted_at` timestamp
- Deleted items are automatically filtered from queries
- Data remains in database for audit trails
- Can be recovered if needed

## Best Practices

### Project Organization

1. **Use Descriptive Names**: Give projects clear, descriptive names that reflect their purpose
2. **Define Instructions**: Set project-specific instructions (system prompts) to ensure consistent AI behavior
3. **Organize by Topic**: Group related conversations under the same project
4. **Regular Cleanup**: Periodically review and delete unused projects

### Knowledge Management

1. **Upload Relevant Files**: Only upload files that are relevant to the project in the Knowledge section
2. **Use Metadata**: Add descriptions to knowledge artifacts for better organization
3. **File Naming**: Use clear, descriptive filenames
4. **Size Considerations**: Be mindful of file sizes for performance

### Session Management

1. **Move Sessions**: Reorganize sessions between projects as needs evolve
2. **Use Search**: Leverage search to find relevant conversations quickly
3. **Delete Unused Sessions**: Clean up old or irrelevant sessions
4. **Consistent Naming**: Use clear session names for easier searching

## Troubleshooting

### Projects Not Visible

If projects are not showing up in the UI:

1. **Check Persistence Configuration**:
   ```yaml
   session_service:
     type: sql  # Must be 'sql', not 'memory'
   ```

2. **Check if Projects are Explicitly Disabled**:
   ```yaml
   projects:
     enabled: false  # Remove this line or set to true
   ```

3. **Check Feature Flags**:
   ```yaml
   frontend_feature_enablement:
     projects: true  # Should be true or omitted
   ```

4. **Verify Config Endpoint**:
   ```bash
   curl http://localhost:8000/api/v1/config | jq '.frontend_feature_enablement.projects'
   ```

### API Returns 501 Error

When project endpoints return 501 Not Implemented:

- **Persistence disabled**: Configure `session_service.type: sql`
- **Explicitly disabled**: Remove `projects.enabled: false` or set to `true`
- **Feature flag disabled**: Set `frontend_feature_enablement.projects: true`


## Performance Considerations

### Database Optimization

- **Indexes**: Projects use indexes on `user_id`, `deleted_at`, and search columns
- **Eager Loading**: Related data is loaded efficiently to prevent N+1 queries
- **Pagination**: Search results are paginated to handle large datasets

### Artifact Storage

Project artifacts use the configured artifact store. See [Configurations - Artifact Service](../installing-and-configuring/configurations.md#artifact-service) for more details.

## Security

### Authorization

- All project operations validate user ownership
- Sessions can only be moved to projects owned by the user
- Knowledge artifacts are scoped to user and project/session context

### Data Privacy

- Soft-deleted data remains in database (consider retention policies)
- User ID tracked for all operations
- Consider implementing hard delete for GDPR compliance

## Related Documentation

- [Gateways](./gateways.md) - Learn about gateway configuration
- [Agents](./agents.md) - Configure agents for your projects