# Enterprise Configuration

Enterprise features including RBAC, SSO, and trust manager.

## RBAC Configuration

```yaml
authorization_service:
  type: "default_rbac"
  role_to_scope_definitions_path: "config/auth/roles.yaml"
  user_to_role_assignments_path: "config/auth/users.yaml"
```

## SSO Configuration

```yaml
authentication_service:
  type: "oauth2"
  provider: "azure"
  client_id: "${OAUTH_CLIENT_ID}"
  client_secret: "${OAUTH_CLIENT_SECRET}"
```

## Trust Manager

```yaml
trust_manager:
  enabled: true
  credential_service:
    type: "sql"
    database_url: "${DATABASE_URL}"
```

## Related Documentation

- [Agent Configuration](./agent-configuration.md)
- [Environment Variables](./environment-variables.md)
