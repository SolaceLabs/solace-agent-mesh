# Authorization Configuration for Development

This directory contains authorization configuration files for development and testing environments.

## ⚠️ SECURITY WARNING

**These configuration files grant FULL ACCESS to all system capabilities and should NEVER be used in production environments.**

## Files

### `dev-roles.yaml`
Defines the `developer` role with comprehensive permissions including:
- `*` - Wildcard access to all operations
- `agent:*:delegate` - Permission to delegate to any agent
- `monitor/*` - All monitoring capabilities
- `admin/*` - All administrative functions
- `artifact:*` - All artifact operations
- `session:*` - All session management
- `gateway:*` - All gateway operations
- `tool:*` - All tool access

### `dev-users.yaml`
Maps the SAM development user to the `developer` role:
- `sam_dev_user` - SAM development user with full access for testing and development

## Usage in Gateway Configurations

Add this to your gateway's `app_config` section:

```yaml
authorization_service:
  type: "default_rbac"
  role_definitions_path: "examples/auth/dev-roles.yaml"
  user_assignments_path: "examples/auth/dev-users.yaml"

# For development: explicitly set default user identity
# WARNING: Only use in trusted development environments!
default_user_identity: "sam_dev_user"
```

### Default User Identity Configuration

The `default_user_identity` setting allows you to specify which user identity to use when no authentication is provided. This is **intentionally explicit** to avoid security issues:

- ✅ **Explicit configuration** - Must be deliberately set in config
- ✅ **No automatic defaults** - Prevents accidental privilege escalation
- ✅ **Clear intent** - Makes development access obvious
- ✅ **Easy to search** - `sam_dev_user` is distinctive and searchable

**Security Note:** Without `default_user_identity` configured, requests with no authentication will be rejected. This prevents accidental access grants.

### Force User Identity (Development Override)

For development, you can completely override any user identity with the `force_user_identity` configuration:

```yaml
# For development: force all user identities to sam_dev_user
# WARNING: This overrides ALL authentication - development only!
force_user_identity: "sam_dev_user"

# Fallback for null identities (kept for completeness)
default_user_identity: "sam_dev_user"
```

**How it works:**
- `force_user_identity` overrides ANY provided user identity (including `web-client-xxxxx`)
- `default_user_identity` only applies when no user identity is provided
- Both settings are explicit and must be deliberately configured

**⚠️ CRITICAL WARNING**: `force_user_identity` completely bypasses authentication and should NEVER be used in production environments!

**Use cases:**
- ✅ Development testing with consistent user identity
- ✅ Debugging authorization issues
- ✅ Local development environments
- ❌ Production deployments
- ❌ Any environment with real user data

## Environment Variables

You can override the file paths using environment variables:

```bash
export ROLE_DEFINITIONS_PATH="path/to/your/roles.yaml"
export USER_ASSIGNMENTS_PATH="path/to/your/users.yaml"
```

## Production Configuration

For production environments:

1. **Create restrictive role definitions** with minimal required permissions
2. **Use specific user assignments** instead of wildcard patterns
3. **Implement proper user authentication** and identity management
4. **Regular security audits** of role assignments and permissions

## Migration from development_mode

This authorization-based approach replaces the previous `development_mode.grant_all_scopes` configuration, providing:

- ✅ **Explicit security model** - No hidden development flags
- ✅ **Production ready** - Easy to create restrictive configs
- ✅ **Flexible permissions** - Granular control over capabilities
- ✅ **Clear audit trail** - Visible role and user assignments