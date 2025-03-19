import subprocess
import json
import logging
import requests
import sys
import signal
import time
import os

from solace_agent_mesh.cli.commands.chat import chat_command
from solace_agent_mesh.cli.commands.run import run_command

# Add the parent directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from helpers import make_llm_api_call

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("agent_mesh.log"), logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("agent_mesh_runner")
process = None


def run_agent_mesh(test_cases=None):
    try:
        # Use Popen to stream output in real-time
        process = subprocess.Popen(
            ["solace-agent-mesh", "run", "-eb"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
        )

        errors_found = False
        error_message = None
        all_output = []

        # Process stdout in real-time
        for line in process.stdout:
            # Store the output
            all_output.append(line)

            # Print the line as it comes
            print(line, end="")

            if "Solace AI Event Connector started successfully" in line:
                logger.info("Solace AI Event Connector started successfully")
                print("Solace Agent Mesh built successfully")

                # Test cases
                # passed_test_cases, test_results = test_agent_with_test_cases(test_cases)

                # print(f"Passed Tests: {passed_test_cases}")

                stop_agent_mesh(process)
                return True, None

        # Process stderr in real-time
        for line in process.stderr:
            # Store the output
            all_output.append(line)

            # Print the line as it comes
            print(line, end="", file=sys.stderr)

            # Log the error
            errors_found = True
            if not error_message:
                error_message = f"Error in stderr: {line.strip()}"

        stop_agent_mesh(process)
        return False, None

    except Exception as e:
        # Catch any other exceptions
        error_message = f"An unexpected error occurred: {str(e)}"
        logger.error(error_message)
        return False, error_message


def stop_agent_mesh(process):
    """Stop the running agent mesh process gracefully."""
    if process is None:
        logger.warning("No agent mesh process is running")
        return False

    try:
        logger.info("Attempting to stop agent mesh process gracefully...")

        # First try SIGTERM for graceful shutdown
        process.terminate()

        # Give it some time to shut down gracefully
        for _ in range(5):  # Wait up to 5 seconds
            if process.poll() is not None:
                logger.info("Agent mesh process terminated successfully")
                print("Agent mesh process terminated successfully")
                return True
            time.sleep(1)

        # If still running, force kill
        logger.warning("Process did not terminate gracefully, forcing kill...")
        process.kill()
        process.wait()
        logger.info("Agent mesh process killed")
        return True

    except Exception as e:
        logger.error(f"Error stopping agent mesh process: {str(e)}")
        return False


def test_agent_with_test_cases(test_cases):
    """
    Test the agent with the given test cases

    Args:
        test_cases (list): List of test cases to run

    Returns:
        dict: A dictionary containing the test results
    """
    test_results = []
    print(f"test_cases: {test_cases}")

    if test_cases is None:
        logger.info("No test cases provided")
        return False, []

    try:
        # Wait longer for the server to fully initialize
        logger.info("Waiting for API server to be ready...")
        max_retries = 30  # 30 seconds max wait time
        api_ready = False

        for i in range(max_retries):
            try:
                # Try a simple request to check if the API is ready
                response = requests.get("http://127.0.0.1:5050/health", timeout=1)
                if response.status_code == 200:
                    logger.info("API server is ready")
                    api_ready = True
                    break
            except requests.exceptions.RequestException:
                logger.info(f"API not ready yet, waiting... ({i+1}/{max_retries})")
                time.sleep(1)

        if not api_ready:
            logger.error("API server failed to start in the expected time")
            return False, [{"error": "API server failed to start in the expected time"}]

        # Extract the actual list of test cases from the dictionary
        test_cases_list = test_cases.get("test_cases", [])

        for i, test_case in enumerate(test_cases_list):
            # Extract test case data
            print(f"test_case: {test_case}")
            input_message = test_case.get("user_query", "")
            expected_output_obj = test_case.get("expected_output", {})
            expected_output = (
                expected_output_obj.get("description", "")
                if isinstance(expected_output_obj, dict)
                else ""
            )

            # Get action and agent info
            action_name = test_case.get("action_name", "")
            agent_name = test_case.get("agent_name", "")
            test_title = test_case.get("title", f"Test case {i+1}")

            logger.info(f"Running test: {test_title}")
            logger.info(f"Input: {input_message}")
            logger.info(f"Expected: {expected_output}")

            # Simulate response
            url = "http://127.0.0.1:5050/api/v1/request"
            data = {"prompt": input_message, "stream": False}
            response = requests.post(url, data=data).json()
            print(f"\nresponse: {response["response"]["content"]}")

            # Compare response with expected output
            # Do an LLM API call to compare the responses
            # Compare response with expected output using LLM
            comparison_prompt = f"""
            You are an AI test evaluator. Compare the actual response with the expected output and determine if they match semantically.

            Expected output: {expected_output}
            Actual response: {response["response"]["content"]}
            Do these match in meaning and intent? Answer with only 'yes' or 'no'.
            """

            comparison_result = make_llm_api_call(comparison_prompt)
            matches_expected = comparison_result.lower().startswith("yes")

            logger.info(f"LLM comparison result: {comparison_result}")
            logger.info(f"Test passed: {matches_expected}")

            test_results.append(
                {
                    "test_case": i + 1,
                    "title": test_title,
                    "input": input_message,
                    "expected": expected_output,
                    "actual": response,
                    "passed": matches_expected,
                    "agent_name": agent_name,
                    "action_name": action_name,
                }
            )

        passed_count = sum(1 for result in test_results if result["passed"])
        total_count = len(test_results)

        logger.info(f"Test results: {passed_count}/{total_count} tests passed")
        print(test_results)

        return passed_count > 0, test_results

    except Exception as e:
        error_message = f"Error testing agent: {str(e)}"
        logger.error(error_message)
        return False, [{"error": error_message}]


# test_case_dictionary = {
#     "test_cases": [
#         {
#             "agent_name": "health_expert",
#             "action_name": "GetCalorieEstimate",
#             "id": "1",
#             "title": "Basic Fruit Calorie Query",
#             "user_query": "How many calories are in an apple?",
#             "invoke_action": {
#                 "agent_name": "health_expert",
#                 "action_name": "GetCalorieEstimate",
#             },
#             "expected_output": {
#                 "status": "success",
#                 "description": "Approximate calorie count for a medium apple with brief nutritional context.",
#             },
#         },
#         {
#             "agent_name": "health_expert",
#             "action_name": "GetCalorieEstimate",
#             "id": "2",
#             "title": "Basic Protein Food Calorie Query",
#             "user_query": "What's the calorie content of a chicken breast?",
#             "invoke_action": {
#                 "agent_name": "health_expert",
#                 "action_name": "GetCalorieEstimate",
#             },
#             "expected_output": {
#                 "status": "success",
#                 "description": "Approximate calorie count for a standard chicken breast serving with brief nutritional context.",
#             },
#         },
#     ]
# }
# test_agent_with_test_cases(test_case_dictionary)
