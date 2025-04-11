"""PlantUML diagram"""

import platform
import os
import tempfile
import subprocess

from solace_ai_connector.common.log import log
from ....common.action import Action
from ....common.action_response import ActionResponse
from ....services.file_service import FileService

PLANTUML_PROMPT = """Generate a PlantUML markup language for the given description by the user. Supports sequence diagrams, class diagrams, use case diagrams, activity diagrams, component diagrams, state diagrams, and timing diagrams. Newlines must be escaped with a backslash and put quotes around participants names. Respond only with PlantUML markup, do not include any other text, symbols or quotes.
Rules to follow for sequence diagrams:
    - Do not use variables if they are not declared as participants.
    - Only use notes to cover one or two participants per line.
    - Do not use the `activate` or `deactivate` commands directly after a delay notation (`...`), whether directly or with a note in between.
    - Do not use the `activate` or `deactivate` commands twice in a row, whether directly or with a note in between.
"""


class PlantUmlDiagram(Action):

    def __init__(self, **kwargs):
        super().__init__(
            {
                "name": "plantuml",
                "prompt_directive": (
                    "Generate PlantUML diagrams using description. Supports sequence diagrams, class diagrams, "
                    "use case diagrams, activity diagrams, component diagrams, state diagrams, and timing diagrams."
                ),
                "params": [
                    {
                        "name": "diagram_description",
                        "desc": "The detailed description of the diagram to be generated in natural English language.",
                        "type": "string",
                    }
                ],
                "required_scopes": ["global:plantuml:read"],
            },
            **kwargs,
        )

    def invoke(self, params, meta={}) -> ActionResponse:
        if platform.system() == "Windows":
            return ActionResponse(
                message=f"Unfortunately, the PlantUML is not available on {platform.system()}"
            )
        # Do a local command to run plantuml -tpng
        description = params.get("diagram_description")
        agent = self.get_agent()
        messages = [
            {"role": "system", "content": PLANTUML_PROMPT},
            {"role": "user", "content": description},
        ]
        agent = self.get_agent()
        try:
            response = agent.do_llm_service_request(messages=messages)
            expression = response.get("content")
        except TimeoutError as e:
            log.error("LLM request timed out: %s", str(e))
            return ActionResponse(message="LLM request timed out")
        except Exception as e:
            log.error("Failed to process content with LLM: %s", str(e))
            return ActionResponse(message="Failed to process content with LLM")

        # Surround expression with @startuml and @enduml if missing
        if not expression.startswith("@startuml"):
            expression = f"@startuml\n{expression}"
        if not expression.endswith("@enduml"):
            expression = f"{expression}\n@enduml"
        log.debug("PlantUML expression: %s", expression)
        img_path = None
        files = []
        with tempfile.NamedTemporaryFile(delete=True) as temp:
            temp.write(expression.encode())
            temp.flush()
            dir_path = os.path.dirname(temp.name)
            img_path = f"{dir_path}/{os.path.basename(temp.name)}.png"

            try:
                subprocess.run(
                    ["plantuml", "-tpng", temp.name, "-o", dir_path],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                file_service = FileService()
                file_meta = file_service.upload_from_file(
                    img_path,
                    meta.get("session_id"),
                    data_source="Global Agent - PlantUML Action",
                )
                files.append(file_meta)

            except subprocess.CalledProcessError as e:
                log.error("Subprocess failed with stderr: %s", e.stderr)
                return ActionResponse(
                    message=f"Failed to create diagram: {e.stderr}",
                )

        return ActionResponse(
            message=f"diagram created with the plantUML: \n```\n{expression}\n```",
            files=files,
        )
