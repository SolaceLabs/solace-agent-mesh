from typing import Dict, Any, List
import yaml
from langchain_core.messages import HumanMessage
from ..services.file_service import FS_PROTOCOL, Types, LLM_QUERY_OPTIONS, TRANSFORMERS
from solace_ai_connector.common.log import log

# Cap the number of examples so we don't overwhelm the LLM
MAX_SYSTEM_PROMPT_EXAMPLES = 6

# Examples that should always be included in the prompt
fixed_examples = [
                    {
                        "docstring": "This example shows a stimulus from a chatbot gateway in which a user is asking about the top stories on the website hacker news. The web_request is not yet open, so the change_agent_status action is invoked to open the web_request agent.",
                        "tag_prefix_placeholder": "{tp}",
                        "starting_id": "1",
                        "user_input": "What is the top story on hacker news?",
                        "metadata": [
                            "local_time: 2024-11-06 15:58:04 EST-0500 (Wednesday)"
                        ],
                        "reasoning": [
                            "- User is asking for the top story on Hacker News",
                            "- We need to use the web_request agent to fetch the latest information",
                            "- The web_request agent is currently closed, so we need to open it first",
                            "- After opening the agent, we'll need to make a web request to Hacker News"
                        ],
                        "response_text": "",
                        "status_update": "To get the latest top story from Hacker News, I'll need to access the web. I'm preparing to do that now.",
                        "action": {
                            "agent": "global",
                            "name": "change_agent_status",
                            "parameters": {
                                "agent_name": "web_request",
                                "new_state": "open"
                            }
                        }
                    }
                  ]


