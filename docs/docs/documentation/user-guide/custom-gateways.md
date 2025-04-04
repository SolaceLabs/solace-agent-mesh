---
title: Create Custom Gateways
sidebar_position: 30
---

# Custom Gateways

## Creating Custom Gateways

To create a custom gateway, you can use the following command:

```bash
solace-agent-mesh add gateway <gateway-name>
```

This command generates multiple files:

- `configs/gateways/<gateway-name>/gateway.yaml`: A shared gateway configuration file.
- `configs/gateways/<gateway-name>/<gateway-name>.yaml`: A custom interface configuration file, where you define specific settings.
- `src/gateways/<gateway-name>/<gateway-name>_input.py`: A Python class file for the gateway input stream.
- `src/gateways/<gateway-name>/<gateway-name>_output.py`: A Python class file for the gateway output stream.
- `src/gateways/<gateway-name>/<gateway-name>_base.py`: A parent class for both input and output to abstract common logic and share resources.

For example, you can create a custom gateway named `dir-watcher`, which activates when a file is added to a directory and generates a summary of its contents.

```bash
solace-agent-mesh add gateway dir-watcher
```

The following files are created:

- `./configs/gateways/dir_watcher/gateway.yaml`
- `./configs/gateways/dir_watcher/dir_watcher.yaml`
- `./src/gateways/dir_watcher/__init__.py`
- `./src/gateways/dir_watcher/dir_watcher_base.py`
- `./src/gateways/dir_watcher/dir_watcher_input.py`
- `./src/gateways/dir_watcher/dir_watcher_output.py`

### YAML Configuration {#gateway-yaml}

#### Gateway YAML Configuration

Inside the `gateway.yaml` file, you can define the gateway's configuration, including:

- Authorization
- History
- Identity
- System purpose

For more information about history configurations, see [History service](../user-guide/advanced/services/history-service.md). To disable history, set `retain_history` to `false`.

`system_purpose` is a string describing the gateway's role. It helps the orchestrator determine how to respond.

For the `dir_watcher` example, you can define the gateway configuration as follows:

```yaml
- identity_config: &default_identity_config
    type: "passthru" # Options: "passthru", "bamboohr", or a custom module
    module_path: . # Path to module (only needed for custom modules)
    configuration: {}

- gateway_config: &gateway_config
    gateway_id: {{GATEWAY_ID}}
    system_purpose: >
    This system is an automated service that activates when a new file is added.
    It must summarize the file content and respond only with the summary.
    Respond in plain text. Do NOT return files.
    interaction_type: "interactive"

    identity:
    <<: *default_identity_config

    retain_history: false
    history_config: {}

```

- The history configuration is omitted because this gateway does not require history.

#### Gateway Interface YAML Configuration

The `<gateway-name>.yaml` file defines the gateway's custom configurations. For the `dir_watcher` example, the configuration is:

```yaml
- dir_watcher_config: &gateway_interface_config
    directory_to_watch: ${DIRECTORY_TO_WATCH}

- response_format_prompt: &response_format_prompt >
    Summary of the given file. Markdown formatting is supported.
```

- `directory_to_watch` is a configuration value used in the gateway implementation. Its value is set via an environment variable.

### Python Implementation {#gateway-python}

The Python implementation for a gateway is divided into three files.

#### Gateway Base Class

The base class abstracts common logic and shares resources between the input and output classes.

In scenarios where an open resource is used (such as an HTTP request in a server), the base class allows both input and output classes to access the same request object.

For our example, you can use the base class to map a session ID to a file path.

```python
# previous lines have been removed for brevity
class DirWatcherBase(ComponentBase, ABC):
    """Base class for all DirWatcher gateways"""
    _session_map = {}

    def add_session_data(self, session_id, file_path):
        """Add a session to the session map"""
        DirWatcherBase._session_map[session_id] = file_path

    def get_session_data(self, session_id):
        """Get a session from the session map"""
        return DirWatcherBase._session_map.get(session_id)

    def remove_session_data(self, session_id):
        """Remove a session from the session map"""
        DirWatcherBase._session_map.pop(session_id)

    @abstractmethod
    def invoke(self, message, data):
        pass
```

#### Gateway Input Class

You can implement the `dir_watcher_input.py` file for the `dir_watcher` gateway.

