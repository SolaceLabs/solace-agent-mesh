# Web Tools Declarative Tests

This directory contains declarative YAML test cases for web-related tools, particularly the `web_request` tool.

## Test Structure

Each test case is defined in a YAML file with the following structure:
- `test_case_id`: Unique identifier for the test
- `description`: Human-readable description
- `tags`: List of tags for test categorization
- `gateway_input`: Input to send to the test gateway
- `llm_interactions`: Expected LLM request/response pairs
- `expected_gateway_output`: Expected final output from the gateway
- `expected_artifacts`: Expected artifacts created during the test

## Placeholder Support

Test files support dynamic placeholders that are substituted at runtime. This allows tests to reference services that may be running on different ports.

### Available Placeholders

- `{{STATIC_FILE_SERVER_URL}}` - URL of the TestStaticFileServer (e.g., `http://localhost:8089`)
- `{{LLM_SERVER_URL}}` - URL of the TestLLMServer (e.g., `http://localhost:8088`)

### Usage Example

```yaml
prompt:
  parts:
    - text: "Please fetch the JSON data from {{STATIC_FILE_SERVER_URL}}/sample.json"
```

At runtime, this will be replaced with the actual server URL:

```yaml
prompt:
  parts:
    - text: "Please fetch the JSON data from http://localhost:8089/sample.json"
```

### Benefits

- **Port Independence**: Tests work regardless of which port the server starts on
- **Parallel Testing**: Multiple test runs can use different ports without conflicts
- **CI/CD Friendly**: No hardcoded ports that might conflict in CI environments

## Test Data Files

The `TestStaticFileServer` serves files from `tests/sam-test-infrastructure/src/sam_test_infrastructure/test_data/web_content/`:

- `sample.json` - JSON test data
- `sample.html` - HTML document
- `sample.txt` - Plain text file
- `sample.xml` - XML document
- `sample.csv` - CSV data

See the [test data README](../../../sam-test-infrastructure/src/sam_test_infrastructure/test_data/web_content/README.md) for more details.

## Adding New Tests

1. Create a new YAML file in the appropriate subdirectory
2. Use placeholders for any URLs that reference test servers
3. Ensure expected content matches the actual test data files
4. Add appropriate tags for test categorization
