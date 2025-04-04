---
title: Configuration
sidebar_position: 40
toc_max_heading_level: 5
---

# Configuration

Solace Agent Mesh uses a YAML-based configuration system. The main configuration file is `solace-agent-mesh.yaml` in your project root.

:::info
Removing any configuration will use the default values for that configuration.
:::

## Core Configuration

### Built-in Components

You can configure the built-in agents using a YAML file. For more information, see [Agents](../concepts/agents.md#built-in-agents).

```yaml
built_in:
  agents:
    - name: web_request
      enabled: true    # Enable/disable web request capabilities
    - name: global
      enabled: true    # Enable/disable global agent
    - name: image_processing
      enabled: true    # Enable/disable image processing
    - name: slack
      enabled: false   # Enable/disable Slack Report integration
```

### Directory Configuration

You can specify the locations for where the system looks for various components:

```yaml
config_directory: tmp/configs
modules_directory: tmp/modules 
overwrite_directory: tmp/overwrite
env_file: .env
```

- `config_directory`: The source component YAML config files. [more 🔗](../user-guide/structure.md).
- `modules_directory`: The Python module files. [more 🔗](../user-guide/structure.md).
- `overwrite_directory`: The custom configuration overwrites. [more 🔗](../user-guide/advanced/overwrites.md).
- `env_file`: The environment variables file. This file is automatically created if `build.extract_env_vars` is set to `true`.

### Build Settings

You can configure the build process:

```yaml
build:
  build_directory: build              # Output directory for generated files
  extract_env_vars: false             # Extract environment variables from configs
  log_level_override: INFO            # Override default logging level
  orchestrator_instance_count: 5      # Number of orchestrator instances
```

- `build_directory`: The output directory for generated files.
- `extract_env_vars`: Extract the required environment variables from the configurations and write them to an `.env` file.
- `log_level_override`: Override the default logging-level for all components.
- `orchestrator_instance_count`: The number of instances of the orchestrator component to run in parallel.

### Runtime Configuration

Runtime configurations are settings that are loaded when you start the application. Those configurations are copied to the `build_directory`.

#### Services

You can include the configuration for the [services](../concepts/services.md) used by the system.

```yaml
runtime:
  services:
    file_service:
```

##### File Service

You can configure how the File service handles temporary file storage. For more information, see [File Service](../user-guide/advanced/services/file-service.md).

```yaml
runtime:
  services:
    file_service:
      type: volume
      max_time_to_live: 86400 # 1 day
      expiration_check_interval: 600 # 10 minutes
      config: {}
```

- `type`: The File service type, for example, `volume`, `bucket`, `memory`, or `your-custom-service`.
- `max_time_to_live`: The file retention period, in seconds.
- `expiration_check_interval`: The clean-up check interval, in seconds.
- `config`: The service-specific configurations. The config `key` must match the service `type`.

File service types:

1. **Volume Storage**
   ```yaml
   config:
     volume:
       directory: /tmp/solace-agent-mesh
   ```

   - **directory**: Directory path for file storage.

2. **S3 Bucket Storage**
   ```yaml
   config:
     bucket:
       bucket_name: your-bucket
       endpoint_url: optional-endpoint
       boto3_config:
         region_name: aws-region
         aws_access_key_id: your-key
         aws_secret_access_key: your-secret
   ```
    - **bucket_name**: The S3 bucket name.
    - **endpoint_url**: (Optional) The S3 endpoint URL. The default is AWS S3.
    - **boto3_config**: The AWS SDK for Python (Boto3) configuration for the S3 client. The default uses the local AWS configuration.

    :::tip
    You can use this option with AWS S3-compatible services, such as [localstack](http://localstack.cloud/).
    :::

3. **Custom Storage**
   ```yaml
   config:
     YourCustomModule:
       module_path: path/to/module
       custom_key: value
   ```
    - **module_path**: The path to the custom python module file.
    - **custom_key**: The key/value pair for the custom configuration.

### Plugins

You can configure the plugins list and load multiple configurations using plugins. For more information, see [Plugins](../concepts/plugins/index.md).

```yaml
  plugins:
  - name: plugin_name
    load_unspecified_files: false
    includes_gateway_interface: false
    load:
      agents: []
      gateways: []
      overwrites: []
```
