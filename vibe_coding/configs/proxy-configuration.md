# Proxy Configuration

Configuration for external agent proxies.

## Configuration

```yaml
app_config:
  namespace: "${NAMESPACE}"
  proxied_agents:
    - agent_name: "external-agent"
      url: "https://api.example.com/agent"
      timeout_seconds: 60
      authentication:
        type: "bearer"
        token: "${API_TOKEN}"
```

## Fields

- `agent_name`: External agent identifier
- `url`: Agent endpoint URL
- `timeout_seconds`: Request timeout
- `authentication`: Auth configuration

## Related Documentation

- [Agent Configuration](./agent-configuration.md)
- [Gateway Configuration](./gateway-configuration.md)
