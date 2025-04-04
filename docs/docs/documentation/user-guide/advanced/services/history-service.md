---
title: History Service
sidebar_position: 20
---

# History Service

The History service is a global service that provides flexible memory storage capabilities for Solace Agent Mesh. This service enables components to store and retrieve session histories and system internal states.

Key features of the History service include:

1. **Flexible Longevity**: The service offers storage with configurable durations.
2. **Efficient File Management**: The service can store references to [file metadata](./file-service.md#file-metadata) and automatically remove entries when they expire.

Here are some example use cases for the History service:

- Storing temporary calculation results during a multi-step process.
- Maintaining conversation context in a chatbot application.
- Saving user preferences across multiple sessions.
- Storing system-wide configurations accessible to all components.

The History service provides a flexible and efficient way to manage state and share data within the framework of Solace Agent Mesh, enabling more complex workflows and improving system performance by reducing redundant computations or API calls.

## Usage

The History service is a global service that creates singleton instances per identifier. Instances with the same identifier share the same memory.

To get started, you first import the History service:

```python
from solace_agent_mesh.services.history_service import HistoryService
```

Then, create a new instance of the History service:

```python
history_service = HistoryService(config, identifier="my_identifier")
```

### Configuration

The History service requires a configuration object when creating a new instance. The configuration object must have the following structure:

```json
{
   "type": "memory",
   "time_to_live": 3600,
   "expiration_check_interval": 60,
   "history_policy": {
      "max_characters": 30000,
      "max_turns": 10,
      "enforce_alternate_message_roles": true
   }
}
```

- `type`: The history provider name. For more information, see [History Providers](#history-providers).
- `time_to_live`: The duration (in seconds) that history will be stored.
- `expiration_check_interval`: The interval (in seconds) at which expired history is checked and removed.
- `history_policy`: The configurations passed to the history provider.
  - `max_characters`: The maximum number of characters the history can store.
  - `max_turns`: The maximum number of message turns the history can store.
  - `enforce_alternate_message_roles`: A boolean that indicates whether the history should enforce alternate message roles (`user`/`system`).
  - The `history_policy` object can include additional properties for [custom history providers](#custom-history-provider).

### Storing Data

There are two methods to store data in the History service:

- `store_history(session_id: str, role: str, content: Union[str, dict])`
- `store_file(session_id: str, file: dict)`

To store a message in the History service, use the `store_history` method:

```python
role = "user"
content = "Hello, World!"

history_service.store_history(session_id, role, content)
```

To store a file in the History service, use the `store_file` method:

```python
file_meta = get_file_metadata()

history_service.store_file(session_id, file_meta)
```

:::note  
The `file_meta` object is the returned output of the [`File Service`](./file-service.md#file-metadata) when uploading a file.  
:::

### Retrieving Data

There are two methods to retrieve data from the History service:

- `get_history(session_id: str) -> list`
- `get_files(session_id: str) -> dict`

To retrieve messages from the History service, use the `get_history` method:

```python
history = history_service.get_history(session_id)
```

To retrieve files from the History service, use the `get_files` method:

```python
files = history_service.get_files(session_id)
```

### Clearing Data

To clear data from the History service, use the `clear` method:

```python
history_service.clear(session_id)
```

:::note  
You can optionally pass a second parameter, `keep_levels`, to specify the number of most recent history entries to retain. By default, all history entries are cleared.  
:::

## History Providers

The `HistoryServer` class uses a history provider to store and manage history data. The provider is defined in the configuration object passed to the service.

Solace Agent Mesh provides the following built-in history providers:

- **Memory History Provider** (`memory`): Stores history in memory.  
- **Redis History Provider** (`redis`): Stores history in a Redis database.  
- **File History Provider** (`file`): Stores history in files on the local filesystem.  
- **MongoDB History Provider** (`mongodb`): Stores history in a MongoDB database.
- **SQL History Provider** (`sql`): Stores history in a SQL database. (MySQL, PostgreSQL)
- **Custom History Provider**: Allows for the implementation of user-defined history storage solutions.

### Built-in History Providers

#### **Provider: `memory`**  

The memory history provider stores history in memory. This provider is useful for storing temporary data that does not need to be persisted across restarts.  

Memory provider does not require any additional packages or configurations.

#### **Provider: `file`**
The file history provider stores history in files on the local filesystem. This provider is useful for easy access to history data and for storing large amounts of data. If using a container, the management of the volume is the responsibility of the user.

The file provider requires the following configuration:  

- `path` (*required* - *string*): The directory path where history files will be stored.

File provider does not require any additional packages.

#### **Provider: `redis`**
The Redis history provider stores history in a Redis database. This provider is useful for storing history data that needs to be persisted across restarts and shared across multiple instances of the application.

The Redis provider requires the following configuration:
- redis_host (*required* - *string*): The hostname of the Redis server.
- redis_port (*required* - *int*): The port number of the Redis server.
- redis_db (*required* - *int*): The database number to use in the Redis server.

The Redis provider requires the `redis` package. To install the package, run the following command:  

```bash
pip install redis
```

#### **Provider: `mongodb`**
The MongoDB history provider stores history in a MongoDB database. This provider is useful for storing history data that needs to be persisted across restarts and shared across multiple instances of the application.

The MongoDB provider requires the following configuration:
- mongodb_uri (*required* - *string*): The connection URI for the MongoDB server.
- mongodb_db (*optional* - *string* - *default*: `history_db`): The name of the database to use in the MongoDB server.
- mongodb_collection (*optional* - *string* - *default*: `sessions`): The name of the collection to use in the MongoDB database.

The MongoDB provider requires the `pymongo` package. To install the package, run the following command:  

```bash
pip install pymongo
```

#### **Provider: `sql`**
The SQL history provider stores history in a SQL database. This provider is useful for storing history data that needs to be persisted across restarts and shared across multiple instances of the application.

The SQL provider requires the following configuration:
- db_type (*required* - *string*): The type of SQL database to use. Supported values are `postgres` and `mysql`.
- sql_host (*required* - *string*): The hostname of the SQL server.
- sql_user (*required* - *string*): The username to use to connect to the SQL server.
- sql_password (*required* - *string*): The password to use to connect to the SQL server.
- sql_database (*required* - *string*): The name of the database to use in the SQL server.
- table_name (*optional* - *string* - *default*: `session_history`): The name of the table to use in the SQL database.

The SQL provider requires the `psycopg2` package for PostgreSQL or the `mysql-connector-python` package for MySQL. To install the packages, run the following commands:

```bash
pip install psycopg2 mysql-connector-python
```


### Custom History Provider

To create a custom history provider, you can define a class that extends the `BaseHistoryProvider` class provided by Solace Agent Mesh:

```python
from solace_agent_mesh.services.history_service.history_providers.base_history_provider import BaseHistoryProvider
```

Then, implement all abstract methods of the `BaseHistoryProvider` class.

Once completed, you can add the `module_path` key to the configuration object with the path to the custom history provider module:

```json
{
  "type": "custom",
  "module_path": "path.to.custom.history.provider",
  "time_to_live": 3600,
  "expiration_check_interval": 60,
  "history_policy": {
    "max_characters": 30000,
    "max_turns": 10,
    "custom_key_1": "value_1",
    "custom_key_2": "value_2"
  }
}
```


## Long-Term Memory

Solace-Agent-Mesh history service also comes with a long-term memory feature. This feature allows the system to extract and store important information and style preferences from the user's interactions. Also, to keep a track of all topics discussed in the same session. This feature is useful for personalizing the user experience and providing a more engaging conversation.

The long-term memory includes the following 3 features:

- Facts: The system stores important facts and information that the user has shared during the conversation. This information can be used to provide more personalized responses to the user's queries. 
- Instructions: The system can also store instructions provided by the user, which can be referenced in future interactions. These include user preferences, style preferences, and how the system should interact and reply to users.
- Session Summary: The system summarizes the key points discussed during the session, which can help in maintaining context in future interactions. The session summary is forgotten if not accessed for a long time.

Facts and instructions memory are stored and accessible across sessions and gateways. They are tied to the user's unique identifier (provided by the gateway).

### Enabling Long-Term Memory

To enable the long-term memory for a gateway, update the `history_policy` of the `gateway.yaml` file with the following configuration:

```yaml
- history_policy: &default_history_policy
    # ... Some other Configs ...
    enable_long_term_memory: true # Enables the long-term memory feature
    long_term_memory_config: # Required if enable_long_term_memory is set to true
      summary_time_to_live: 432000 # How long to keep the session summary before forgetting, default 5 Days in seconds
      llm_config: # LLM configuration to be used for the AI features of the long-term memory
        model: ${LLM_SERVICE_PLANNING_MODEL_NAME}
        api_key: ${LLM_SERVICE_API_KEY}
        base_url: ${LLM_SERVICE_ENDPOINT}
      store_config: # Configuration for storing long-term memory
        type: "file" # History Provider
        module_path: . # Not required if using one of the existing History Providers
        # Other configs required for the history provider
        path: /tmp/history  # Required for file history provider
```

:::warning
The long-term memory feature requires the gateway to provide unique user identifiers. The user identifier is used to store and retrieve long-term memory information. If the user identifier is not provided, the long-term memory can not be stored separately for each user.
:::
