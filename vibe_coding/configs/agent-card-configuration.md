# Agent Card Configuration

Agent metadata for discovery and capability description.

## Configuration

```yaml
agent_card:
  description: "Agent description"
  defaultInputModes: ["text", "file"]
  defaultOutputModes: ["text", "file"]
  skills:
    - id: "skill_id"
      name: "Skill Name"
      description: "What this skill does"
```

## Fields

- `description`: Agent purpose
- `defaultInputModes`: Supported input types
- `defaultOutputModes`: Supported output types
- `skills`: List of agent capabilities

## Related Documentation

- [Agent Configuration](./agent-configuration.md)
