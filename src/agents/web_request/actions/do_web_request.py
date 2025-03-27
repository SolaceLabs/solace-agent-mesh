"""Web Request action"""

from solace_ai_connector.common.log import log
import requests
from bs4 import BeautifulSoup
import html2text


from ....common.action import Action
from ....common.action_response import ActionResponse


class DoWebRequest(Action):

    def __init__(self, **kwargs):
        super().__init__(
            {
                "name": "do_web_request",
                "prompt_directive": "Fetch content from a URL and process it according to a specified LLM prompt. Returns processed content from a single web request. For comprehensive data gathering, multiple requests may be needed to follow relevant links.",
                "params": [
                    {
                        "name": "url",
                        "desc": "URL to fetch",
                        "type": "string",
                    },
                    {
                        "name": "llm_prompt",
                        "desc": "Text prompt to direct the LLM on how to process the fetched content. If this parameter is not provided, the fetched content will be returned as is.",
                        "type": "string",
                    },
                ],
                "required_scopes": ["web_request:do_web_request:read"],
                "examples": [
                    {
                        "docstring": "This is an example of a user requesting to fetch information from the web. The web_request agent is open so invoke the do_web_request action to fetch the content from the url and process the information according to the llm_prompt.",
                        "tag_prefix_placeholder": "{tp}",
                        "starting_id": "10",
                        "user_input": "What is the weather in Ottawa?",
                        "metadata": [
                            "local_time: 2024-11-06 12:33:12 EST-0500 (Wednesday)"
                        ],
                        "reasoning": [
                            "- User is asking for current weather information in Ottawa",
                            "- We need to fetch up-to-date weather data",
                            "- Use the web_request agent to get the latest weather information",
                            "- Plan to use the Environment Canada website for accurate local weather data"
                        ],
                        "response_text": "Certainly! I'll fetch the current weather information for Ottawa for you right away.",
                        "status_update": "Retrieving the latest weather data for Ottawa...",
                        "action": {
                            "agent": "web_request",
                            "name": "do_web_request",
                            "parameters": {
                                "url": "https://weather.gc.ca/city/pages/on-118_metric_e.html",
                                "llm_prompt": "Extract the current temperature, weather conditions, and any important weather alerts or warnings for Ottawa from the webpage. Format the response as a bulleted list with emoji where appropriate."
                            }
                        }
                    }
                ],
            },
            **kwargs,
        )

    def get_system_prompt(self):
        return """
        The assistant is a professional web researcher. It will take the URL and request below and 
        will diligently extract the requested information from that URL. Sometimes the page does
        not have the information requested, but it might be on a different page that is linked to
        from this page. In that case the assistant will indicate the page doesn't have the information
        but it will provide other links to try for the information.
        
        The assistant will also include a section of 'interesting links' that it found on the page
        that might be useful for further research. These links must be from the page and not from
        the assistant's own knowledge.
        
        The assistant will respond in markdown format.
        """

    def get_user_prompt(self, url, content, prompt):
        return f"""
        <page_url>{url}</page_url>
        <research_request>
        {prompt}
        </research_request>
        <page_content_markdown>
        {content}
        </page_content_markdown>
        """

    def invoke(self, params, meta={}) -> ActionResponse:
        url = params.get("url")
        prompt = params.get("llm_prompt")

        if not url:
            return ActionResponse(message="URL is required")

        # Fetch the content from the URL
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
        except Exception as e:
            return ActionResponse(message=f"Failed to fetch content from URL: {e}")

        # Use beautiful soup to extract the text content from the HTML
        soup = BeautifulSoup(response.content, "html.parser")

        # Convert the HTML content to Markdown using html2text
        h = html2text.HTML2Text()
        h.ignore_links = False  # Ensure that links are preserved
        h.ignore_images = False  # Ignore images
        content = h.handle(str(soup))

        # If a prompt is provided, send the content to an LLM model
        if prompt:
            system_prompt = self.get_system_prompt()
            user_prompt = self.get_user_prompt(url, content, prompt)

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            agent = self.get_agent()
            try:
                response = agent.do_llm_service_request(messages=messages)
                content = response.get("content")
            except TimeoutError as e:
                log.error("LLM request timed out: %s", str(e))
                return ActionResponse(message="LLM request timed out")
            except Exception as e:
                log.error("Failed to process content with LLM: %s", str(e))
                return ActionResponse(message="Failed to process content with LLM")

        # Code to create the image using the provided content
        return ActionResponse(message=content)
