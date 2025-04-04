---
title: Create Custom Agents
sidebar_position: 40
---

# Creating Custom Agents

You can create custom agents for Solace Agent Mesh.

:::info[Learn about agents]
Before you create a custom agent, we recommend learn about agents. For more information, see [Agents](../concepts/agents.md).
:::

As an example, you will build an agent that can perform sentiment analysis and entity extraction on incoming requests.

## Setting Up the Environment

First, you need to [install the Solace Agent Mesh and Solace Agent Mesh (SAM) CLI](../getting-started/installation.md), and then you'll want to [create a new project](../getting-started/quick-start.md) or [create a new plugin](../concepts/plugins/create-plugin.md).

After you have your project set up, you can create an agent called `message-analyzer` using the following command:

```sh
solace-agent-mesh add agent message-analyzer
```

The following files are created in your project:

- `./configs/agents/message_analyzer.yaml`: Includes the agent configuration. Learn more about configs [here 🔗](../user-guide/solace-ai-connector.md).
- `./modules/agents/message_analyzer/message_analyzer_agent_component.py`: Includes the agent component.
- `./modules/agents/message_analyzer/actions/sample_action.py`: Includes a sample action, which you will replace with your own action.

## Planning the Agent

You are going to build an agent that will have two actions: one for sentiment analysis and another for entity extraction. Each action will require configuration.

:::tip[AI access]
Solace Agent Mesh provides access to [LLM Service](../user-guide/advanced/services/llm-service.md) and [Embedding Service](../user-guide/advanced/services/embedding-service.md) to agents.
:::

For the sentiment analysis action, you are going to use the LLM service to determine the sentiment of the message. Similarly, for the entity extraction action, you are going to use the LLM service to extract entities from the message. The types of entities will be configurable.

## Describing the Agent

You can start by updating the `./modules/agents/message_analyzer/message_analyzer_agent_component.py` file to describe the agent:

```python
# previous lines have been removed for brevity
from message_analyzer.actions.sample_action import SampleAction

info = copy.deepcopy(agent_info)
info["agent_name"] = "message_analyzer"
info["class_name"] = "MessageAnalyzerAgentComponent"
info["description"] = (
    "This agent can analyze messages for sentiment or extract entities."
)

class MessageAnalyzerAgentComponent(BaseAgentComponent):
    info = info
    # sample action
    actions = [SampleAction]
```

At this point, you have only updated the `description` field in the agent info. You will now update the actions after you have created them.

## Implementing the Actions

Next, copy the `sample_action.py` file to `sentiment_analysis_action.py` and `entity_extraction_action.py` files in the `./modules/agents/message_analyzer/actions` directory and update the contents as follows:

### Sentiment Analysis Action

Now, you update the action info in `./modules/agents/message_analyzer/actions/sentiment_analysis_action.py`:

```python
# previous lines have been removed for brevity
class SentimentAnalysisAction(Action):
    def __init__(self, **kwargs):
        super().__init__(
            {
                "name": "sentiment_analysis",
                "prompt_directive": "Analyze the sentiment of the message and return an analysis indicating whether it's positive, negative, or neutral.",
                "params": [
                    {
                        "name": "message",
                        "desc": "The message to analyze",
                        "type": "string",
                    }
                ],
                "required_scopes": ["message_analyzer:sentiment_analysis:execute"],
            },
            **kwargs,
        )

    def invoke(self, params, meta={}) -> ActionResponse:
        msg = params.get("message")
        log.debug("Analyzing the message: %s", msg)
        return self.analyze_message(msg)

    def analyze_message(self, message) -> ActionResponse:
        # TODO: Implement the action
```

That's all you need to configure the sentiment analysis action. You will now implement the action in the `analyze_message` method.

To access the [LLM Service](../user-guide/advanced/services/llm-service.md) for sentiment analysis, you must first access the agent. You can do this by using the `get_agent` method from the `Action` class.

```python
agent = self.get_agent()
```

Next, you will need to access the `do_llm_service_request` method to make a request to the LLM service. This function requires an array of messages in the format of the standard OpenAI interface.

You also need to determine a proper system prompt for the LLM service to understand the context of the task.