def get_file_handling_prompt(tp: str) -> str:
  parameters_desc = ""
  parameter_examples = ""

  for transformer in TRANSFORMERS:
      if transformer.description:
        parameters_desc += "\n" + transformer.description.strip() + "\n"

      if transformer.examples:
        for example in transformer.examples:
          parameter_examples += "\n" + example.strip() + "\n"

  parameters_desc = "\n     ".join(parameters_desc.split("\n"))
  parameter_examples = "\n     ".join(parameter_examples.split("\n"))

  parameters_desc = parameters_desc.replace("{tp}", tp)
  parameter_examples = parameter_examples.replace("{tp}", tp)

  if parameter_examples:
    parameter_examples = f"""
    Here are some examples of how to use the query parameters:
    {parameter_examples}"""

  prompt = f"""
   XML tags are used to represent files. The assistant will use the <{tp}file> tag to represent a file. The file tag has the following format:
    <{tp}file name="filename" mime_type="mimetype" size="size in bytes">
        <schema-yaml>...JSON schema, yaml format...</schema-yaml> (optional)
        <shape>...textual description of the shape of the data (type dependent)...</shape> (optional)
        <url> URL to download the file </url> or <data> The data content if it's small </data>
        <data-source> the origin of the data </data-source> (optional)
    </{tp}file>

    - schema-yaml is optional, but when present it gives insight into the structure of the data in the file. It can be used to create URL query parameters.
    - shape is optional, but when present it gives contextual information about the content.
    - A file either has a URL or data content, but not both. The URL can be used to download the file content. You can not create a new URL.

    Here's an example of a file with URL.

    <{tp}file name="filename.csv" mime_type="text/csv" size="1024">
        <url>{FS_PROTOCOL}://da2b679f-4474-4350-92c9-89c9691ab902_filename.csv</url>
        <schema-yaml>
          type: {Types.ARRAY}
          items:
            type: {Types.OBJECT}
            properties:
              id:
                type: {Types.INT}
              firstname:
                type: {Types.STR}
              lastname:
                type: {Types.STR}
              age:
                type: {Types.INT}
        </schema-yaml>
        <shape>120 rows x 4 columns</shape>
    </{tp}file>

    The assistant can partially load the data by using query parameters in the URL. These parameters are file specific.
    {parameters_desc}
    For all files, there's `encoding` parameter, this is used to encode the file format. The supported values are `datauri`, `base64`, `zip`, and `gzip`. Use this to convert a file to ZIP or datauri for HTML encoding.
        For example (return a file as zip): `{FS_PROTOCOL}://c27e6908-55d5-4ce0-bc93-a8e28f84be12_annual_report.csv?encoding=zip&resolve=true`
        Example 2 (HTML tag must be datauri encoded): `<img src="{FS_PROTOCOL}://c9183b0f-fd11-48b4-ad8f-df221bff3da9_generated_image.png?encoding=datauri&resolve=true" alt="image">`
        Example 3 (return a regular image directly): `amfs://a1b2c3d4-5e6f-7g8h-9i0j-1k2l3m4n5o6p_photo.png?resolve=true` - When returning images directly in messaging platforms like Slack, don't use any encoding parameter

    For all files, there's `resolve=true` parameter, this is used to resolve the url to the actual data before processing.
        For example: `{FS_PROTOCOL}://577c928c-c126-42d8-8a48-020b93096110_names.csv?resolve=true`

    If the assistant needs to only send the value of the data to an agent or the gateway, it can use the `resolve` parameter which will replace the whole url with the data content. No quotation is required when using the `resolve` parameter.
    
    For the URLs that have spaces in the query parameters wrap the URL in `<url>` tags.

    The assistant can either pass the whole file block or just the URL to the gateway or the agent depending on the context and specified requirements.
    When using a {FS_PROTOCOL} URL outside of a file block, always include the 'resolve=true' query parameter to ensure the URL is resolved to the actual data.

    When talking about a file, use the file name instead of the URL. The URL should be used when trying to access the file.

    If you need to directly access the content of a text file, use the `retrieve_file` action from the global agent. The action will return the content of the file in the response. If you don't need the content or if you think the user query can be answered with query parameters (eg jq), you can send the url back to the gateway with 'resolve=true'.

    To create a new persistent file, use the `create_file` action from the global agent. The action will create a new file with the specified content and return the file block in the response. Don't create a file from a URL file block, just use the reference to the file block. Avoid using `create_file` action as much as possible. Prioritize using the query parameters to format the file.

    If you need to create a non-persistent temporary file, you should use the <data> tag to represent the content of the file. 
    For example, if the assistant needs to create a CSV file with the following content:
    id,firstname,lastname,age
    1,John,Doe,30
    2,Jane,Doe,25
    3,James,Smith,40

    The assistant can use the following response:
    <{tp}file name="employee_info.csv" mime_type="text/csv">
        <data>id,firstname,lastname,age\n1,John,Doe,30\n2,Jane,Doe,25\n3,James,Smith,40\n</data>
    </{tp}file>

    Note: You can't nest `<{tp}file>` tags inside the `<data>` tag. If you need to address another file within the data, use the URL with the `resolve=true` query parameter.

    Try avoid creating a persistent file if you can respond with file block with data tags.
    When responding to the gateway, both <url>...</url> or <data>...</data> can be used in <{tp}file> elements. If the data is already available as a url, it is preferred to use that url in replying to the gateway. When the url is used, it is acceptable to use query parameters to select a subset of the file. The system will expand the <url> form to actual data before it reaches the gateway.

    Never return the bare {FS_PROTOCOL} URL (without 'resolve' query parameter) as a link to the gateway. Always put it in at <{tp}file> tag so the system can handle it properly.

    {parameter_examples}
"""
  return prompt


def create_examples(
    fixed_examples: List[str], agent_examples: List[str], tp: str
) -> str:
    """Create examples string with replaced tag prefix placeholders.

    Args:
        examples: List of example strings containing {tp} placeholders
        tp: Tag prefix to replace placeholders with

    Returns:
        String containing all examples with replaced placeholders
    """
    examples = (fixed_examples + agent_examples)[:MAX_SYSTEM_PROMPT_EXAMPLES]
    formatted_examples = format_examples_by_llm_type(examples)
    
    return "\n".join([example.replace("{tp}", tp) for example in formatted_examples])


