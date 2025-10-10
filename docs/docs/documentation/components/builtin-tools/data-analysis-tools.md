---
title: Data Analysis Tools
sidebar_position: 20
---

# Data Analysis Tools

Agent Mesh includes a suite of optional built-in tools that enable agents to perform data analysis tasks directly on artifacts. These tools provide functionality for SQL querying, JQ transformations, and Plotly chart generation.

## Setup and Configuration

Enable the data analysis tool group in the agent's `app_config.yml` file.

```yaml
# In your agent's app_config:
tools:
  - tool_type: builtin-group
    group_name: "data_analysis"

# Optional: Configure tool behavior
data_tools_config:
  sqlite_memory_threshold_mb: 100
  max_result_preview_rows: 50
  max_result_preview_bytes: 4096
```

## Available Tools

### `query_data_with_sql`
:::info[Enterprise Only]
This feature is available in the Enterprise Edition only.
:::
Executes a SQL query against data stored in a CSV or SQLite artifact.

- **Parameters**:
    - `input_filename` (str): The filename of the input artifact (for example, `'data.csv'`, `'mydatabase.sqlite'`). Supports versioning (for example, `'data.csv:2'`).
    - `sql_query` (str): The SQL query string to execute.
    - `output_format` (str, optional): The desired format for the output artifact (`'csv'` or `'json'`). Defaults to `'csv'`.
- **Behavior**:
    - **For CSV Input**: The tool loads the CSV data into a temporary in-memory SQLite database table named `data` and executes the query against it.
    - **For SQLite Input**: The tool connects directly to the specified SQLite database artifact in **read-only mode**.
- **Returns**: A dictionary containing the execution status, a preview of the query result, and the `output_filename` where the full result set is stored.

---

### `create_sqlite_db`
:::info[Enterprise Only]
This feature is available in the Enterprise Edition only.
:::
Converts a CSV or JSON artifact into a persistent SQLite database artifact. This is the recommended approach for executing multiple queries on the same dataset, as it avoids repeated parsing of the source file.

- **Parameters**:
    - `input_filename` (str): The filename of the input CSV or JSON artifact.
    - `output_db_filename` (str): The desired filename for the output SQLite database artifact (for example, `'queryable_dataset.sqlite'`).
    - `table_name` (str, optional): The name of the table to be created within the SQLite database. Defaults to `'data'`.
- **Returns**: A dictionary confirming the successful creation of the database artifact and providing its `output_filename`.

---

### `transform_data_with_jq`
:::info[Enterprise Only]
This feature is available in the Enterprise Edition only.
:::
Applies a JQ expression to transform data from a JSON, YAML, or CSV artifact.

- **Parameters**:
    - `input_filename` (str): The filename of the input artifact.
    - `jq_expression` (str): The JQ filter or transformation expression string (for example, `'.users[] | {name, id}'`).
- **Returns**: A dictionary containing the execution status, a preview of the transformed data, and the `output_filename` where the full JSON result is stored.

---

### `create_chart_from_plotly_config`
Generates a static chart image (for example, PNG, JPG, SVG) from a Plotly configuration provided as a string.

- **Parameters**:
    - `config_content` (str): A JSON or YAML formatted string representing the Plotly `figure` dictionary.
    - `config_format` (str): Specifies whether `config_content` is `'json'` or `'yaml'`.
    - `output_filename` (str): The desired filename for the output image artifact (for example, `'sales_chart.png'`).
    - `output_format` (str, optional): The desired image format (`'png'`, `'jpeg'`, `'svg'`, etc.). Defaults to `'png'`.
- **Returns**: A dictionary confirming the chart's creation and providing its `output_filename`.

## Example Workflow: Querying a Large CSV

The following workflow demonstrates an efficient method for analyzing a large CSV file:

1.  **User Request**: "I need to run several queries on `large_data.csv`."
2.  **Agent Strategy**: The agent determines that converting the CSV to a SQLite database is more performant for subsequent queries.
3.  **Agent Call 1**: The agent calls `create_sqlite_db` to convert `large_data.csv` into a new artifact, `queryable_data.sqlite`.
4.  **Agent Response**: "The data has been prepared for querying. What is your first question?"
5.  **User Request**: "Find all records where the category is 'Sales'."
6.  **Agent Call 2**: The agent calls `query_data_with_sql`, targeting the **`queryable_data.sqlite`** artifact.
7.  **Agent Response**: The agent provides the results of the query.
8.  **User Request**: "Now, find the average amount for the 'Marketing' category."
9.  **Agent Call 3**: The agent calls `query_data_with_sql` again on the **same `queryable_data.sqlite` artifact**, avoiding the overhead of reprocessing the original CSV file.

## Technical Considerations

### Result Handling
- **Previews**: For `query_data_with_sql` and `transform_data_with_jq`, the tools return a truncated preview of the result directly to the LLM for immediate context.
- **Full Results**: The complete, untruncated result sets are always saved as new artifacts. The LLM is provided with the filename and version of these artifacts.
- **Accessing Full Results**: To utilize the full results, the agent can employ file management tools (`load_artifact`) or [Dynamic Embeds](embeds.md) (`«artifact_content:...»`).

### Security
- **SQL Execution**: Queries against existing SQLite artifacts are performed in **read-only mode** to prevent data modification. Queries against temporary databases generated from CSVs are isolated.
- **JQ Execution**: JQ expressions are executed within a sandboxed Python library, not via shell execution.
- **Resource Usage**: Complex queries or transformations can be resource-intensive. Monitor performance and resource consumption accordingly.