```python
SYSTEM_PROMPT = (
    "Analyze the sentiment of the message and return whether it's positive, negative, or neutral. "
    "You should only respond with a JSON value with 2 keys: 'sentiment' and 'confidence'. "
    "The sentiment should be one of 'positive', 'negative', or 'neutral'. "
    "The confidence should be a float value between 0 and 1."
)

user_msg = f"<message>{message}</message>"

message = [
    {
        "role": "system",
        "content": SYSTEM_PROMPT,
    },
    {
        "role": "user",
        "content": user_msg,
    },
]

agent.do_llm_service_request(message)
```

:::note
`do_llm_service_request` will take some time as the output needs to be generated by the LLM. The speed and delay vary based on the LLM model and the input message.
:::

:::info
In this example, you will not be using the Embedding service, but you can use it as follows:

```python
agent = self.get_agent()
strings = ["hello", "world"]
vectors = agent.do_embedding_service_request(strings)
```

:::

Now, get the content from the LLM Service response and parse it to JSON.

```python
try:
    response = agent.do_llm_service_request(message)
    content = response.get("content")
    analysis = json.loads(content)
    log.debug("Sentiment: %s, Confidence: %s", analysis["sentiment"], analysis["confidence"])
    return ActionResponse(message=content) # Message should be of type string, converting to JSON was just an example
except Exception as e:
    log.error("Error in sentiment analysis: %s", e)
    return ActionResponse(message="error: Error in sentiment analysis")
```

Next, put it all together:

```python
# previous lines have been removed for brevity
import json

SYSTEM_PROMPT = (
    "Analyze the sentiment of the message and return whether it's positive, negative, or neutral. "
    "You should only respond with a JSON value with 2 keys: 'sentiment' and 'confidence'. "
    "The sentiment should be one of 'positive', 'negative', or 'neutral'. "
    "The confidence should be a float value between 0 and 1."
)

class SentimentAnalysisAction(Action):
    def __init__(self, **kwargs):
        super().__init__(
            {
                "name": "sentiment_analysis",
                "prompt_directive": "Analyze the sentiment of the message and return an analysis indicating whether it's positive, negative, or neutral.",
                "params": [
                    {
                        "name": "message",
                        "desc": "The message to analyze",
                        "type": "string",
                    }
                ],
                "required_scopes": ["message_analyzer:sentiment_analysis:execute"],
            },
            **kwargs,
        )

    def invoke(self, params, meta={}) -> ActionResponse:
        msg = params.get("message")
        log.debug("Analyzing the message: %s", msg)
        return self.analyze_message(msg)

    def analyze_message(self, message) -> ActionResponse:
        agent = self.get_agent()

        user_msg = f"<message>{message}</message>"

        message = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_msg,
            },
        ]

        try:
            response = agent.do_llm_service_request(message)
            content = response.get("content")
            analysis = json.loads(content)
            log.debug("Sentiment: %s, Confidence: %s", analysis["sentiment"], analysis["confidence"])
            return ActionResponse(message=content) # Message should be of type string, converting to JSON was just an example
        except Exception as e:
            log.error("Error in sentiment analysis: %s", e)
            return ActionResponse(message="error: Error in sentiment analysis")
```

### Entity Extraction Action

To be more flexible, you are going to allow the user to specify the types of entities they want to extract. Update the `./configs/agents/message_analyzer.yaml` file to include the entity types.

```yaml
# previous lines have been removed for brevity
      - component_name: action_request_processor
        component_base_path: .
         # path is completed at build time
        component_module: {{MODULE_DIRECTORY}}.agents.message_analyzer.message_analyzer_agent_component
        component_config:
          llm_service_topic: ${SOLACE_AGENT_MESH_NAMESPACE}solace-agent-mesh/v1/llm-service/request/general-good/
          embedding_service_topic: ${SOLACE_AGENT_MESH_NAMESPACE}solace-agent-mesh/v1/embedding-service/request/text/
          # ---- New Configuration ----
          entity_extraction_action:
            entity_types: ${ENTITY_TYPES}
          # ---- End of New Configuration ----
        broker_request_response:
          enabled: true
          broker_config: *broker_connection
          request_expiry_ms: 120000
          payload_encoding: utf-8
          payload_format: json
          response_topic_prefix: ${SOLACE_AGENT_MESH_NAMESPACE}solace-agent-mesh
          response_queue_prefix: ${SOLACE_AGENT_MESH_NAMESPACE}solace-agent-mesh
        component_input:
          source_expression: input.payload
# next lines have been removed for brevity
```