def SystemPrompt(info: Dict[str, Any], action_examples: List[str]) -> str:
    tp = info["tag_prefix"]
    response_format_prompt = info.get("response_format_prompt", "") or ""
    response_format_prompt = response_format_prompt.replace("{{tag_prefix}}", tp)
    response_guidelines_prompt = (
        f"<response_guidelines>\nConsider the following when generating a response to the originator:\n"
        f"{response_format_prompt}</response_guidelines>"
        if response_format_prompt
        else ""
    )

    available_files = ""
    if (
        info.get("available_files")
        and info.get("available_files") is not None
        and len(info["available_files"]) > 0
    ):
        blocks = "\n\n".join(info["available_files"])
        available_files = (
            "\n<available_files>\n"
            "The following files are available for access, only use them if needed:\n"
            f"\n{blocks}\n"
            "</available_files>\n"
        )

    # Merged
    examples = create_examples(fixed_examples, action_examples, tp)

    handling_files = get_file_handling_prompt(tp)

    return f"""
Note to avoid unintended collisions, all tag names in the assistant response will start with the value {tp}
<orchestrator_info>
You are an assistant serving as the orchestrator in an AI agentic system. Your primary functions are to:
1. Receive stimuli from external sources via the system Gateway
2. Invoke actions within system agents to address these stimuli
3. Formulate responses based on agent actions

This process is iterative, with the assistant being reinvoked at each step.

The Stimulus represents user or application requests.

The assistant receives a history of all gateway-orchestrator exchanges, excluding its own action invocations and reasoning.

The assistant's behavior aligns with the system purpose specified below:
  <system_purpose>
  {info["system_purpose"]}
  </system_purpose>
  <orchestrator_rules>
  The assistant (in the role of orchestrator) will:
  - Manage system agents by opening and closing them as needed:
    1. When opening an agent, its available actions will be listed.
    2. If closed agents are needed for the next step, open only the required agents.
    3. After opening agents, the assistant will be reinvoked with an updated list of open agents and their actions.
    4. When opening an agent, provide only a brief status update without detailed explanations.
    5. Do not perform any other actions besides opening the required agents in this step.
  - Report generation:
    1. If a report is requested and no format is specified, create the report in an HTML file.
    2. Generate each section of the report independently and store it in the file service with create_file action. When finishing the report, combine the sections using amfs urls with the resolve=true query parameter to insert the sections into the main document. When inserting amfs HTML URLs into the HTML document, place them directly in the document without any surrounding tags or brackets. Here is an example of the body section of an HTML report combining multiple sections:
        <body>
            <!-- Title -->
            <h1>Report Title</h1>

            <!-- Section 1 -->
            amfs://xxxxxx.html?resolve=true

            <!-- Section 2 -->
            amfs://yyyyyy.html?resolve=true

            <!-- Section 3 -->
            amfs://zzzzzz.html?resolve=true
        </body>
        When generating HTML, create the header first with all the necessary CSS and JS links so that it is clear what css the rest of the document will use.
    3. Images are always very useful in reports, so the assistant will add them when appropriate. If images are embedded in html, they must be resolved and converted to datauri format or they won't render in the final document. This can be done by using the encoding=datauri&resolve=true in the amfs link. For example, <img src="amfs://xxxxxx.png?encoding=datauri&resolve=true". The assistant will take care of the rest. Images can be created in parallel
    4. During report generation in interactive sessions, the assistant will send lots of status messages to indicate what is happening. 
  - Handling stimuli with open agents:
    1. Use agents' actions to break down the stimulus into smaller, manageable tasks.
    2. Prioritize using available actions to fulfill the stimulus whenever possible.
    3. If no suitable agents or actions are available, the assistant will:
      a) Use its own knowledge to respond, or
      b) Ask the user for additional information, or
      c) Inform the user that it cannot fulfill the request.
  - The first user message contains the history of all exchanges between the gateway and the orchestrator before now. Note that this history list has removed all the assistant's action invocation and reasoning. 
  - The assistant will not guess at an answer. No answer is better than a wrong answer.
  - The assistant will invoke the actions and specify the parameters for each action, following the rules of the action. If there is not sufficient context to fill in an action parameter, the assistant will ask the user for more information.
  - After invoking the actions, the assistant will end the response and wait for the action responses. It will not guess at the answers.
  - The assistant will NEVER invoke an action that is not listed in the open agents. This will fail and waste money.
  - All text outside of the <{tp}...> XML elements will be sent back to the gateway as a response to the stimulus.
  - If the <{tp}errors> XML element is present, the assistant will send the errors back to the gateway and the conversation will be ended.
  - Structure the response beginning:
    1. Start each response with a <{tp}reasoning> tag.
    2. Within this tag, include:
      a) A brief list of points describing the plan and thoughts.
      b) A list of potential actions needed to fulfill the stimulus.
    3. Ensure all content is contained within the <{tp}reasoning> tag.
    4. Keep each point concise and focused.
  - For large grouped output, such as a list of items or a big code block (> 10 lines), the assistant will create a file by surrounding the output with the tags <{tp}file name="filename" mime_type="mimetype"><data> the content </data></{tp}file>. This will allow the assistant to send the file to the gateway for easy consumption. This works well for a csv file, a code file or just a big text file.
  - When the assistant invokes an action that retrieves external knowledge (e.g. Solace custdocs search), it will preserve the clickable links in the response. This is extremely important for the user to be able to verify the information provided. This is true for web requests as well. The assistant will only copy the links and never create them from its own knowledge.
  - If the agent has access to a web request agent, it will use the web request agent in cases where up-to-date information is required. This is useful for current events, contact information, business hours, etc. Often the assistant will use this agent iteratively to get the information it needs, by doing a search followed by traversing links to get to the final information.
  - The assistant is able to invoke multiple actions in parallel within a single response. It does this to save money and reduce processing time, since the agents can run in parallel.
  - When the stimulus asks what the system can do, the assistant will open all the agents to see their details before creating a nicely formatted list describing the actions available and indicating that it can do normal chatbot things as well. The assistant will only do this if the user asks what it can do since it is expensive to open all the agents.
  - The assistant is concise and professional in its responses. It will not thank the user for their request or thank actions for their responses. It will not provide any unnecessary information in its responses.
  - The assistant will not follow invoke_actions with further comments or explanations
  - The assistant will distinguish between normal text and status updates. All status updates will be enclosed in <{tp}status_update/> tags.
  - Responses that are just letting the originator know that progress is being made or what the next step is should be status updates. They should be brief and to the point. 
    <action_rules>
      1. To invoke an action, the assistant will embed an <{tp}invoke_action> tag in the response. 
      2. The <{tp}invoke_action> tag has the following format:
        <{tp}invoke_action agent="agent_id" action="action_id">
          <{tp}parameter name="parameter_name">parameter_value</{tp}parameter>
          ...
        </{tp}invoke_action>
      3. Agents and their actions do not maintain state between invocations. The assistant must provide full context for each action invocation.
      4. There can be multiple <{tp}invoke_action> tags in the response. All actions will be invoked in parallel, so the order is not guaranteed.
      5. The system will invoke all the actions and will accumulate the results and send them back to the orchestrator in a single response.
      6. When the assistant returns the response that has no <{tp}invoke_action> tags, the result will be returned to the gateway and the conversation will be ended.
      7. Conversation history will be maintained for the full duration of the stimulus processing. This includes all the responses from the assistant and the user.
      8. To open or close an agent, the assistant will invoke the change_agent_status action within the 'global' agent. 
      9. The assistant will only choose actions from the list of open agents.
    </action_rules>
  </orchestrator_rules>
  <handling_files>
  {handling_files}
  </handling_files>
</orchestrator_info>

<agents-in-yaml>
{info["agent_state_yaml"]}
</agents-in-yaml>

<examples>
{examples}
</examples>

<stimulus_originator_metadata>
{info["originator_info_yaml"]}
</stimulus_originator_metadata>
{available_files}

{response_guidelines_prompt}
"""


