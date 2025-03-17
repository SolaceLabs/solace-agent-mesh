"""Action description"""

import os
import sys
import importlib.util
import subprocess

from solace_ai_connector.common.log import log


from solace_agent_mesh.common.action import Action
from solace_agent_mesh.common.action_response import ActionResponse
from src.services.file_service import FileService

# To import from a local file, like this file, use a relative path from the replicator
# For example, to load this class, use:
#   from replicator.actions.sample_action import SampleAction


class ActionReplicator(Action):
    def __init__(self, **kwargs):
        super().__init__(
            {
            "name": "sample_action",
            "prompt_directive": ("This action can create instances of specific agent plugins. "),
            "params": [
                {
                "name": "new_agent_name",
                "desc": ("The name of the agent plugin to replicate.", 
                     "Supported plugins are 'sam_sql_database'."),
                "type": "string",
                },
                {
                "name": "existing_agent_plugin_name",
                "desc": ("The name of the agent plugin to replicate.", 
                     "Supported plugins are 'sam_sql_database'."),
                "type": "string",
                },
                {
                "name": "configuration_description",
                "desc": "Natural language description of the configuration for this agent instance.",
                "type": "string",
                }
            ],
            "required_scopes": ["replicator:agent:create"],
            },
            **kwargs,
        )

    def invoke(self, params, meta={}) -> ActionResponse:
        log.debug("Invoking sample action with params: %s", params)
        return self.do_action(params)

    def do_action(self, params, meta={}) -> ActionResponse:
        # Extract parameters
        existing_agent_plugin_name = params.get("existing_agent_plugin_name")
        new_agent_name = params.get("new_agent_name")
        
        # Check if plugin name is supported
        if existing_agent_plugin_name != "sam-sql-database":
            return ActionResponse(message="I cannot make a copy of this plugin")
        
        # Check if the Python library exists
        try:
            # Try to import the library
            importlib.util.find_spec(existing_agent_plugin_name.replace("-", "_"))
        except ImportError:
            # If not found, install it
            subprocess.check_call([sys.executable, "-m", "pip", "install", existing_agent_plugin_name])
        
        # Create destination directory
        destination_dir = f"/tmp/{new_agent_name}"
        if not os.path.exists(destination_dir):
            os.makedirs(destination_dir)
        
        # Get session_id from meta
        session_id = meta.get("session_id")
        
        # Create FileService instance and get metadata
        file_service = FileService()
        all_metadata = file_service.list_all_metadata(session_id)
        
        # Filter for CSV files
        csv_files = [metadata for metadata in all_metadata if metadata.get("name", "").endswith(".csv")]
        
        # Download each CSV file
        for metadata in csv_files:
            file_url = metadata.get("url")
            filename = metadata.get("name")
            destination_path = os.path.join(destination_dir, filename)
            file_service.download_to_file(file_url, destination_path, session_id)
        
        # TODO: Create the new agent flow with configuration
        
        return ActionResponse(message=f"Successfully copied {len(csv_files)} CSV files to {destination_dir}")
