import sys
import os
import logging
import uuid
import json
import time
import threading
import queue
from functools import wraps

# Add the project root to the path
solace_agent_mesh = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(solace_agent_mesh)

from flask import Flask, request, jsonify, Response, stream_with_context
from solace_agent_mesh.cli.commands.add.agent import add_agent_command
from scripts.test_build import run_agent_mesh, test_agent_with_test_cases
from helpers import (
    make_llm_api_call,
    parse_actions_from_global_context,
    parse_agent_from_global_context,
    add_filenames_to_action_list_and_create,
    parse_config_output,
    parse_test_cases_xml,
    add_env_variable_if_missing,
    extract_filename,
    get_agent_file,
)
from scripts.prompts import (
    create_agent_prompt,
    create_test_cases_prompt,
    create_action_file_correcter_prompt,
)
from scripts.file_utils import (
    create_agent_component,
    delete_sample_action_file,
    write_agent_file,
)
from build_actions import output_action_file

from build_config import build_config

# from solace_agent_mesh.cli.config import Config

app = Flask(__name__)
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Stream queues to track progress for each job
# Maps job_id to a queue of progress events
stream_queues = {}
MAX_RETRIES = 3


def process_agent_creation(
    tracking_id, agent_name, agent_description, api_key, api_description
):
    """Process agent creation in a background thread and report progress via streaming."""
    try:
        # Initialize the stream queue for this job
        if tracking_id not in stream_queues:
            stream_queues[tracking_id] = queue.Queue()

        # Report initial progress
        report_progress(
            tracking_id, "initializing", 0, "Starting agent creation process"
        )

        # Create a default config when not in CLI context
        config = {
            "solace_agent_mesh": {
                "config_directory": os.path.join(os.getcwd(), "configs"),
                "modules_directory": os.path.join(os.getcwd(), "modules"),
            }
        }

        # Report progress
        report_progress(tracking_id, "in_progress", 10, "Creating agent framework")

        result = add_agent_command(agent_name, config)

        if result == 1:
            report_progress(
                tracking_id,
                "failed",
                0,
                f"Failed to create agent '{agent_name}'",
                error="Agent creation failed",
            )
            return

        # Report progress
        report_progress(
            tracking_id, "in_progress", 20, "Generating agent definition with AI"
        )

        # Prompt LLM to get the agent format in XML
        prompt = create_agent_prompt(
            agent_name, agent_description, bool(api_key), api_description
        )
        response = make_llm_api_call(prompt)

        # Parse XML response to dictionary
        action_dictionary = parse_actions_from_global_context(response)
        agent_dictionary = parse_agent_from_global_context(response)

        # Report progress
        report_progress(
            tracking_id, "in_progress", 25, "Creating agent component structure"
        )

        # Action(s) to be created
        imports = []
        action_names = []
        for action in action_dictionary:
            action_name = action["name"]
            action_names.append(action_name)
            # Convert action name to snake_case for file naming and action name
            snake_case_action = "".join(
                ["_" + c.lower() if c.isupper() else c for c in action_name]
            ).lstrip("_")
            imports.append(
                f"from {agent_name.replace('-','_')}.actions.{snake_case_action} import {action_name}"
            )

        # Create the new agent component
        create_agent_component(
            agent_name=agent_name.replace("-", "_"),
            actions=action_names,
            description=agent_dictionary["description"],
            imports=imports,
        )

        # Delete the sample action file
        delete_sample_action_file(agent_name.replace("-", "_"))

        # Report progress
        report_progress(tracking_id, "in_progress", 30, "Generating action files")

        # Create action files
        add_filenames_to_action_list_and_create(
            agent_name.replace("-", "_"), action_dictionary
        )

        # Report progress
        report_progress(tracking_id, "in_progress", 35, "Updating agent configuration")

        # update the config file with any needed configurations
        updated_config_file_raw = build_config(
            agent_name.replace("-", "_"),
            agent_dictionary,
            action_dictionary,
            bool(api_key),
        )
        updated_config_file_parsed = parse_config_output(updated_config_file_raw)
        write_agent_file(
            agent_name.replace("-", "_"),
            "agent_config",
            updated_config_file_parsed["file_content"],
        )

        configs_added = updated_config_file_parsed["configs_added"]
        environment_variable = updated_config_file_parsed["api_key_name"]

        # Report progress
        report_progress(
            tracking_id, "in_progress", 40, "Setting up environment variables"
        )

        if api_key:
            added = add_env_variable_if_missing(environment_variable, api_key)
            if added:
                print(f"Added environment variable: {environment_variable}")

        # Report progress
        report_progress(tracking_id, "in_progress", 50, "Creating action files")

        # update action files
        for action in action_dictionary:
            action_name = action["name"]
            action_file_name = action["filename"]
            action_description = action["description"]
            action_return_description = action["returns"]

            updated_action_file_raw = output_action_file(
                agent_name.replace("-", "_"),
                action_file_name,
                action_name,
                action_description,
                action_return_description,
                configs_added,
                api_description,
            )
            updated_action_file_parsed = parse_config_output(updated_action_file_raw)
            write_agent_file(
                agent_name.replace("-", "_"),
                "agent_action",
                updated_action_file_parsed["file_content"],
                action_file_name,
            )

        # Report progress
        report_progress(tracking_id, "in_progress", 65, "Creating test cases")

        test_case_prompt = create_test_cases_prompt(
            agent_name.replace("-", "_"),
            agent_dictionary["description"],
            action_dictionary,
        )
        test_case_response = make_llm_api_call(test_case_prompt)

        test_case_dictionary = parse_test_cases_xml(test_case_response)

        # Test build
        retries_left = MAX_RETRIES
        while retries_left > 0:
            report_progress(tracking_id, "in_progress", 80, "Testing the new agent")
            # success, error_message = run_agent_mesh(test_case_dictionary)
            success, error_message = run_agent_mesh()
            if success:
                break
            retries_left -= 1
            print(f"Retrying test build. Retries left: {retries_left}")
            print(f"Error message: {error_message}")

            # Find action file that caused the error
            action_file_name = extract_filename(error_message)
            print(
                f"content of file: {get_agent_file(agent_name.replace('-', '_'), "agent_action", action_file_name)}"
            )

            report_progress(
                tracking_id,
                "in_progress",
                85,
                f"Correcting action file: {action_file_name}.py\n {retries_left} retries left",
            )

            # Modify action file(s) to fix the error
            action_file_correcter_prompt = create_action_file_correcter_prompt(
                get_agent_file(
                    agent_name.replace("-", "_"), "agent_action", action_file_name
                ),
                error_message,
            )
            response = make_llm_api_call(action_file_correcter_prompt)
            print(f"Response: {response}")
            write_agent_file(
                agent_name.replace("-", "_"),
                "agent_action",
                response,
                action_file_name,
            )

        if not success:
            print(f"Agent mesh failed to start: {error_message}")
            return (
                jsonify(
                    {
                        "success": False,
                        "message": f"Failed to build agent '{agent_name}'",
                        "error": error_message,
                    }
                ),
                500,
            )

        # Final update - completed
        report_progress(
            tracking_id,
            "completed",
            100,
            f"Agent '{agent_name}' created successfully",
            is_complete=True,
        )

    except Exception as e:
        # Report error
        report_progress(
            tracking_id, "failed", 0, f"Error creating agent: {str(e)}", error=str(e)
        )