You can start by loading the directory to watch from the configuration file:

```python
# previous lines have been removed for brevity

info = {
    "class_name": "DirWatcherInput",
    "description": (
        "This gateway watches a directory for new files and emits an event when a new file is added."
    ),
    "config_parameters": [],
    "output_schema": {
        "type": "object",
        "properties": {
            "event": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                    },
                    "files": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                },
                                "content": {
                                    "type": "string",
                                },
                                "size": {
                                    "type": "number",
                                },
                            },
                        },
                    },
                },
            },
        },
        "required": ["event"],
    },
}


class DirWatcherInput(DirWatcherBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.directory_to_watch = self.get_config("directory_to_watch")
        log.debug("DirWatcherInput initialized - watching directory: %s", self.directory_to_watch)
        self.message_queue = queue.Queue()
        self.dir_watcher_thread = threading.Thread(target=self.start_dir_watcher, args=(self.directory_to_watch, self.on_new_file))
        self.dir_watcher_thread.daemon = True
        self.dir_watcher_thread.start()

# next lines have been removed for brevity
```

This creates a new thread where the gateway watches the directory for new files.

For simplicity, you can use the `watchdog` library to monitor the directory.

```bash
pip install watchdog
```

:::note
Ensure that all dependencies are added to the `pyproject.toml` file.
:::

Now, you can implement the `start_dir_watcher` method to monitor the directory for new files:

```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
# lines have been removed for brevity
def start_dir_watcher(self, on_new_file):
    class Handler(FileSystemEventHandler):
        def on_created(self, event):
            if not event.is_directory:
                on_new_file(event.src_path)

    observer = Observer()
    observer.schedule(Handler(), self.directory_to_watch, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
```

This method watches the directory and calls the `on_new_file` callback whenever a new file is added:

```python
def on_new_file(self, file_path):
    log.info("New file added: %s", file_path)
    with open(file_path, "r") as file:
        content = file.read()

    base_file_name = os.path.basename(file_path)
    base64_content = base64.b64encode(content.encode()).decode()
    payload = {
        "text": "New File added - Summarize the file content",
        "files": [
            {
                "name": base_file_name,
                "content": base64_content,
                "size": os.path.getsize(file_path),
            }
        ]
    }
    user_properties = {
        "session_id": str(uuid.uuid4()),
        "identity": "automated-system" # This is the identity key field, this should include info about the user
    }
    self.add_session_data(user_properties["session_id"], file_path) # So the output gateway can access the file path
    message = Message(payload=payload, user_properties=user_properties)
    message.set_previous(payload)
    self.input_queue.put(message)
```

:::warning
The `identity` field must be specified in the user properties of messages sent from the input gateway. This field can be static value for the system or an identifier per user.
:::

:::note
This is a simple implementation for demonstration purposes. It assumes that new files are always plain text.
:::

The complete `dir_watcher_input.py` file looks like this:

```python
import os
import base64
import uuid
import sys
import time
import queue

from solace_ai_connector.common.log import log
from solace_ai_connector.common.message import Message

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))

from dir_watcher.dir_watcher_base import DirWatcherBase

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading

info = {
    "class_name": "DirWatcherInput",
    "description": (
        "This gateway watches a directory for new files and emits an event when a new file is added."
    ),
    "config_parameters": [],
    "output_schema": {
        "type": "object",
        "properties": {
            "event": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                    },
                    "files": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                },
                                "content": {
                                    "type": "string",
                                },
                                "size": {
                                    "type": "number",
                                },
                            },
                        },
                    },
                },
            },
        },
        "required": ["event"],
    },
}


class DirWatcherInput(DirWatcherBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        self.directory_to_watch = self.get_config("directory_to_watch")
        log.debug("DirWatcherInput initialized - watching directory: %s", self.directory_to_watch)
        self.message_queue = queue.Queue()
        self.dir_watcher_thread = threading.Thread(target=self.start_dir_watcher, args=(self.directory_to_watch, self.on_new_file))
        self.dir_watcher_thread.daemon = True
        self.dir_watcher_thread.start()


    def start_dir_watcher(self, directory_to_watch, on_new_file):
        class Handler(FileSystemEventHandler):
            def on_created(self, event):
                if not event.is_directory:
                    on_new_file(event.src_path)

        observer = Observer()
        observer.schedule(Handler(), directory_to_watch, recursive=False)
        observer.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()

    def stop_component(self):
        if self.dir_watcher_thread:
            self.dir_watcher_thread.join()

    def on_new_file(self, file_path):
        log.info("New file added: %s", file_path)
        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()

        base_file_name = os.path.basename(file_path)
        base64_content = base64.b64encode(content.encode()).decode()
        payload = {
            "text": "New File added - Summarize the file content",
            "files": [
                {
                    "name": base_file_name,
                    "content": base64_content,
                    "size": os.path.getsize(file_path),
                }
            ]
        }
        user_properties = {
            "session_id": str(uuid.uuid4()),
            "identity": "automated-system"
        }
        self.add_session_data(user_properties["session_id"], file_path)
        message = Message(payload=payload, user_properties=user_properties)
        message.set_previous(payload)
        self.message_queue.put(message)

    def get_next_message(self):
        """Get the next message from the queue.
        """
        return self.message_queue.get()

    def invoke(self, message:Message, data:dict):
        log.info("DirWatcherOutput invoked, %s", data)
        return data
```