:::tip
If you are building a plugin and have a lot of configurations or objects that don't transfer to environment variables (like arrays), you can hard-code them and request the user to template your agent instead of directly using it. To learn more, check the [copy from agent, plugins](../concepts/plugins/use-plugins.md#copy-from-an-agent) page.
:::

Now, you update the `./modules/agents/message_analyzer/actions/entity_extraction_action.py` file:

```python
# previous lines have been removed for brevity
class EntityExtractionAction(Action):
    def __init__(self, **kwargs):
        super().__init__(
            {
                "name": "entity_extraction",
                "prompt_directive": "Extract entities from the message and return the entities as a JSON file",
                "params": [
                    {
                        "name": "message",
                        "desc": "The message to extract entities from",
                        "type": "string",
                    }
                ],
                "required_scopes": ["message_analyzer:entity_extraction:execute"],
            },
            **kwargs,
        )

        # Loading the entity types from the yaml config file
        entity_extraction_config = self.get_config("entity_extraction_action", {})
        self.entity_types = entity_extraction_config.get("entity_types")

        if not self.entity_types:
            # This will crash the agent if the entity types are not found
            raise ValueError("Entity types not found in the configuration")

    def invoke(self, params, meta={}) -> ActionResponse:
        msg = params.get("message")
        log.debug("Extracting entities from the message: %s", msg)
        return self.extract_entities(msg)

    def extract_entities(self, message) -> ActionResponse:
        # TODO: Implement the action
```

Similar to the sentiment analysis action, you will need to access the LLM service to extract entities from the message. You will then use the same `do_llm_service_request` method to make a request to the LLM service.

```python
SYSTEM_PROMPT = (
    "Extract entities from the message and return the entities as a JSON file. "
    "You should only respond with a JSON value with the extracted entities. "
    f"Look for the following entity types: {self.entity_types}"
)

user_msg = f"<message>{message}</message>"

message = [
    {
        "role": "system",
        "content": SYSTEM_PROMPT,
    },
    {
        "role": "user",
        "content": user_msg,
    },
]

content = agent.do_llm_service_request(message).get("content")
```

This time, you are going to return the response as a JSON file. So you are **going to use the [File service](../user-guide/advanced/services/file-service.md)** to first upload your JSON file, and then return the metadata of the file.

```python
from solace_agent_mesh.services.file_service import FileService
import random

file_service = FileService()
file_name = "extracted_entities" + str(random.randint(100000, 999999)) + ".json"
file_meta = file_service.upload_from_buffer(
    content.encode("utf-8"), # convert the string to bytes
    file_name,
    session_id, # Session ID is provided through the meta parameter
    data_source="Message Analyzer Agent - Entity Extraction Action",
)
return ActionResponse(files=[file_meta])
```

Now, you put it all together:

```python
# previous lines have been removed for brevity
from solace_agent_mesh.services.file_service import FileService
import random

class EntityExtractionAction(Action):
    def __init__(self, **kwargs):
        super().__init__(
            {
                "name": "entity_extraction",
                "prompt_directive": "Extract entities from the message and return the entities as a JSON file",
                "params": [
                    {
                        "name": "message",
                        "desc": "The message to extract entities from",
                        "type": "string",
                    }
                ],
                "required_scopes": ["message_analyzer:entity_extraction:execute"],
            },
            **kwargs,
        )

        # Loading the entity types from the yaml config file
        entity_extraction_config = self.get_config("entity_extraction_action", {})
        self.entity_types = entity_extraction_config.get("entity_types")

        if not self.entity_types:
            # This will crash the agent if the entity types are not found
            raise ValueError("Entity types not found in the configuration")

    def invoke(self, params, meta={}) -> ActionResponse:
        msg = params.get("message")
        log.debug("Extracting entities from the message: %s", msg)

        return self.extract_entities(msg, meta.get("session_id"))

    def extract_entities(self, message, session_id) -> ActionResponse:
        system_prompt = (
            "Extract entities from the message and return the entities as a JSON file. "
            "You should only respond with a JSON value with the extracted entities. "
            f"Look for the following entity types: {self.entity_types}"
        )

        agent = self.get_agent()
        user_msg = f"<message>{message}</message>"

        message = [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_msg,
            },
        ]

        try:
            content = agent.do_llm_service_request(message).get("content")

            file_service = FileService()
            file_name = "extracted_entities" + str(random.randint(100000, 999999)) + ".json"
            file_meta = file_service.upload_from_buffer(
                content.encode("utf-8"), # convert the string to bytes
                file_name,
                session_id, # Session ID is provided through the meta parameter
                data_source="Message Analyzer Agent - Entity Extraction Action",
            )
            return ActionResponse(files=[file_meta])
        except Exception as e:
            log.error("Error in entity extraction: %s", e)
            return ActionResponse(message="error: Error in entity extraction")
```

