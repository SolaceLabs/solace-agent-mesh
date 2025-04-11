---
title: File Service  
sidebar_position: 10  
---

# File Service  

The File service is a global service that provides short-term file storage capabilities for Solace Agent Mesh framework. This service enables efficient handling of large files within the system **without overloading the PubSub+ event broker or the LLM context**.  


The key features of the File service include:  

1. **Short-term Storage**: The service offers temporary storage for files that need to be shared between components in the system. Files are stored for one day, after which they are automatically deleted. This short-term storage time is configurable.

2. **Upload and Download Functionality**: Components can upload files to the service and download them as needed.  

3. **Efficient File Handling**: Large files can be used in the system without transferring them entirely over the event broker, reducing network load and improving system performance. Additionally, extracted metadata is added to the LLM context instead of the file content itself, allowing for efficient processing of large files. The LLM can request the complete file content if necessary.  

4. **File URLs**: The service generates specialized file URLs that can be included in events. These URLs allow components to reference and access files without embedding the entire file content in the event payload. Furthermore, these URLs can be used to access a subset of data within the file without opening it.  

5. **On-demand Access**: Components that need to work with a file can download it using the provided URL, ensuring that only necessary data transfers occur.  

6. **Security**: On upload, files are tagged with the session ID. A file is only available for download by entities with the same ID. The download mechanism verifies the ID to prevent AI injection attacks.  

The following are example use cases for this service: 

- A gateway receives a large data file from an external source, such as a file uploaded into Slack.  
- The gateway uploads the file to the File service and includes the generated file URL in the event payload.  
- At the time of upload, the file is tagged with the stimulus UUID and given a TTL value that exceeds the expected processing time of the stimulus.  
- An action that needs to process the file can download it using the provided URL without transferring the entire file over the PubSub+ event broker.  

This approach significantly reduces the load on the PubSub+ event broker and allows for more efficient handling of large data files within Solace Agent Mesh framework.  


### File Metadata  

Once a file is uploaded using the File service, a metadata object is automatically created. This metadata contains key information about the file, providing the LLM with enough context to process the file without accessing its content.  

The metadata includes:  
- filename  
- file size  
- MIME type (extracted from the file extension)  
- file URL  
- upload timestamp  
- expiry timestamp  
- session ID  
- file schema (for structured files)  
- file shape (for structured files)  
- data source (optional)  

### File URL  

The File service uses a URL format that ensures uniqueness, security, and transformation. The format is as follows:  

```
amfs://<file-random-sig>_<filename>?<transformation-params>
```

Where:  
- `<file-random-sig>`: A long, randomly generated signature for the specific file.  
- `<filename>`: The original filename (URL-encoded).  
- `<transformation-params>`: Optional parameters for transformations.  

**Example URL:**  

```
amfs://a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s_important_document.pdf
```

This URL structure allows for easy file management, secure access control, and efficient debugging when necessary.  

### File Schema and Shape  

For structured files, the File service extracts the schema and shape of the file and includes it in the metadata. This information helps the LLM process the file content efficiently.  

- **Schema**: For a CSV file, the schema is derived from the header row. For a YAML or JSON file, it consists of key-type pairs.  
- **Shape**: Represents the structure of the file, such as the number of rows and columns in a table or the length of top-level arrays.  

#### Example Schema and Shape  

For a CSV file with the following content:  

```csv
Name,Age
Alice,25
Bob,30
```

**Schema:**  

```json
{
  "type": "array",
  "items": {
    "type": "object",
    "properties": {
      "Name": { "type": "string" },
      "Age": { "type": "int" }
    }
  }
}
```

**Shape:**  

```
2 rows x 2 columns
```

For a JSON file:  

```json
[
    {
        "name": "John",
        "age": 30,
        "numbers": [1, 2, 3],
        "addresses": [
            {
                "city": "New York",
                "zipcode": "10001",
                "values": [85.5, 90]
            },
            {
                "city": "Los Angeles",
                "zipcode": "90001",
                "values": [85.5, 90]
            }
        ]
    }
]
```

**Schema:**  