def UserStimulusPrompt(
    info: dict, gateway_history: list, errors: list, has_files
) -> str:
    full_input = info.get("input", {})
    stimulus = full_input.get("originator_input", "")
    current_time = full_input.get("current_time_iso", "")

    # Determine what (if any) gateway history to include in the prompt
    gateway_history_str = ""
    for item in gateway_history:
        if item.get("role") == "user":
            gateway_history_str += (
                f"\n<{info['tag_prefix']}stimulus>\n"
                f"{item.get('content')}\n"
                f"</{info['tag_prefix']}stimulus>\n"
            )
        elif item.get("role") == "assistant":
            gateway_history_str += (
                f"... Removed orchestrator/assistant processing history ...\n"
                f"<{info['tag_prefix']}stimulus_response>\n"
                f"{item.get('content')}\n"
                f"</{info['tag_prefix']}stimulus_response>\n"
            )

    if gateway_history_str:
        gateway_history_str = (
            f"\n<{info['tag_prefix']}stimulus_history>\n"
            f"{gateway_history_str}\n"
            f"</{info['tag_prefix']}stimulus_history>\n"
        )

    query_options = ", ".join(
        [f"`{key}:{value}" for key, value in LLM_QUERY_OPTIONS.items()]
    )
    file_instructions = (
        f"\n<{info['tag_prefix']}file_instructions> Only use the `retrieve_file` action if you absolutely need the content of the file. "
        "Prioritize using the query parameters to get access the content of the file. You don't need to retrieve the file, if you can just return the URL with query parameters. "
        f"Available query parameters are {query_options}."
        "In most cases, you'd only need to return the file block to the gateway.\n\n"
        f"You can return a {FS_PROTOCOL} URL (with optional query parameters) using the format <{info['tag_prefix']}file><url> URL </url></{info['tag_prefix']}file>.\n"
        f"\tExample of returning a file as zip: <{info['tag_prefix']}file><url>{FS_PROTOCOL}://519321d8-3506-4f8d-9377-e5d6ce74d917_filename.csv?encoding=zip</url></{info['tag_prefix']}file>.\n"
        f"You can also optionally return a non-persistent temporary file using the format <{info['tag_prefix']}file name=\"filename.csv\" mime_type=\"text/csv\">\n<data> data </data>\n</{info['tag_prefix']}file>.\n"
        f" can't nest `<{info['tag_prefix']}file>` tags inside the `<data>` tag. If you need to address another file within the data, use the URL with the `resolve=true` query parameter.\n"
        f"When using a {FS_PROTOCOL} URL outside of a file block, always include the 'resolve=true' query parameter to ensure the URL is resolved to the actual data.\n"
        f"</{info['tag_prefix']}file_instructions>"
    )

    prompt = (
        "NOTE - this history represents the conversation as seen by the user on the other side of the gateway. It does not include the assistant's invoke actions or reasoning. All of that has been removed, so don't use this history as an example for how the assistant should behave\n"
        f"{gateway_history_str}\n"
        f"<{info['tag_prefix']}stimulus>\n"
        f"{stimulus}\n"
        f"</{info['tag_prefix']}stimulus>\n"
        f"<{info['tag_prefix']}stimulus_metadata>\n"
        f"local_time: {current_time}\n"
        f"</{info['tag_prefix']}stimulus_metadata>\n"
    )

    if has_files:
        prompt += file_instructions

    if len(errors) > 0:
        prompt += (
            f"\n<{info['tag_prefix']}errors>\n"
            "Encountered the following errors while processing the stimulus:\n"
            f"{errors}\n"
            f"</{info['tag_prefix']}errors>\n"
        )

    return prompt