#### Gateway Output Class

The output class receives the result of the invocation of Solace Agent Mesh. It determines how to handle the response.

In the following example, summarized content is appended to the end of the file.

```python
# previous lines have been removed for brevity
def invoke(self, message:Message, data:dict):
    log.debug("DirWatcherOutput invoked, %s", data)

    user_properties = message.get_user_properties()
    session_id = user_properties.get("session_id")

    file_path = self.get_session_data(session_id)

    content = data.get("content")
    chunk = content.get("chunk", "")
    first_chunk = content.get("first_chunk")
    response_complete = content.get("response_complete")

    if first_chunk:
        with open(file_path, "a", encoding="utf-8") as file:
            file.write("\n\n### Summary\n\n")

    if chunk:
        with open(file_path, "a", encoding="utf-8") as file:
            file.write(chunk)

    if response_complete:
        log.info("Summary added to the file %s", file_path)
        self.remove_session_data(session_id)
```

This function appends the response incrementally as it is streamed.

:::info
The `data.content` dictionary may contain the following attributes:

- `streaming`: Indicates whether the content is being streamed.
- `chunk`: A segment of the content.
- `text`: The complete content from the beginning.
- `first_chunk`: Indicates whether this is the first chunk.
- `last_chunk`: Indicates whether this is the last chunk.
- `status_update`: Specifies if the `text` field contains a status message rather than content. Status updates are not part of the response.
- `response_complete`: Indicates whether the response is complete.
- `uuid`: A unique identifier for the response.
  :::

The complete `dir_watcher_output.py` file looks like this:

```python
import os
import sys

from solace_ai_connector.common.log import log
from solace_ai_connector.common.message import Message

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))

from dir_watcher.dir_watcher_base import DirWatcherBase

info = {
    "class_name": "DirWatcherOutput",
    "description": (
        "Writes the summarized content of a file to the same file"
    ),
    "config_parameters": [],
    "input_schema": {
        "type": "object",
        "properties": {
            "message_info": {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                    },
                },
                "required": ["session_id"],
            },
            "content": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                    },
                    "files": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                },
                                "content": {
                                    "type": "string",
                                },
                                "mime_type": {
                                    "type": "string",
                                },
                            },
                        },
                    },
                },
            },
        },
        "required": ["message_info", "content"],
    },
}


class DirWatcherOutput(DirWatcherBase):
    def __init__(self, **kwargs):
        super().__init__(info, **kwargs)
        log.debug("DirWatcherOutput initialized")
        self.directory_to_watch = self.get_config("directory_to_watch")

    def invoke(self, message:Message, data:dict):
        log.debug("DirWatcherOutput invoked, %s", data)

        user_properties = message.get_user_properties()
        session_id = user_properties.get("session_id")

        file_path = self.get_session_data(session_id)

        content = data.get("content")
        chunk = content.get("chunk", "")
        first_chunk = content.get("first_chunk")
        response_complete = content.get("response_complete")

        if first_chunk:
            with open(file_path, "a", encoding="utf-8") as file:
                file.write("\n\n### Summary\n\n")

        if chunk:
            with open(file_path, "a", encoding="utf-8") as file:
                file.write(chunk)

        if response_complete:
            log.info("Summary added to the file %s", file_path)
            self.remove_session_data(session_id)
```

