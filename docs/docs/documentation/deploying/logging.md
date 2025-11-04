---
title: Logging
sidebar_position: 35
---

# Logging

This guide covers the essential information you need to effectively configure and manage logging in your Agent Mesh applications. Proper logging configuration is critical for troubleshooting issues, monitoring system behavior, and maintaining reliable production deployments.

Agent Mesh uses [Python's built-in logging module](https://docs.python.org/3/library/logging.html) to provide flexible and powerful logging capabilities.

This approach provides several advantages:

- **Centralized Control**: Single configuration file manages logging for all components
- **Python Native**: Built on Python's standard `logging` module
- **Flexible and Powerful**: Full access to Python's logging capabilities
- **Production-Ready**: Industry-standard approach used by many Python applications

## Configuration

Agent Mesh supports logging configuration as either a YAML or JSON file. Both formats leverage Python's [dictConfig](https://docs.python.org/3/library/logging.config.html#logging.config.dictConfig) method for advanced logging features.

To provide a logging configuration, set the `LOGGING_CONFIG_PATH=path/to/logging_config.yaml` environment variable in your `.env` file or with the `export` command.

:::info
While the INI format using [Python's fileConfig()](https://docs.python.org/3/library/logging.config.html#configuration-file-format) is still supported by Agent Mesh, it is not recommended due to its limitations compared to YAML and JSON formats.
:::

:::info[Agent/Gateway Specific Logging Configuration]
While individual agent and gateway YAML files may contain a `log:` section:
```
log:
  stdout_log_level: INFO
  log_file_level: INFO
  log_file: my-agent.log
```
using a dedicated logging configuration file (YAML, JSON) is the recommended and preferred approach. The simple `log:` section configuration has lower precedence and will only be active when a dedicated logging configuration file is not provided.
:::

## Default Logging Configuration

When you run `sam init`, Agent Mesh automatically generates a `configs/logging_config.yaml` file in your project directory. This file establishes sensible defaults while remaining easy to customize for your specific needs.

```yaml
# Python logging configuration version (always 1)
version: 1

# Don't disable existing loggers when this config is loaded
disable_existing_loggers: false

# Formatters control the structure and appearance of log messages
formatters:
  # Simple human-readable format
  simpleFormatter:
    format: "%(asctime)s | %(levelname)-5s | %(threadName)s | %(name)s | %(message)s"
  
  # JSON format for structured logging
  jsonFormatter:
    "()": pythonjsonlogger.json.JsonFormatter # The python-json-logger package is used for JSON formatting
    format: "%(asctime)s %(levelname)s %(threadName)s %(name)s %(message)s"

# Handlers determine where log messages go
handlers:
  # Stream handler - outputs logs to console (stdout)
  streamHandler:
    class: logging.StreamHandler
    formatter: simpleFormatter
    stream: "ext://sys.stdout"
  
  # Rotating file handler - writes to log files with automatic rotation
  rotatingFileHandler:
    class: logging.handlers.RotatingFileHandler
    formatter: simpleFormatter
    filename: sam.log
    mode: a             # Append mode - don't overwrite existing logs
    maxBytes: 52428800  # 50 MB - rotate when file reaches this size
    backupCount: 10     # Keep up to 10 historical log files

# Loggers 
loggers:
  # Keys are logger names used in the application code
  solace_ai_connector:
    level: ${LOGGING_SAC_LEVEL, INFO}
    handlers: []
  
  solace_agent_mesh:
    level: ${LOGGING_SAM_LEVEL, INFO}
    handlers: []
  
  # Special trace logger for detailed troubleshooting. Set to DEBUG to enable.
  sam_trace:
    level: ${LOGGING_SAM_TRACE_LEVEL, INFO}
    handlers: []

# Root logger - applies to all log statements (including those from external libraries) that propagate up to root
# The root logger also specifies handlers for the application
root:
  level: ${LOGGING_ROOT_LEVEL, WARNING}
  handlers:
    - streamHandler
    - rotatingFileHandler
```

:::note 
The examples in this documentation use YAML format, but examples can be easily converted to JSON if preferred.
:::

### Loggers

Loggers are organized in a hierarchical namespace using dot-separated names, forming a tree structure where child loggers inherit configuration from their parents. When a logger is asked to handle a log record, it propagates the record up through the logger hierarchy until it reaches a logger with handlers configured or reaches the root logger.

### Handlers

Handlers determine where log messages go. The default configuration includes:

- **`streamHandler`**: Outputs logs to the console (stdout) for immediate visibility
- **`rotatingFileHandler`**: Writes logs to files with automatic rotation when size limits are reached.

For complete details on handlers, see Python's [supported handlers documentation](https://docs.python.org/3/library/logging.handlers.html) 

### Formatters

Formatters control the structure and appearance of log messages:

- **`simpleFormatter`**: Human-readable format including timestamp, level, thread, logger name, and message
- **`jsonFormatter`**: Structured JSON format for log aggregation and analysis tools

For complete details on formatters and available fields, see Python's [LogRecord attributes documentation](https://docs.python.org/3/library/logging.html#logrecord-attributes).

### Understanding Effective Log Levels

The effective log level for a logger is determined by the most specific configuration in the logger hierarchy. If a logger doesn't have a level explicitly set, it inherits from its parent. The root logger applies to all modules that do not have a logger defined. 

For example, if you set the root logger to DEBUG but create a more specific logger for solace_ai_connector at the INFO level, the effective log level for the solace_ai_connector module will be INFO. This means DEBUG level logs from solace_ai_connector will not be handled, as they fall below the effective log level.

## Environment Variable Substitution {#env-var-substitution}

All configuration formats (YAML, JSON, and INI) support environment variable substitution using the syntax:
```yaml
${VARIABLE_NAME, default_value}
```
Users can use variable names of their choice; the application will look for these environment variables at runtime and substitute their values accordingly. If the environment variable is not set, the provided default value will be used.

## Common Configuration Scenarios

### Structured Logging

Structured logging outputs log messages in JSON format, making them easier to parse, search, and analyze in log aggregation systems like Datadog, Splunk, Elasticsearch, and others.

Enabling structured logging includes two steps.

#### 1- Enable JSON Formatter

Structured logging is enabled by assigning the `jsonFormatter`, which is provided in the default logging configuration, to one or more logging handlers in your configuration. This means log messages handled by those specific handlers will be output in structured JSON format.

```yaml
handlers:
  rotatingFileHandler:
    class: logging.handlers.RotatingFileHandler
    formatter: jsonFormatter  # Changed from simpleFormatter
    filename: sam.log
    mode: a
    maxBytes: 52428800
    backupCount: 10
  
  streamHandler:
    class: logging.StreamHandler
    formatter: simpleFormatter  # Kept as simpleFormatter to show handlers can have different formatters
    stream: "ext://sys.stdout"
```

#### 2- Configure Contextual Info (Optional)

Log aggregation systems often expect contextual fields to be included in log records for better filtering, grouping, and analysis. For example, contextual fields like `service` and `env` can be added to each log record to indicate which service generated the log and the environment it ran in.

To add contextual info to every log record, use [python-json-logger's static_fields feature](https://nhairs.github.io/python-json-logger/latest/quickstart/#static-fields) as shown below:

```yaml
  jsonFormatter:
    "()": pythonjsonlogger.json.JsonFormatter
    format: "%(asctime)s %(levelname)s %(threadName)s %(name)s %(message)s"
    static_fields:
      service: ${SERVICE_NAME, payment-service}
      env: ${ENV, production}
```

With this `jsonFormatter` configuration, all JSON log records will automatically include the specified static fields:

```json
{
   "asctime":"2025-10-30 22:25:56,960",
   "levelname":"INFO",
   "threadName":"MainThread",
   "name":"solace_ai_connector.flow",
   "message":"Processing message",
   "service": "payment-service",
   "env": "production"
}
```

Notice that [environment variable substitution](#env-var-substitution) can be used for increased flexibility.

### Customizing Log Levels

You can add loggers to control the log level of specific modules or external libraries in your application. This allows you to increase verbosity for troubleshooting specific components while keeping other parts of the system quiet.

```yaml
loggers:
  solace_ai_connector:
    level: INFO
    handlers: []
  
  solace_agent_mesh:
    level: INFO
    handlers: []
  
  sam_trace:
    level: INFO
    handlers: []
  
  # Increase verbosity of a specific package
  solace_agent_mesh.gateway.http_sse:
    level: DEBUG
    handlers: []
  
  # Increase verbosity of a specific external library
  google_adk:
    level: INFO
    handlers: []

root:
  level: WARNING
  handlers:
    - streamHandler
    - rotatingFileHandler
```

:::tip[Discovering Logger Names]
To discover what logger names are available to control, temporarily set the root logger level to `DEBUG` and run your application. The logger names will be visible in the actual log output (shown in the logger name field). This is particularly useful for identifying logger names from external libraries you want to control.

Once you've identified the logger names you need, you can:
1. Set the root logger level back to `WARNING` to reduce overall verbosity
2. Add specific logger configurations for the modules/library you want to monitor with increased verbosity

This approach keeps your logs clean while giving you detailed visibility into the specific components you're troubleshooting.
:::