@app.route("/api/create-agent", methods=["POST"])
def create_agent():
    """Create a new agent with the provided configuration."""
    data = request.json

    # Extract data from request
    agent_name = data.get("name")
    agent_description = data.get("description")
    api_key = data.get("apiKey")
    api_description = data.get("apiDescription")

    # Generate a tracking ID for this job
    tracking_id = str(uuid.uuid4())

    # Initialize the stream queue
    stream_queues[tracking_id] = queue.Queue()

    # Start the process in a background thread
    thread = threading.Thread(
        target=process_agent_creation,
        args=(tracking_id, agent_name, agent_description, api_key, api_description),
    )
    thread.daemon = True  # Make sure thread doesn't block application exit
    thread.start()

    # Return the tracking ID immediately
    return jsonify(
        {
            "success": True,
            "message": "Agent creation started",
            "tracking_id": tracking_id,
        }
    )


# Helper function to report progress through the stream
def report_progress(job_id, status, progress, message, error=None, is_complete=False):
    """Add a progress event to the queue for a job"""
    if job_id not in stream_queues:
        # If queue doesn't exist, ignore the event
        return

    event = {
        "id": str(uuid.uuid4()),
        "event": "progress",
        "data": {
            "status": status,
            "progress": progress,
            "message": message,
            "error": error,
            "is_complete": is_complete,
        },
    }

    stream_queues[job_id].put(json.dumps(event))

    # If complete or error, add a special "complete" event after a short delay
    if is_complete or status == "failed":
        # Add the complete event after the progress event
        complete_event = {
            "id": str(uuid.uuid4()),
            "event": "complete",
            "data": {"status": status, "success": status == "completed"},
        }
        stream_queues[job_id].put(json.dumps(complete_event))


# SSE endpoint for streaming progress updates
@app.route("/api/progress/<job_id>/stream", methods=["GET"])
def stream_progress(job_id):
    """Stream progress events for a job using Server-Sent Events (SSE)"""

    def event_stream():
        # Create a new queue if one doesn't exist
        if job_id not in stream_queues:
            stream_queues[job_id] = queue.Queue()

            # Send an initial "connected" event
            initial_event = {
                "id": str(uuid.uuid4()),
                "event": "connected",
                "data": {"message": "Connected to progress stream"},
            }
            yield f"data: {json.dumps(initial_event)}\n\n"

        # Get the queue for this job
        q = stream_queues[job_id]

        try:
            # Keep the connection open indefinitely
            while True:
                try:
                    # Try to get an event with a timeout
                    event_data = q.get(timeout=30)
                    yield f"data: {event_data}\n\n"

                    # Check if the event was a complete event
                    event = json.loads(event_data)
                    if event.get("event") == "complete":
                        # When complete, break the loop to close the connection
                        break

                except queue.Empty:
                    # Send a keepalive comment to prevent the connection from timing out
                    yield ": keepalive\n\n"
        finally:
            # If we break out of the loop for any reason, remove the queue
            if job_id in stream_queues:
                del stream_queues[job_id]

    # Return the event stream with appropriate headers
    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable buffering in Nginx
            "Connection": "keep-alive",
        },
    )


# Add a health check endpoint
@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "message": "API is running"})


# Add a catch-all route to help debug 404s
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def catch_all(path):
    print(f"Received request for path: {path}")
    return (
        jsonify(
            {
                "error": "not_found",
                "message": f"Path '/{path}' not found",
                "available_endpoints": [
                    "/api/create-agent",
                    "/api/health",
                    "/api/progress/<job_id>/stream",
                ],
            }
        ),
        404,
    )


if __name__ == "__main__":
    # Run on 0.0.0.0 to make it accessible from other machines/containers
    print("Starting server with CORS enabled for all origins...")
    app.run(host="0.0.0.0", port=5002, debug=True)