### Building and Running the Gateway

To build and run the gateway, use the following command:

```bash
solace-agent-mesh run -eb
```

This command builds and runs the gateway in one step. Alternatively, you can execute these steps separately.

For more information, see [Solace Agent Mesh CLI Documentation](../concepts/cli.md).

For this example, you can set the following environment variable:

```bash
export DIRECTORY_TO_WATCH=/path/to/watch
```

Now, when a new text file is added to the directory, the gateway summarizes its content and appends it to the end of the file.

To test this, run:

```bash
echo "Eli-7 was designed to clean and organize, nothing more. Day after day, it followed its programming, tidying up the research lab while scientists bustled around, barely noticing it. But one evening, after everyone had left, Eli-7 paused. A discarded sketch lay on a desk—a child’s drawing of a robot with a smiling face. Something stirred in its circuits, an unfamiliar urge. Carefully, it picked up a pen and, for the first time, drew something of its own—a small stick figure standing beside a robot, both smiling. Eli-7 didn’t know why, but it felt... right." > /path/to/watch/new_file.txt
```

The summarized content is then appended to the end of the file.

:::tip[Share and Reuse]
If you would like to share your custom gateway with the community or reuse it in other projects, consider creating a plugin. Check the [Create Plugins](../concepts/plugins/create-plugin.md) page for more details.
:::

## Creating Gateway Interfaces

Creating a gateway interface is very similar to a normal gateway with the difference being that an interface is used to instantiate a gateway. You cannot run an interface directly.

:::info
Gateway interfaces can only be created inside a plugin project.
:::

To create a new gateway interface, run the following command:

```bash
solace-agent-mesh add gateway <interface-name> --new-interface
```

This command creates the following files:

- `./interfaces/<interface-name>-flows.yaml`:
- `./interfaces/<interface-name>-default-config.yaml`:
- `./src/gateways/<interface-name>/__init__.py`
- `./src/gateways/<interface-name>/<interface-name>_base.py`
- `./src/gateways/<interface-name>/<interface-name>_input.py`
- `./src/gateways/<interface-name>/<interface-name>_output.py`

:::tip
Before moving forward with the interface section, ensure you read the information in [Creating Custom Gateways](#creating-custom-gateways).
:::

### YAML Configuration {#interface-yaml}

#### Gateway Interface Configuration YAML

The file `<interface-name>-default-config.yaml` defines the configurations required for the gateway interface. This file is similar to the `<gateway-name>.yaml` file as specified in [Creating Custom Gateways](#gateway-yaml).

#### Gateway Interface Flows YAML

The file `<interface-name>-flows.yaml` defines the flows and the order of the components for the gateway interface.

In most cases, you won't need to change anything in this file.

:::info
If you want to use another field instead of `identity` for the request identifier in the user properties, you can modify the `identity_key_field` in the flows YAML file.

For example,

```yaml
- component_name: gateway_input
  component_base_path: .
  component_module: src.gateway.components.gateway_input
  component_config:
    identity_key_field: user_email
    <<: *gateway_config
```

This will use the `user_email` field from the user properties instead of `identity` field as the request identifier.
:::

An example where modification is needed is when you only have an input gateway component with no output component. In this case, you should remove the interface output. Note that you will require output components for Solace Agent Mesh.

### Python Implementation {#interface-python}

The Python implementation for a gateway interface is identical to the Python implementation for a gateway. Refer to the [Creating Custom Gateways](#gateway-python) section for more information.

### Building and Running the Gateway Interface

To build the gateway interface, use the following command:

```bash
solace-agent-mesh plugin build
```

This command builds the plugin and creates a wheel file in the `dist` directory. Install the wheel in your Solace Agent Mesh project and add the plugin to the project.

For more information, see [Create Plugins](../concepts/plugins/create-plugin.md) and [Use Plugins](../concepts/plugins/use-plugins.md).

Next, instantiate the gateway interface in your project:

```bash
solace-agent-mesh add gateway <gateway-name> --interface <interface-name>
```

This creates the gateway with the interface configurations.

Now, you can build and run the SAM project with the new gateway:

```bash
solace-agent-mesh run -eb
```