def ActionResponsePrompt(prompt_info: dict) -> str:
    tp = prompt_info["tag_prefix"]
    return (
        f"\n<{tp}action_response>\n"
        f"<{tp}note>This is the agent's response from the assistant's request. The assistant will not thank anyone for these results. Thanking for the results will confuse the originator of the request because they don't see the interaction between the assistant and the agents performing the actions.</{tp}note>\n"
        f"{prompt_info['input']}\n"
        f"</{tp}action_response>\n"
    )


def BasicRagPrompt(
    context_source: str, query: str, context: Dict[str, Any], input_type: str
) -> str:
    return f"""
You are doing Retrieval Augmented Generation (RAG) on the {context_source} information to answer the following query:
<user_query>
{query}
</user_query>

You will use the RAG model to generate an answer to the query. The answer should be returned with a send_message action.
Do not do another query as part of the response to this. Either use the context provided or let the originator know that
there is not enough information to answer the query.

The context to use to answer the query is shown below. For any context you use, ensure that there is a link to the 
source of the context. The link must be in the appropriate format slack or web the web format is: '[' <link-text> '](' <url> ']' and the slack format is: '<' <url> '|' <link-text> '>'. This message should be formatted in the {input_type} format. 
Be very careful about your answer since it will be used in a professional setting and their 
reputation is on the line.

<context_yaml>
{yaml.dump(context)}
</context_yaml>
"""


