# Identity Service Configuration

The Identity Service provides user lookup functionality for features like @mentions in the chat UI. It supports pluggable providers for different identity sources.

## Local File Identity Service (for Development/Testing)

The `LocalFileIdentityService` loads user data from a JSON file. This is useful for development and testing without requiring external identity providers.

### Configuration

Add this to your gateway configuration YAML:

```yaml
identity_service:
  type: local_file
  file_path: /absolute/path/to/your/employees.json
  lookup_key: id  # Optional, defaults to "id"
  cache_ttl_seconds: 3600  # Optional, defaults to 3600 (1 hour)
```

### Example Configuration for Development

```yaml
identity_service:
  type: local_file
  file_path: ./tests/integration/test_data/people/dummy_employees.json
  cache_ttl_seconds: 300  # 5 minutes for faster testing
```

### JSON File Format

The JSON file should contain an array of user objects with the following fields:

```json
[
  {
    "id": "user.email@example.com",
    "email": "user.email@example.com",
    "name": "Full Name",
    "title": "Job Title"
  }
]
```

**Required fields:**
- `id`: Unique identifier for the user (typically email address)
- `email`: User's email address
- `name`: Full display name

**Optional fields:**
- `title`: Job title or role
- Any other custom fields your application needs

### Example JSON File

See `tests/integration/test_data/people/dummy_employees.json` for a complete example with sample employee data.

## Enterprise Identity Providers

For production use, you can integrate with enterprise identity providers like Azure AD, Okta, or custom LDAP systems through the plugin system.

### Plugin Configuration

```yaml
identity_service:
  type: azure_ad  # or your custom plugin type
  tenant_id: your-tenant-id
  client_id: your-client-id
  client_secret: your-client-secret
  cache_ttl_seconds: 3600
```

Consult your specific identity provider plugin documentation for configuration details.

## API Endpoints

The Identity Service powers the following API endpoints:

### People Search

**Endpoint:** `GET /api/v1/people/search`

**Query Parameters:**
- `q` (required): Search query string (minimum 2 characters)
- `limit` (optional): Maximum number of results to return (default: 10, max: 25)

**Example:**
```bash
curl "http://localhost:8000/api/v1/people/search?q=john&limit=5"
```

**Response:**
```json
{
  "data": [
    {
      "id": "john.doe@example.com",
      "name": "John Doe",
      "email": "john.doe@example.com",
      "title": "Product Manager"
    }
  ]
}
```

## Features Using Identity Service

### @Mentions in Chat

The @mention feature in the chat UI uses the Identity Service to search for users:

1. Type `@` followed by at least 2 characters
2. A popup appears with matching people from the identity service
3. Select a person to insert their mention
4. The mention is formatted as `Name <id:email>` when sent to the backend

### Future Features

The Identity Service can be extended to support:
- User profile lookups
- Organizational chart queries
- Team membership information
- Availability status

## Troubleshooting

### No search results appearing

1. **Check file path**: Ensure the `file_path` in your configuration points to a valid JSON file
2. **Verify JSON format**: Make sure the JSON file follows the correct structure
3. **Check minimum query length**: Search requires at least 2 characters
4. **Review logs**: Look for error messages in the gateway logs

### Cache issues

If you're not seeing updated user data:

1. **Restart the gateway**: Changes to the JSON file require a gateway restart
2. **Reduce cache TTL**: Set `cache_ttl_seconds` to a lower value during development
3. **Clear cache**: Restart the gateway to clear the in-memory cache

### Permission errors

Ensure the gateway process has read permissions for the identity JSON file:

```bash
chmod 644 /path/to/employees.json
```

## Security Considerations

### Local File Provider

- **File permissions**: Restrict read access to the identity JSON file
- **Sensitive data**: Avoid storing sensitive information in the local file
- **Development only**: This provider is intended for development and testing

### Enterprise Providers

- **Credentials**: Store provider credentials securely (use environment variables or secrets management)
- **Access control**: Configure appropriate scopes and permissions
- **Data retention**: Follow your organization's data retention policies
- **Audit logging**: Enable logging for identity service access

## See Also

- [Employee Service Documentation](./employee_service.md) - For HR-specific data like time off and org charts
- [Authentication Configuration](./authentication.md) - For user authentication setup
- [@Mentions Feature Guide](../features/mentions.md) - User guide for the mention feature