## Updating the Agent

Now that you have the actions implemented, you must update the agent to include these actions. To accomplish this, update the `./modules/agents/message_analyzer/message_analyzer_agent_component.py` file:

```python
# previous lines have been removed for brevity
from message_analyzer.actions.sentiment_analysis_action import SentimentAnalysisAction
from message_analyzer.actions.entity_extraction_action import EntityExtractionAction

info = copy.deepcopy(agent_info)
info["agent_name"] = "message_analyzer"
info["class_name"] = "MessageAnalyzerAgentComponent"
info["description"] = (
    "This agent can analyze messages for sentiment or extract entities."
)

class MessageAnalyzerAgentComponent(BaseAgentComponent):
    info = info
    actions = [SentimentAnalysisAction, EntityExtractionAction]
```

## Building and Running the Agent

Before you build and run the agent, update the environment variables to include the entity types. You can do this by updating the `env_file` from `solace-agent-mesh.yaml`:

```sh
ENTITY_TYPES="Name, Company, Query"
```

Now, you can build and run the agent:

```sh
sam run -be
```

For more information, see [Solace Agent Mesh CLI](../concepts/cli.md).

## Testing the Agent

You can try the following two prompts to test your new actions:

**Sentiment Analysis:**

> Analyze the sentiment of this message: I love the new product, it is amazing. But I just wish it was a bit cheaper.

**Entity Extraction:**

> Extract entities from the message: Hi, This John from ABC Company. We are looking to buy 100 units of your product. Can you provide a quote?

You can test these prompts through any gateway. Here, you will use a REST endpoint.

```sh
curl --location 'http://localhost:5050/api/v1/request' \
--header 'Authorization: Bearer None' \
--form 'prompt="Analyze the sentiment of this message: I love the new product, it is amazing. But I just wish it was a bit cheaper."' \
--form 'stream="false"'
```

Action Response (As text):

```
{
  "sentiment": "positive",
  "confidence": 0.7
}
```

System Output:

```
Based on the sentiment analysis of the message "I love the new product, it is amazing. But I just wish it was a bit cheaper.", here's the interpretation:

The overall sentiment of the message is positive, with a confidence score of 0.7 out of 1.0. This indicates a generally favorable opinion, but with some nuance.

Breaking it down:

1. Positive aspects:
   - The user expresses strong positive emotions with phrases like "I love" and "it is amazing."
   - These statements show a high level of satisfaction with the product's features or performance.

2. Slight reservation:
   - The phrase "But I just wish it was a bit cheaper" introduces a minor negative element.
   - This reservation about the price slightly tempers the overall positivity, which explains why the confidence score is 0.7 rather than higher.

In conclusion, the sentiment is predominantly positive, reflecting enthusiasm for the product. However, there's a small concern about the price, which adds a touch of complexity to the overall positive sentiment. This balanced view is typical in product feedback, where users often weigh multiple factors in their assessment.
```

```sh
curl --location 'http://localhost:5050/api/v1/request' \
--header 'Authorization: Bearer None' \
--form 'prompt="Extract entities from the message: Hi, This John from ABC Company. We are looking to buy 100 units of your product. Can you provide a quote?"' \
--form 'stream="false"'
```

Action Output (As a file):

```json
{
  "Name": "John",
  "Company": "ABC Company",
  "Query": "provide a quote for 100 units of your product"
}
```

System Output:

```
I have extracted the entities from the given message. Here are the results:

1. Name: John
2. Company: ABC Company
3. Query: provide a quote for 100 units of your product

These entities represent the key information extracted from the message, including the person's name, their company, and the main query or request they're making.
```

:::tip
You can modify the formatting and verbosity of the system output in the gateway configuration. For more information, see [gateway](../concepts/gateways.md).
:::
