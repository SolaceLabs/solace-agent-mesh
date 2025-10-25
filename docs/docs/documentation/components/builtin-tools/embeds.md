---
title: Dynamic Embeds
sidebar_position: 40
---

## Dynamic Embeds

Dynamic embeds provide a mechanism for agents to insert context-dependent information into their text responses or tool parameters using a specialized `«...»` syntax. This feature allows for the dynamic retrieval and formatting of data without requiring explicit tool calls for simple data retrieval or calculations.

### Overview

Dynamic embeds allow an agent to defer the inclusion of data until it is needed, resolving the value just before the final response is sent to the user.

-   **Standard Approach**: "The current time is [call `get_time` tool]."
-   **With Dynamic Embeds**: "The current time is `«datetime:%H:%M»`."

The system resolves the embed directive, a dynamic placeholder for data that gets computed at runtime, replacing it with the evaluated result (for example, "The current time is 10:45.").

### Syntax

There are two primary syntaxes for embed directives.

#### Simple Syntax
This syntax is used for most general-purpose embeds.

```
«type:expression | format_spec»
```
- **`type`**: A keyword indicating the type of information to embed (for example, `state`, `math`, `datetime`).
- **`expression`**: The specific data to retrieve or the expression to evaluate.
- **`format_spec`**: (Optional) A specifier for formatting the output value (for example, a number precision `.2f` or a `strftime` string `%Y-%m-%d`).

#### Chain Syntax
This syntax is used exclusively for the `artifact_content` embed type to apply a sequence of transformations.

```
«artifact_content:spec >>> modifier1 >>> modifier2 >>> format:output_format»
```
- **`artifact_spec`**: The artifact identifier (`filename[:version]`).
- **`>>>`**: The chain delimiter, separating transformation steps.
- **`modifier`**: A transformation to apply to the data (for example, `jsonpath`, `grep`, `slice_lines`).
- **`format`**: A **required** final step that specifies the output format (for example, `text`, `json`, `datauri`).

### Available Embed Types

#### General Purpose Embeds
These are typically resolved by the agent host during execution.

| Type              | Description                                       | Example                                               |
| ----------------- | ------------------------------------------------- | ----------------------------------------------------- |
| **`state`**       | Accesses a session state variable.                | `«state:user_name»`                                   |
| **`math`**        | Evaluates a mathematical expression.              | `«math:100 * 0.05 \| .2f»` (Result: `5.00`)            |
| **`datetime`**    | Inserts the current date and/or time.             | `«datetime:%Y-%m-%d»` (Result: `2023-10-27`)           |
| **`uuid`**        | Inserts a random Version 4 UUID.                  | `«uuid:»`                                             |
| **`status_update`**| Signals a temporary status update to the UI.      | `«status_update:Searching knowledge base...»`         |

#### Artifact-Related Embeds

##### `artifact_meta`
Retrieves a JSON string containing the full metadata of a specified artifact.
- **Syntax**: `«artifact_meta:filename[:version]»`
- **Example**: `«artifact_meta:report.csv»`

##### `artifact_return`
**This is the primary way to return an artifact to the user.** It attaches the specified artifact to the message as a file attachment. The embed itself is removed from the text during gateway processing.

- **Syntax**: `«artifact_return:filename[:version]»`
- **Resolution**: Late-stage (processed by gateway before sending to user)
- **Examples**:
  - `«artifact_return:report.pdf»` - Returns the latest version of report.pdf
  - `«artifact_return:data.csv:3»` - Returns version 3 of data.csv
- **Note**: `artifact_return` is not necessary if the artifact was just created in the same response, since newly created artifacts are automatically attached to messages.

##### `artifact_content`
Embeds the content of an artifact, with support for a chain of transformations. This is the most advanced embed type.

**Note**: If this embed resolves to binary content (like an image), it will be automatically converted into an attached file, similar to `artifact_return`.

**Modifiers (Data Transformations)**
Modifiers are applied sequentially to transform the data.