```json
{
  "type": "array",
  "items": {
    "type": "object",
    "properties": {
      "name": { "type": "str" },
      "age": { "type": "int" },
      "numbers": { "type": "array", "items": "int" },
      "addresses": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "city": { "type": "str" },
            "zipcode": { "type": "str" },
            "values": { "type": "array", "items": "float" }
          }
        }
      }
    }
  }
}
```

**Shape:**  

```
top level: 1  
[*].numbers: 3  
[*].addresses: 2  
```

### Data Source  

The entity uploading the file can optionally include a data source field in the metadata. This field helps track the file's origin and provides additional processing context.  

A typical format for the agent would be:  

```
<agent-name> - <action-name> - <extra-info>
```

- `<agent-name>`: The agent responsible for the action.  
- `<action-name>`: The name of the action that uploaded the file.  
- `<extra-info>`: Optional additional data, e.g., the query used to fetch the data.  

## Usage  

The `FileService` class in the Solace Agent Mesh framework provides methods to upload, download, and retrieve file metadata.  

### Importing the File Service  

```python
from solace_agent_mesh.services.file_service import FileService
```

Then, create an instance of `FileService`. (It is a singleton, so it can be instantiated anywhere in your code.)  

```python
file_service = FileService()
```

### Uploading a File

To upload a file to the File service, use one of the following two methods to upload a file:

- `upload_from_buffer(buffer: bytes, file_name: str, session_id: str, **kwargs) -> dict`
- `upload_from_file(file_path: str, session_id: str, **kwargs) -> dict:`

From buffer:

```python
file_name = "important_document.pdf"

with open(file_path, "rb") as file:
    file_content = file.read()

data_source = "my_agent - my_action - query"
file_metadata = file_service.upload_from_buffer(file_content, file_name, session_id, data_source=data_source)
```

:::note
The buffer must be of type `bytes`.
You can convert strings to bytes using `str.encode()`.
:::

From file:

```python
file_path = "path/to/important_document.pdf"
data_source = "my_agent - my_action - query"

file_metadata = file_service.upload_from_file(file_path, session_id, data_source=data_source)
```

:::note
The `kwargs` parameters are added to the metadata object. 
:::

### Downloading a File

To download a file from the File service, use one of the following two methods:

- `download_to_buffer(file_url: str, session_id: str) -> bytes`
- `download_to_file(file_url: str, destination_path: str, session_id: str) -> None`

To buffer:

```python
file_url = file_metadata["url"]

file_content = file_service.download_to_buffer(file_url, session_id)
```

To file:

```python
file_url = file_metadata["url"]
destination_path = "path/to/important_document.pdf"

file_service.download_to_file(file_url, destination_path, session_id)
```

## File Managers

The `FileService` class uses a file manager to handle file storage and retrieval. The file manager is responsible for storing files, and metadata, and providing access to the files when needed.

Solace Agent Mesh comes with the following built-in file managers:

- **Volume File Manager**: Stores files on the local file system.
- **Bucket File Manager**: Stores files on an S3 compatible storage service.
- **Memory File Manager**: Stores files in memory (for testing purposes).

This value can be set in [configuration](../../../getting-started/configuration.md) using the `runtime.services.file_service.type` key.


Check the next section to learn how to create and configure a custom file manager.

### Custom File Manager  

To create a custom file manager, extend the `BaseFileManager` class:  

```python
from solace_agent_mesh.services.file_service.file_manager.file_manager_base import BaseFileManager
```

Then, implement all the abstract methods.

Once completed, you can update the [configuration](../../../getting-started/configuration.md) file as follows:

```yaml
services:
  file_service:
    type: YourCustomModule # Your custom file manager class name
    max_time_to_live: 86400 # 1 day
    expiration_check_interval: 600 # 10 minutes
    config:
      YourCustomModule: # Your custom file manager class name
        module_path: path/to/module # Path to file manager python file
        custom_key_1: value one # Optional custom key-value pairs
        custom_key_2: value two
```

:::note
You can access the custom key-value pairs in the file manager using the `config` attribute.
:::
