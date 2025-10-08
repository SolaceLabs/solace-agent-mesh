# SAM REST API Client

A Python client library for interacting with Solace Agent Mesh (SAM) REST API Gateway.

This library simplifies task submission and result retrieval by abstracting the underlying HTTP calls, including the polling mechanism for asynchronous tasks.

## Installation

```bash
pip install sam-rest-client
```

## Prerequisite

Ensure you have an instance of Solace Agent Mesh running with the [REST Gateway](https://solacelabs.github.io/solace-agent-mesh/docs/documentation/tutorials/rest-gateway) configured

## Usage

Here is a quick example of how to use the client to submit a task to an agent.

### Script

```python
import asyncio
from sam_rest_client import SAMRestClient, SAMTaskTimeoutError, SAMTaskFailedError

async def main():
    # Initialize the client with the gateway's base URL and an auth token
    client = SAMRestClient(
        base_url="http://localhost:8080",
        auth_token="your-bearer-token-here" # Required if your REST Gateway requires authentication; omit if authentication is disabled
    )

    try:
        print("Submitting task to 'OrchestratorAgent'...")
        # Use the modern, asynchronous API (default)
        final_result = await client.invoke(
            agent_name="OrchestratorAgent",
            prompt="Summarize the attached sales data.",
            files=[("sales.csv", open("sales.csv", "rb"))],
            timeout_seconds=120
        )

        print("\nTask Completed!")
        print("Agent Response:", final_result.get_text())

        artifacts = final_result.get_artifacts()
        if artifacts:
            print("\nGenerated Artifacts:")
            for artifact in artifacts:
                print(f"  - Artifact: {artifact.name} ({artifact.mime_type}, {artifact.size} bytes)")
                # The client has a helper to download the latest version of the artifact
                await artifact.save_to_disk(".")
                print(f"    Saved latest version of {artifact.name} to current directory.")

            # To download a specific version, use the get_content() method:
            # first_artifact = artifacts[0]
            # content_of_version_1 = await first_artifact.get_content(version=1)

    except SAMTaskTimeoutError:
        print("The task timed out.")
    except SAMTaskFailedError as e:
        print(f"The agent reported an error: {e.error_details}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
```

### Using the CLI

When you install the sam-rest-client, you also have access to a CLI command via `sam-rest-cli`. To learn more about it run the following

```
sam-rest-cli -h
```

For example
```
sam-rest-cli --url http://localhost:8080 --agent OrchestratorAgent --prompt "Give me a list of all the agents in the system"
```

### Legacy Synchronous Mode

To use the deprecated synchronous v1 API, specify `mode='sync'`:

```python
# ... inside main async function ...
legacy_result = await client.invoke(
    agent_name="LegacyAgent",
    prompt="A quick task.",
    mode='sync'
)
print("Legacy API Response:", legacy_result.get_text())
```