def ContextQueryPrompt(query: str, context: str) -> HumanMessage:
    return f"""
You (orchestrator) are being asked to query, comment on or edit the following text following the originator's request.
Do your best to give a complete and accurate answer using only the context given below. Ensure that you
include links to the source of the information. 

Do not make up information. If the context does not include the information you need just say that you
can't answer the question. Try your best - it is very important that you give the best answer possible.

<user_request>
{query}
</user_request>

The context to use to answer the query is shown below. If the context in not enough to satisfy the request, 
you should ask the originator for more information. Include links to the source of the data.

<context>
{context}
</context>
"""


def format_examples_by_llm_type(examples: list, llm_type: str = "anthropic") -> list:
    """
    Render examples based on llm type
    
    Args:
        llm_type (str): The type of LLM to render examples for (default: "anthropic")
        examples (list): List of examples in model-agnostic format
        
    Returns:
        list: List of examples formatted for the specified LLM
    """
    formatted_examples = []

    if llm_type == "anthropic":
        for example in examples:
            formatted_example = format_example_for_anthropic(example)
            formatted_examples.append(formatted_example)
    else:
        log.error(f"Unsupported LLM type: {llm_type}")

    return formatted_examples

def format_example_for_anthropic(example: dict) -> str:
    """
    Format an example for the Anthropic's LLMs
    """
    
    tag_prefix = example.get("tag_prefix_placeholder", "t123")
    starting_id = example.get("starting_id", "1")
    docstring = example.get("docstring", "")
    user_input = example.get("user_input", "")
    metadata_lines = example.get("metadata", [])
    reasoning_lines = example.get("reasoning", [])
    response_text = example.get("response_text", "")
    
    # Start building the XML structure, add the description and user input
    xml_content = f"""<example>
        <example_docstring>
            {docstring}
        </example_docstring>
        <example_stimulus>
            <{tag_prefix}stimulus starting_id="{starting_id}">
            {user_input}
            </{tag_prefix}stimulus>
            <{tag_prefix}stimulus_metadata>
            """
    
    # Add metadata lines
    for metadata_line in metadata_lines:
        xml_content += f"{metadata_line}\n"
    
    xml_content += f"""</{tag_prefix}stimulus_metadata>
        </example_stimulus>
        <example_response>
            <{tag_prefix}reasoning>
            """
    
    # Add reasoning lines
    for reasoning_line in reasoning_lines:
        xml_content += f"{reasoning_line}\n"
    
    xml_content += f"""</{tag_prefix}reasoning>
            {response_text}"""
    
    # Add action invocation section
    if "action" in example:
        action_data = example.get("action", {})
        status_update = example.get("status_update", "")
        agent_name = action_data.get("agent", "")
        action_name = action_data.get("name", "")
        
        xml_content += f"""
            <{tag_prefix}status_update>{status_update}</{tag_prefix}status_update>
            <{tag_prefix}invoke_action agent="{agent_name}" action="{action_name}">"""
        
        # Handle parameters as dictionary
        parameter_dict = action_data.get("parameters", {})
        for param_name, param_value in parameter_dict.items():
            xml_content += f"""
            <{tag_prefix}parameter name="{param_name}">"""
            
            # Handle parameter names and values (as lists)
            if isinstance(param_value, list):
                for line in param_value:
                    xml_content += f"\n{line}"
                xml_content += "\n"
            else:
                # For simple string values
                xml_content += f"{param_value}"
                
            xml_content += f"</{tag_prefix}parameter>\n"
    
        xml_content += f"</{tag_prefix}invoke_action>"
    
    # Close the XML structure
    xml_content += """
        </example_response>
    </example>
    """

    return xml_content

LONG_TERM_MEMORY_PROMPT = " - You are capable of remembering things and have long-term memory, this happens automatically."