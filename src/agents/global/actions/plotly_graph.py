"""Plotly graph generation"""

import platform
import os
import random
import tempfile
import json
import yaml
from importlib.metadata import version
from io import BytesIO
from packaging.version import parse
from solace_ai_connector.common.log import log

import plotly.graph_objects as go
import plotly.io as pio

from ....common.action import Action
from ....common.action_response import ActionResponse
from ....services.file_service import FileService


class PlotlyGraph(Action):

    def __init__(self, **kwargs):
        super().__init__(
            {
                "name": "plotly",
                "prompt_directive": (
                    "Create a plotly graph from the given plotly figure configuration. Note that this will be rendered as a static image that can't be interacted with."
                ),
                "params": [
                    {
                        "name": "plotly_figure_config",
                        "desc": "The plotly figure configuration as a yaml object (do not give python code, just the yaml object)",
                        "type": "object",
                    }
                ],
                "required_scopes": ["global:plotly:read"],
                "examples": [
                    {
                        "docstring": "This is an example of a user asking for a bar graph. The plotly action from the global agent is invoked to generate the graph.",
                        "tag_prefix_placeholder": "{tp}",
                        "starting_id": "12",
                        "user_input": "Please generate a random bar graph for me",
                        "metadata": [
                            "local_time: 2024-09-04 15:59:02 EDT-0400 (Wednesday)"
                        ],
                        "reasoning": [
                            "- user has requested a random bar graph",
                            "- invoke the plotly action from the global agent to generate a bar graph with random data"
                        ],
                        "response_text": "Certainly! I'd be happy to generate a random bar graph for you.",
                        "status_update": "I'll use our plotting tool to create this for you right away.",
                        "action": {
                            "agent": "global",
                            "name": "plotly",
                            "parameter_name": "plotly_figure_config",
                            "parameters": {
                                "plotly_figure_config": [
                                    "{{",
                                    "    \"data\": [",
                                    "    {{",
                                    "        \"x\": [\"A\", \"B\", \"C\", \"D\", \"E\"],",
                                    "        \"y\": [23, 45, 56, 78, 90],",
                                    "        \"type\": \"bar\"",
                                    "    }}",
                                    "    ],",
                                    "    \"layout\": {{",
                                    "    \"title\": \"Random Bar Graph\",",
                                    "    \"xaxis\": {{\"title\": \"Categories\"}},",
                                    "    \"yaxis\": {{\"title\": \"Values\"}}",
                                    "    }}",
                                    "}}"
                                ]
                            }
                        }
                    }
                ],
            },
            **kwargs,
        )

    def invoke(self, params, meta={}) -> ActionResponse:
        if platform.system() == "Windows":
            kaleido_version = version('kaleido')
            min_version = parse('0.1.0.post1')
            max_version = parse('0.2.0')
            if parse(kaleido_version) < min_version or parse(kaleido_version) >= max_version:
                return ActionResponse(
                    message="For Windows users, the plotting functionality requires a specific version of Kaleido. Please refer to the documentation."
                )
        obj = params["plotly_figure_config"]
        if isinstance(obj, str):
            # Remove any leading/trailing quote characters
            obj = obj.strip("'\" ")
            try:
                obj = json.loads(obj)
            except:  # pylint: disable=bare-except
                try:
                    obj = yaml.safe_load(obj)
                except Exception:  # pylint: disable=broad-except
                    return ActionResponse(
                        message=f"Could not parse plotly figure configuration: {obj}\n\nNOTE that this action expects a config object, not code.",
                    )

        files = []
        try:
            fig = go.Figure(obj)
            byte_io = BytesIO()
            pio.write_image(fig, byte_io)
            byte_io.seek(0)
            file_service = FileService()
            image_name = "generated_graph_" + str(random.randint(100000, 999999)) + ".png"
            image_meta = file_service.upload_from_buffer(
                byte_io.read(),
                image_name,
                meta.get("session_id"),
                data_source="Global Agent - PlotlyGraph Action",
            )
            files.append(image_meta)
        except Exception as e:
            return ActionResponse(
                message="Could not create plotly graph. Please check the plotly figure configuration. plotly error: " + str(e),
            )

        return ActionResponse(files=files)
