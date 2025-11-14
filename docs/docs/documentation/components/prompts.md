---
title: Prompt Library
sidebar_position: 290
---

# Prompt Library

The Prompt Library is a powerful feature that enables you to create, manage, and reuse prompt templates across your AI conversations. Instead of retyping common instructions or workflows, you can save them as reusable templates with variable placeholders, making your interactions with AI agents more efficient and consistent.

:::tip[In one sentence]
The Prompt Library lets you create reusable prompt templates with variables, accessible via quick commands in chat, enabling faster and more consistent AI interactions.
:::

## Key Features

1. **Quick Access**: Type `/` in any chat to instantly search and insert prompts using keyboard shortcuts.

2. **Variable Substitution**: Use `{{Variable Name}}` placeholders in your prompts to create flexible templates that adapt to different contexts.

3. **Version Management**: Track changes to your prompts over time with automatic versioning, and designate specific versions as "Active" for active use.

4. **Organization**: Tag prompts by topic (Development, Analysis, Documentation, etc.) and assign custom chat shortcuts for even faster access.

5. **AI-Assisted Creation**: Use the built-in prompt builder assistant to help you design effective templates through natural conversation.

## Understanding Prompts

### Prompt Groups

A prompt group is a container that holds multiple versions of a prompt template. Each group includes:

- **Name**: A descriptive title for the prompt (e.g., "Code Review Template")
- **Description**: Optional details about the prompt's purpose
- **Tag**: Organizational label (e.g., "Development", "Analysis", "Documentation")
- **Shortcut**: Optional shortcut for quick access (e.g., typing `/review` instantly finds your code review prompt)
- **Active Version**: The currently active version of the prompt that appears when you use the shortcut

### Prompt Versions

Each time you modify a prompt, a new version is created automatically. This allows you to:

- Track the evolution of your prompts over time
- Revert to previous versions if needed
- Compare different approaches
- Designate which version is "active"

### Variables

Variables are placeholders in your prompts that you fill in each time you use them. They use the format `{{Variable Name}}` with Title Case and spaces. For example:

```
Review the {{Module Name}} module located at {{File Path}}.

Focus on:
- Security vulnerabilities
- Error handling
- {{Specific Concerns}}
```

When you select this prompt, you'll be prompted to fill in the Module Name, File Path, and Specific Concerns before the prompt is inserted into your chat.

## Creating and Managing Prompts

### Creating Your First Prompt

You can create prompts in two ways: using the AI-assisted prompt builder, or manually by specifying the required parameters.

#### Using the AI Prompt Builder

The prompt builder assistant helps you create effective templates through conversation:

1. Navigate to the Prompts section in the UI
2. Click "Build with AI" 
3. Describe what you want the template to do
4. The AI will ask clarifying questions about what information changes each time
5. Review the generated template and make adjustments
6. Save when ready

The assistant understands that only data that changes (like file paths, names, dates) should be variables, while instructions and steps should remain as fixed text.

### Updating Prompts

When you update a prompt's text, a new version is automatically created. This preserves your history while allowing you to improve your templates over time.

## Using Prompts in Chat

### Quick Access with `/` Command

The fastest way to use prompts is through the `/` command in chat:

1. Type `/` in the chat input field
2. A search popover appears showing all your prompts
3. Start typing to filter by name or chat shortcut
4. Use arrow keys to navigate the list
5. Press Enter to select a prompt
6. If the prompt has variables, a dialog appears for you to fill them in
7. The completed prompt is inserted into your chat input

### Using Chat Shortcuts

If you've assigned a shortcut to a prompt (e.g., "review"), you can type it directly:

1. Type `/review` in chat
2. The prompt appears immediately
3. Fill in any variables
4. The prompt is inserted

## Configuration

### Enabling the Prompt Library

The Prompt Library requires SQL database persistence to function. Configure persistence in your `shared_config.yaml`:

```yaml
session_service:
  type: sql
  database_url: "sqlite:///./data/sessions.db"
```

The Prompt Library is enabled by default when persistence is configured. To explicitly control it:

```yaml
# Enable or disable the prompt library
prompt_library:
  enabled: true
```

### Feature Flag Control

You can also control the Prompt Library via feature flags:

```yaml
frontend_feature_enablement:
  promptLibrary: true  # Enable prompt library
  projects: true
  taskLogging: true
```

:::note[Configuration Priority]
The feature flag resolution follows this priority:
1. **Persistence Check**: If persistence is disabled, prompts are disabled (non-negotiable)
2. **Explicit Config**: `prompt_library.enabled` setting
3. **Feature Flag**: `frontend_feature_enablement.promptLibrary` setting
4. **Default**: Enabled (if persistence is enabled and no explicit disable)
:::

### Database Migration

When you first enable the Prompt Library, the database tables are created automatically through Alembic migrations. The migration creates:

- `prompt_groups` table: Stores prompt metadata and organization
- `prompts` table: Stores individual prompt versions
- `prompt_group_users` table: Manages sharing and permissions

No manual intervention is required - the tables are created when you start the application with persistence enabled.

## Best Practices

### Designing Effective Prompts

1. **Use Clear Variable Names**: Choose descriptive names like `{{File Path}}` instead of `{{x}}` or `{{input}}`

2. **Keep Instructions Fixed**: Only make data that changes into variables. Instructions, steps, and requirements should be part of the template text.

3. **Provide Context**: Include enough context in the prompt so the AI understands what you're asking for.

## Troubleshooting

### Prompts Not Visible

If prompts are not showing up in the UI:

1. **Check Persistence Configuration**:
   ```yaml
   session_service:
     type: sql  # Must be 'sql', not 'memory'
   ```

2. **Check if Prompts are Explicitly Disabled**:
   ```yaml
   prompt_library:
     enabled: false  # Remove this line or set to true
   ```

3. **Check Feature Flags**:
   ```yaml
   frontend_feature_enablement:
     promptLibrary: true  # Should be true or omitted
   ```