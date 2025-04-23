"""This test the orchestrator_streaming_output_component"""

import unittest

from solace_ai_connector.test_utils.utils_for_test_files import run_component_test
from src.services.file_service import FileService

file_manager_config = {
    "type": "memory",
    "max_time_to_live": 86400,
    "expiration_check_interval": 600,
    "config": {"memory": {}},
}

FileService(file_manager_config)


def strip_lines(text):
    return "\n".join([line.strip() for line in text.strip().split("\n")]).strip()

class TestOrchestratorStreamingOutput(unittest.TestCase):

    def setUp(self):
        self.maxDiff = None

    def test_simple_streaming_output(self):
        """Test the OrchestratorStreamingOutputComponent with a basic message"""

        def validation_func(output_data, _output_message, _input_message):
            self.assertEqual(
                output_data[0],
                [
                    {
                        "text": "Hello",
                        "streaming": True,
                        "first_chunk": True,
                        "last_chunk": True,
                        "uuid": "1234-0",
                        "chunk": "Hello",
                    }
                ],
            )

        run_component_test(
            "src.orchestrator.components.orchestrator_streaming_output_component",
            validation_func,
            input_data={
                "content": "Hello",
                "streaming": True,
                "first_chunk": True,
                "last_chunk": True,
                "response_uuid": "1234",
                "check_reasoning": False,
            },
        )

    def test_multiple_chunks_streaming_output(self):
        """Test the OrchestratorStreamingOutputComponent with multiple input data, but only one message"""

        def validation_func(output_data, _output_message, _input_message):
            self.assertEqual(
                output_data,
                [
                    [
                        {
                            "text": "Hello",
                            "chunk": "Hello",
                            "streaming": True,
                            "first_chunk": True,
                            "last_chunk": False,
                            "uuid": "1234-0",
                        }
                    ],
                    [
                        {
                            "text": "Hello World",
                            "chunk": " World",
                            "streaming": True,
                            "first_chunk": False,
                            "last_chunk": True,
                            "uuid": "1234-0",
                        }
                    ],
                ],
            )

        run_component_test(
            "src.orchestrator.components.orchestrator_streaming_output_component",
            validation_func,
            input_data=[
                {
                    "content": "Hello",
                    "streaming": True,
                    "first_chunk": True,
                    "last_chunk": False,
                    "response_uuid": "1234",
                    "check_reasoning": False,
                },
                {
                    "content": "Hello World",
                    "streaming": True,
                    "first_chunk": False,
                    "last_chunk": True,
                    "response_uuid": "1234",
                    "check_reasoning": False,
                },
            ],
        )

    def test_multiple_content_pieces_streaming_output(self):
        """Test the OrchestratorStreamingOutputComponent with multiple pieces of content"""

        def validation_func(output_data, _output_message, _input_message):
            # Make sure there is a URL for the file
            self.assertTrue(output_data[0][1]["files"][0]["url"])
            # Now delete the URL so we can compare the rest of the data
            del output_data[0][1]["files"][0]["url"]
            del output_data[0][1]["files"][0]["expiration_timestamp"]
            del output_data[0][1]["files"][0]["session_id"]
            del output_data[0][1]["files"][0]["file_size"]
            del output_data[0][1]["files"][0]["upload_timestamp"]
            self.assertEqual(
                output_data,
                [
                    [
                        {
                            "text": "First bit of content\n",
                            "streaming": True,
                            "first_chunk": True,
                            "last_chunk": True,
                            "uuid": "1234-0",
                        },
                        {
                            "files": [
                                {
                                    "data": "My file content",
                                    "mime_type": "text/plain",
                                    "name": "file1.txt",
                                    "data_source": "Orchestrator created data",
                                }
                            ],
                            "streaming": True,
                            "first_chunk": True,
                            "last_chunk": True,
                            "uuid": "1234-1",
                        },
                        {
                            "text": "Last bit of content\n\nAnd the end",
                            "chunk": "First bit of content\nLast bit of content\n\nAnd the end",
                            "streaming": True,
                            "first_chunk": True,
                            "last_chunk": True,
                            "uuid": "1234-2",
                        },
                        {
                            "status_update": True,
                            "streaming": True,
                            "text": "Work is complete",
                            "uuid": "1234-status",
                        },
                    ],
                ],
            )

        run_component_test(
            "src.orchestrator.components.orchestrator_streaming_output_component",
            validation_func,
            input_data=[
                {
                    "content": strip_lines(
                        """
                        First bit of content<status_update>Doing some work</status_update>
                        <file name="file1.txt" mime_type="text/plain">
                        <data>
                        My file content
                        </data>
                        </file>
                        Last bit of content
                        <status_update>Work is complete</status_update>
                        And the end
                    """
                    ),
                    "streaming": True,
                    "first_chunk": True,
                    "last_chunk": True,
                    "response_uuid": "1234",
                    "check_reasoning": False,
                },
            ],
        )

    def test_empty_data(self):
        """Test the component with empty data"""

        def validation_func(_output_data, _output_message, _input_message):
            pass

        try:
            run_component_test(
                "src.orchestrator.components.orchestrator_streaming_output_component",
                validation_func,
                input_data={},
            )
        except Exception as e:
            self.assertIn(
                "Either input_data or input_messages must be provided", str(e)
            )

    def test_response_complete(self):
        """Test the component with a response_complete message"""

        def validation_func(output_data, _output_message, _input_message):
            self.assertEqual(
                output_data, [[{"response_complete": True, "streaming": True}]]
            )

        run_component_test(
            "src.orchestrator.components.orchestrator_streaming_output_component",
            validation_func,
            input_data={"response_complete": True, "streaming": True},
        )

    def test_invalid_content(self):
        """Test the component with an invalid content"""

        def validation_func(output_data, _output_message, _input_message):
            print("output_data", output_data)
            self.assertEqual(output_data, [None])

        run_component_test(
            "src.orchestrator.components.orchestrator_streaming_output_component",
            validation_func,
            input_data={
                "content": "Invalid content",
            },
            max_response_timeout=3,
        )

    def test_empty_content(self):
        """Test the component with empty content"""

        def validation_func(output_data, _output_message, _input_message):
            self.assertEqual(output_data, [None])

        run_component_test(
            "src.orchestrator.components.orchestrator_streaming_output_component",
            validation_func,
            input_data=[None],
            max_response_timeout=3,
        )

    def test_already_sent_content(self):
        """Test the component with already sent content"""
        self.maxDiff = None

        def validation_func(output_data, _output_message, _input_message):
            # Verify that the file has a URL
            self.assertTrue(output_data[1][1]["files"][0]["url"])
            # Now delete the URL so we can compare the rest of the data
            del output_data[1][1]["files"][0]["url"]
            del output_data[1][1]["files"][0]["expiration_timestamp"]
            del output_data[1][1]["files"][0]["session_id"]
            del output_data[1][1]["files"][0]["file_size"]
            del output_data[1][1]["files"][0]["upload_timestamp"]
            self.assertEqual(
                output_data,
                [
                    [
                        {
                            "text": "Hi",
                            "chunk": "Hi",
                            "streaming": True,
                            "first_chunk": True,
                            "last_chunk": False,
                            "uuid": "1234-0",
                        },
                        {
                            "status_update": True,
                            "streaming": True,
                            "text": "File file1.txt loading (51 characters)...",
                            "uuid": "1234-status",
                        },
                    ],
                    [
                        {
                            "text": "Hi\n",
                            "streaming": True,
                            "first_chunk": False,
                            "last_chunk": True,
                            "uuid": "1234-0",
                        },
                        {
                            "files": [
                                {
                                    "data": "My file content",
                                    "mime_type": "text/plain",
                                    "name": "file1.txt",
                                    "data_source": "Orchestrator created data",
                                }
                            ],
                            "streaming": True,
                            "first_chunk": True,
                            "last_chunk": True,
                            "uuid": "1234-1",
                        },
                        {
                            "text": "Bye",
                            "chunk": "\nBye",
                            "streaming": True,
                            "first_chunk": True,
                            "last_chunk": False,
                            "uuid": "1234-2",
                        },
                    ],
                    [
                        {
                            "text": "Bye Bye",
                            "chunk": " Bye",
                            "streaming": True,
                            "first_chunk": False,
                            "last_chunk": True,
                            "uuid": "1234-2",
                        }
                    ],
                ],
            )

        run_component_test(
            "src.orchestrator.components.orchestrator_streaming_output_component",
            validation_func,
            input_data=[
                {
                    "content": strip_lines(
                        """
                        <t321_reasoning>
                        This is some reasoning
                        </t321_reasoning>
                        Hi
                        <t321_file name="file1.txt" mime_type="text/plain">
                        <dat
                        """
                    ),
                    "streaming": True,
                    "first_chunk": True,
                    "last_chunk": False,
                    "response_uuid": "1234",
                },
                {
                    "content": strip_lines(
                        """
                        <t321_reasoning>
                        This is some reasoning
                        </t321_reasoning>
                        Hi
                        <t321_file name="file1.txt" mime_type="text/plain">
                        <data>My file content</data>
                        </t321_file>
                        Bye
                        """
                    ),
                    "streaming": True,
                    "first_chunk": False,
                    "last_chunk": False,
                    "response_uuid": "1234",
                },
                {
                    "content": strip_lines(
                        """
                        <t321_reasoning>
                        This is some reasoning
                        </t321_reasoning>
                        Hi
                        <t321_file name="file1.txt" mime_type="text/plain">
                        <data>My file content</data>
                        </t321_file>
                        Bye Bye
                        """
                    ),
                    "streaming": True,
                    "first_chunk": False,
                    "last_chunk": True,
                    "response_uuid": "1234",
                },
            ],
            max_response_timeout=3,
        )

    def test_incomplete_tag(self):
        """Test the component with an incomplete tag"""

        def validation_func(output_data, _output_message, _input_message):
            self.assertEqual(
                output_data,
                [
                    [
                        {
                            "text": "Hello",
                            "chunk": "Hello",
                            "streaming": True,
                            "first_chunk": True,
                            "last_chunk": False,
                            "uuid": "1234-0",
                        },
                    ],
                    [
                        {
                            "streaming": True,
                            "text": "Hello",
                            "first_chunk": False,
                            "last_chunk": False,
                            "uuid": "1234-0",
                        },
                    ],
                    [
                        {
                            "streaming": True,
                            "text": "Hello\n\ndata",
                            "chunk": "\n\ndata",
                            "first_chunk": False,
                            "last_chunk": False,
                            "uuid": "1234-0",
                        },
                        {
                            "status_update": True,
                            "streaming": True,
                            "text": "hi",
                            "uuid": "1234-status",
                        },
                    ],
                    [
                        {
                            "streaming": True,
                            "text": "Hello\n\ndata",
                            "first_chunk": False,
                            "last_chunk": False,
                            "uuid": "1234-0",
                        },
                    ],
                    [
                        {
                            "streaming": True,
                            "text": "Hello\n\ndata",
                            "first_chunk": False,
                            "last_chunk": False,
                            "uuid": "1234-0",
                        },
                    ],
                ],
            )

        run_component_test(
            "src.orchestrator.components.orchestrator_streaming_output_component",
            validation_func,
            input_data=[
                {
                    "content": "Hello\n<t123_reasonin",
                    "streaming": True,
                    "first_chunk": True,
                    "last_chunk": False,
                    "response_uuid": "1234",
                    "check_reasoning": False,
                },
                {
                    "content": "Hello\n<t123_reasoning>Some reasoning</t123_reasoning><t123_status_update>hi</t123_sta",
                    "streaming": True,
                    "first_chunk": False,
                    "last_chunk": False,
                    "response_uuid": "1234",
                    "check_reasoning": False,
                },
                {
                    "content": "Hello\n<t123_reasoning>Some reasoning</t123_reasoning><t123_status_update>hi</t123_status_update>\n"
                    "data\n"
                    "<t123_invoke_action",
                    "streaming": True,
                    "first_chunk": False,
                    "last_chunk": False,
                    "response_uuid": "1234",
                    "check_reasoning": False,
                },
                {
                    "content": "Hello\n<t123_reasoning>Some reasoning</t123_reasoning><t123_status_update>hi</t123_status_update>\n"
                    "data\n"
                    '<t123_invoke_action agent="agent1" action="action1">\n'
                    '<t123_parameter name="param1">value1</t123_',
                    "streaming": True,
                    "first_chunk": False,
                    "last_chunk": False,
                    "response_uuid": "1234",
                    "check_reasoning": False,
                },
                {
                    "content": "Hello\n<t123_reasoning>Some reasoning</t123_reasoning><t123_status_update>hi</t123_status_update>\n"
                    "data\n"
                    '<t123_invoke_action agent="agent1" action="action1">\n'
                    '<t123_parameter name="param1">value1</t123_parameter>\n'
                    "</t123_invoke_action>",
                    "streaming": True,
                    "first_chunk": False,
                    "last_chunk": False,
                    "response_uuid": "1234",
                    "check_reasoning": False,
                },
            ],
        )

    def test_verify_matching_tag_prefix(self):
        """Test the component with a matching tag prefix"""

        def validation_func(output_data, _output_message, _input_message):
            self.assertEqual(
                output_data,
                [
                    [
                        {
                            "text": "Hello\n",
                            "chunk": "Hello\n",
                            "streaming": True,
                            "first_chunk": True,
                            "last_chunk": True,
                            "uuid": "1234-0",
                        },
                        {
                            "status_update": True,
                            "streaming": True,
                            "text": "Things are now complete",
                            "uuid": "1234-status",
                        },
                    ]
                ],
            )

        run_component_test(
            "src.orchestrator.components.orchestrator_streaming_output_component",
            validation_func,
            input_data={
                "content": strip_lines(
                    """
                    <t321_reasoning>
                    This is some reasoning
                    </t321_reasoning>
                    <t321_current_subject starting_id="123"/>
                    Hello
                    <t321_status_update>Things are underway</t321_status_update>
                    <t321_invoke_action agent="agent1" action="action1">
                    <t321_parameter name="param1">value1</t321_parameter>
                    <t321_parameter name="param2">
                    value2
                    </t321_parameter>
                    </t321_invoke_action>
                    <t321_status_update>
                    Things are now complete
                    </t321_status_update>
                    """
                ),
                "streaming": True,
                "first_chunk": True,
                "last_chunk": True,
                "response_uuid": "1234",
            },
        )

    def test_strip_after_invoke_action(self):
        """Test that all text is ignored after the <t321_invoke_action> tag"""

        def validation_func(output_data, _output_message, _input_message):
            self.assertEqual(
                output_data,
                [
                    [
                        {
                            "text": "Hello\n",
                            "chunk": "Hello\n",
                            "streaming": True,
                            "first_chunk": True,
                            "last_chunk": True,
                            "uuid": "1234-0",
                        },
                        {
                            "status_update": True,
                            "streaming": True,
                            "text": "Things are now complete",
                            "uuid": "1234-status",
                        },
                    ]
                ],
            )

        run_component_test(
            "src.orchestrator.components.orchestrator_streaming_output_component",
            validation_func,
            input_data={
                "content": strip_lines(
                    """
                    <t321_reasoning>
                    This is some reasoning
                    </t321_reasoning>
                    <t321_current_subject starting_id="123"/>
                    Hello
                    <t321_status_update>Things are underway</t321_status_update>
                    <t321_invoke_action agent="agent1" action="action1">
                    <t321_parameter name="param1">value1</t321_parameter>
                    <t321_parameter name="param2">
                    value2
                    </t321_parameter>
                    </t321_invoke_action>
                    <t321_status_update>
                    Things are now complete
                    </t321_status_update>
                    This should be ignored
                    """
                ),
                "streaming": True,
                "first_chunk": True,
                "last_chunk": True,
                "response_uuid": "1234",
            },
        )

    def test_strip_file_after_invoke_action(self):
        """Test that all text is ignored after the <t321_invoke_action> tag"""

        def validation_func(output_data, _output_message, _input_message):
            self.assertEqual(
                output_data,
                [
                    [
                        {
                            "text": "Hello\n",
                            "chunk": "Hello\n",
                            "streaming": True,
                            "first_chunk": True,
                            "last_chunk": True,
                            "uuid": "1234-0",
                        },
                        {
                            "status_update": True,
                            "streaming": True,
                            "text": "Things are now complete",
                            "uuid": "1234-status",
                        },
                    ]
                ],
            )

        run_component_test(
            "src.orchestrator.components.orchestrator_streaming_output_component",
            validation_func,
            input_data={
                "content": strip_lines(
                    """
                    <t321_reasoning>
                    This is some reasoning
                    </t321_reasoning>
                    <t321_current_subject starting_id="123"/>
                    Hello
                    <t321_status_update>Things are underway</t321_status_update>
                    <t321_invoke_action agent="agent1" action="action1">
                    <t321_parameter name="param1">value1</t321_parameter>
                    <t321_parameter name="param2">
                    value2
                    </t321_parameter>
                    </t321_invoke_action>
                    <t321_status_update>
                    Things are now complete
                    </t321_status_update>
                    This should be ignored
                    <file name="file1.txt" mime_type="text/plain">
                    <data>My file content</data>
                    </file>
                    """
                ),
                "streaming": True,
                "first_chunk": True,
                "last_chunk": True,
                "response_uuid": "1234",
            },
        )
