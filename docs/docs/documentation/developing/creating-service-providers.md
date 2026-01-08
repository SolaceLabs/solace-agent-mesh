---
title: Creating Service Providers
sidebar_position: 450
---

# Creating Service Providers

This guide details the process for developers to create service provider plugins for integrating backend systems (for example, HR platforms, CRMs) with Agent Mesh.

## Understanding Service Providers

Service Providers function as the abstraction layer between Agent Mesh and enterprise data sources. They are implemented as Python classes that adhere to a specific abstract base class, enabling standardized interaction between Agent Mesh components (Gateways and Agents) and the underlying data.

There are two primary service provider interfaces:

- **`BaseIdentityService`**: Responsible for **identity enrichment**. This service is utilized by Gateways to augment the profile of an authenticated user with additional details (for example, full name, job title) based on their initial authentication claims.
- **`BaseEmployeeService`**: Responsible for **general directory querying**. This service is utilized by agents (for example, the `EmployeeAgent`) to execute lookups across the entire employee directory.

## The "Dual-Role Provider" Pattern

In many enterprise systems, particularly HR platforms, the data source for identity enrichment and general employee queries is identical. To optimize development, Agent Mesh promotes a "Dual-Role Provider" pattern.

This pattern involves creating a single class that inherits from both `BaseIdentityService` and `BaseEmployeeService`. This consolidated class can then be configured to fulfill either or both roles, thereby reducing code duplication.

## Step-by-Step Implementation Guide

This section provides a walkthrough for creating a new provider for a fictional "CorpHR" system.

### Step 1: Establish the Plugin Structure

The recommended structure for a custom service provider plugin should include a `pyproject.toml` for packaging and a `src` directory for the source code.

```bash
sam plugin create my_corp_hr_provider --type custom
```

### Step 2: Define the Provider Class

Create a `provider.py` module and define the provider class, ensuring it inherits from both base service classes.

```python
# my_corp_hr_provider/provider.py

# Import base classes from the Agent Mesh framework
try:
    from solace_agent_mesh.common.services.identity_service import BaseIdentityService
    from solace_agent_mesh.common.services.employee_service import BaseEmployeeService
except ImportError:
    # Fallback for local development environments
    from src.solace_agent_mesh.common.services.identity_service import BaseIdentityService
    from src.solace_agent_mesh.common.services.employee_service import BaseEmployeeService

# Import any other necessary libraries, such as 'requests' or a proprietary SDK
# from .corp_hr_sdk import CorpHR_SDK

class CorpHRProvider(BaseIdentityService, BaseEmployeeService):
    """
    A dual-role provider for the CorpHR system, implementing methods
    for both identity enrichment and employee directory services.
    """
    def __init__(self, config):
        super().__init__(config)
        # Initialize the backend service/SDK client here.
        # It is best practice to implement this as a singleton to share
        # connection pools and cache.
        # self.corp_hr_sdk = CorpHR_SDK(api_key=config.get("api_key"))

    # --- BaseIdentityService Method Implementations ---

    async def get_user_profile(self, auth_claims):
        """Enrich the current user's profile based on their auth claims."""
        # TODO: Implement logic to fetch user data from CorpHR
        pass

    async def search_users(self, query, limit=10):
        """Search for users, for features like @-mentions."""
        # TODO: Implement user search logic against CorpHR
        pass

    # --- BaseEmployeeService Method Implementations ---

    async def get_employee_dataframe(self):
        """Return all employees as a pandas DataFrame for directory-wide queries."""
        # TODO: Fetch all employee data and return as a DataFrame
        pass

    async def get_employee_profile(self, employee_id):
        """Get a single employee's full profile by their ID."""
        # Note: This is a general directory lookup, distinct from get_user_profile.
        # TODO: Implement single employee lookup
        pass

    async def get_time_off_data(self, employee_id):
        """Get an employee's raw time off data."""
        # Example return format:
        # return [{'start': '2025-07-04', 'end': '2025-07-04', 'type': 'Holiday'}]
        # TODO: Implement time off data retrieval
        pass

    async def get_employee_profile_picture(self, employee_id):
        """Fetch a profile picture as a data URI string."""
        # Example return format: "data:image/jpeg;base64,..."
        # TODO: Implement profile picture fetching
        pass
```

### Step 3: Map to the Canonical Employee Schema

When implementing the service methods, it is **mandatory** to map the data from the source system to the **canonical employee schema** of Agent Mesh. This ensures data consistency and interoperability with all tools and components across the mesh.

| Field Name     | Data Type | Description                                                         |
| -------------- | --------- | ------------------------------------------------------------------- |
| `id`           | `string`  | A unique, stable, and **lowercase** identifier (e.g., email, GUID). |
| `displayName`  | `string`  | The employee's full name for display purposes.                      |
| `workEmail`    | `string`  | The employee's primary work email address.                          |
| `jobTitle`     | `string`  | The employee's official job title.                                  |
| `department`   | `string`  | The department to which the employee belongs.                       |
| `location`     | `string`  | The physical or regional location of the employee.                  |
| `supervisorId` | `string`  | The unique `id` of the employee's direct manager.                   |
| `hireDate`     | `string`  | The date the employee was hired (ISO 8601: `YYYY-MM-DD`).           |
| `mobilePhone`  | `string`  | The employee's mobile phone number (optional).                      |

:::info
If a field is not available in the source system, return `None` or omit the key from the returned dictionary.
:::

### Step 4: Register the Plugin

To make the provider discoverable by Agent Mesh, it must be registered as a plugin via entry points.

**1. Add an entry point in `pyproject.toml`:**
The key assigned here (`corphr`) is used as the `type` identifier in YAML configurations.
```toml
[project.entry-points."solace_agent_mesh.plugins"]
corphr = "my_corp_hr_provider:info"
```

**2. Define the `info` object in the plugin's `__init__.py`:**
This object points to the provider's class path and provides a brief description.
```python
# my_corp_hr_provider/__init__.py
info = {
    "class_path": "my_corp_hr_provider.provider.CorpHRProvider",
    "description": "Identity and People Service provider for CorpHR.",
}
```

## Configuring the Provider

Once the plugin is created and installed (for example, via `pip install .`), it can be configured in any Gateway or Agent `app_config.yml`.

**For a Gateway (Identity Service Role):**

```yaml
app_config:
  identity_service:
    type: "corphr" # Matches the key in pyproject.toml
    api_key: "${CORPHR_API_KEY}"
    lookup_key: "email" # The field from auth_claims to use for lookup
```

**For an Agent (Employee Service Role):**
This example demonstrates configuring the provider for the `employee_tools` group.
```yaml
app_config:
  tools:
    - tool_type: builtin-group
      group_name: "employee_tools"
      config:
        type: "corphr" # Same provider, different role
        api_key: "${CORPHR_API_KEY}"
```