| Modifier                  | Description                                                                    |
| ------------------------- | ------------------------------------------------------------------------------ |
| `jsonpath:<expr>`         | Applies a JSONPath query to JSON data.                                         |
| `select_cols:<c1,c2>`     | Selects specific columns from CSV data.                                        |
| `filter_rows_eq:<col>:<val>`| Filters CSV rows where a column's value equals the specified value.            |
| `slice_rows:<start>:<end>`| Selects a slice of rows from CSV data.                                         |
| `slice_lines:<start>:<end>`| Selects a slice of lines from text data.                                       |
| `grep:<pattern>`          | Filters lines matching a regular expression in text data.                      |
| `head:<N>` / `tail:<N>`   | Returns the first or last N lines of text data.                                |
| `select_fields:<f1,f2>`   | Selects specific fields from a list of dictionaries.                           |
| `apply_to_template:<file>`| Renders data using a Mustache template artifact. See the [Templates Guide](#templates). |

**Formatters (Final Output)**
This is the **required** final step in an `artifact_content` chain, defining the output format.

| Formatter       | Description                                                                    |
| --------------- | ------------------------------------------------------------------------------ |
| `text`          | Plain text, decoded as UTF-8.                                                  |
| `json` / `json_pretty` | A compact or indented JSON string.                                       |
| `csv`           | A CSV formatted string.                                                        |
| `datauri`       | A Base64-encoded data URI, typically for images (`data:image/png;base64,...`). |

**`artifact_content` Examples:**
- To embed an image for display in a UI:
  `«artifact_content:logo.png >>> format:datauri»`
- To extract and format specific data from a JSON file:
  `«artifact_content:results.json >>> jsonpath:$.data[*].name >>> format:json»`
- To get the last 10 lines of a log file:
  `«artifact_content:debug.log >>> tail:10 >>> format:text»`
- To filter a CSV file and render it using an HTML template:
  `«artifact_content:users.csv >>> filter_rows_eq:Status:Active >>> apply_to_template:active_users.html >>> format:text»`

### Technical Details

#### Resolution Stages
Embeds are resolved in two distinct stages, depending on where the required data is available:
1.  **Early Stage (Agent Host)**: Resolved by the agent runtime itself. This stage handles simple, context-local embeds like `state`, `math`, and `datetime`.
2.  **Late Stage (Gateway)**: Resolved by the Gateway component before the final message is sent to the client. This is necessary for `artifact_content` embeds, which may involve large files or transformations that are too resource-intensive for the agent host.

#### Configuration
- **Enabling/Disabling**: Embed resolution is enabled by default. It can be disabled in the `app_config` of the agent host or gateway by setting `enable_embed_resolution: false`.
- **Resource Limits**: The gateway enforces configurable limits to prevent abuse, including `gateway_artifact_content_limit_bytes` (default: 32KB) and `gateway_recursive_embed_depth` (default: 3).

### Error Handling
If an embed directive fails during parsing or evaluation, it is replaced with a descriptive error message in the final output.
- **Parsing Error**: `[Error: Invalid modifier format: 'badmodifier']`
- **Evaluation Error**: `[Error: State variable 'user_id' not found]`
- **Limit Exceeded**: `[Error: Artifact 'large_file.zip' exceeds size limit]`

## Templates

### Using Templates for Formatted Output

The `apply_to_template` modifier, used within an `«artifact_content:...»` embed directive, enables an agent to render structured data using a **Mustache template**. This mechanism allows for the separation of data and presentation, enabling the agent to control the output format (for example, HTML, Markdown) without generating the formatting markup itself.

### The Templating Workflow

The process involves three distinct steps:

1.  **Template Creation**: Author a Mustache template file that defines the desired output structure.
2.  **Artifact Storage**: Persist the template file as an artifact in the agent's artifact storage using the `create_artifact` tool.
3.  **Template Rendering**: Utilize an `«artifact_content:...»` embed chain to process a data artifact and then apply the stored template to the result.

---

#### Step 1: Create a Mustache Template

Mustache is a logic-less template syntax. Templates are created as text files (for example, `user_table.html.mustache`) containing placeholders for data injection.

**Key Mustache Syntax**:
- **`{{variable}}`**: A variable placeholder. It is replaced with the corresponding value from the data context.
- **`{{#section}}...{{/section}}`**: A section tag. The enclosed block is rendered for each item in a list or if the section variable is a non-empty object or truthy value.
- **`{{^section}}...{{/section}}`**: An inverted section tag. The enclosed block is rendered only if the section variable is false, null, or an empty list.
- **`{{! comment }}`**: A comment tag. The content is ignored during rendering.

**Example: `user_table.html.mustache`**
This template generates an HTML table from a list of user objects.
```html
<h2>User List</h2>
{{#items}}
<table>
  <thead>
    <tr>
      <th>Name</th>
      <th>Status</th>
    </tr>
  </thead>
  <tbody>
    {{#.}}
    <tr>
      <td>{{name}}</td>
      <td>{{status}}</td>
    </tr>
    {{/.}}
  </tbody>
</table>
{{/items}}
{{^items}}
<p>No users found.</p>
{{/items}}
```

---

#### Step 2: Store the Template as an Artifact

The template must be stored as an artifact to be accessible by the Gateway during the late-stage embed resolution process. This is accomplished using the `create_artifact` tool.

**Example Agent Interaction**:
> **User**: "Please create an HTML template to display a list of users."
> **Agent**: "Acknowledged. I will create the template artifact `user_table.html.mustache`."
> *(The agent then invokes the `create_artifact` tool with the specified filename and the HTML content from Step 1.)*

---

#### Step 3: Render the Template with an Embed

With the data and template artifacts stored, the agent can construct an `artifact_content` embed chain to perform the rendering.

- **Syntax**: `... >>> apply_to_template:template_filename[:version] >>> ...`
- **Data Context**: The data provided to the template engine is the output of the preceding modifier in the chain.
  - If the data is a **list**, it is automatically wrapped in a dictionary of the form `{'items': your_list}`. The template should use `{{#items}}` to iterate over this list.
  - If the data is a **dictionary**, it is used directly as the rendering context.
- **Output Format**: It is **mandatory** to terminate the chain with a `format:` step (for example, `format:text`) to specify the MIME type of the final rendered output.

**Complete Example**:
The following embed chain processes a JSON file and renders its content using the HTML template created in Step 1.

```
«artifact_content:user_data.json >>> jsonpath:$.users[*] >>> select_fields:name,status >>> apply_to_template:user_table.html.mustache >>> format:text»
```

**Execution Flow**:
1.  `artifact_content:user_data.json`: Loads the raw data from the `user_data.json` artifact.
2.  `jsonpath:$.users[*]`: Applies a JSONPath expression to extract the list of user objects.
3.  `select_fields:name,status`: Filters each object in the list to retain only the `name` and `status` fields.
4.  `apply_to_template:user_table.html.mustache`: Renders the resulting list of users using the specified Mustache template.

### Error Handling
- **Template Not Found**: If the specified template artifact does not exist, the embed resolves to `[Error: Template artifact '...' not found]`.
- **Rendering Error**: If the data structure is incompatible with the template's expectations, the embed resolves to `[Error: Error rendering template '...']`.