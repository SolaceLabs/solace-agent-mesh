# tests to verify that the action_manager.py file is working as expected:
import unittest

from src.common.utils import (
    parse_file_content,
    parse_orchestrator_response,
    strip_text_after_invoke_action,
)


class TestParser(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def test_parse_file_content_with_url(self):
        data = """<file name="numbers_1_to_10.csv" mime_type="text/csv" size="20">
<url>
amfs://file/numbers_1_to_10.csv
</url>
</file>"""
        result = parse_file_content(data)
        expected_dict = {
            "data": "",
            "url": "amfs://file/numbers_1_to_10.csv",
            "mime_type": "text/csv",
            "name": "numbers_1_to_10.csv",
        }
        self.assertEqual(result, expected_dict)

    def test_parse_file_content_with_csv_data(self):
        data = """<file name="numbers_1_to_10.csv" mime_type="text/csv" size="20">
<data>number
1
2
3
4
5
6
7
8
9
10</data>
</file>"""
        result = parse_file_content(data)
        expected_dict = {
            "data": "number\n1\n2\n3\n4\n5\n6\n7\n8\n9\n10",
            "url": "",
            "mime_type": "text/csv",
            "name": "numbers_1_to_10.csv",
        }
        self.assertEqual(result, expected_dict)

    def test_parse_file_content_with_csv_data_with_tags(self):
        tp = "a123"
        data = f"""<{tp}file name="numbers_1_to_10.csv" mime_type="text/csv" size="20">
<data>number
1
2
3
4
5
6
7
8
9
10</data>
</{tp}file>"""
        result = parse_file_content(data)
        expected_dict = {
            "data": "number\n1\n2\n3\n4\n5\n6\n7\n8\n9\n10",
            "url": "",
            "mime_type": "text/csv",
            "name": "numbers_1_to_10.csv",
        }
        self.assertEqual(result, expected_dict)

    def test_parse_orchestrator_response(self):
        data = """<t628_reasoning>
- User wants a CSV file with numbers from 1 to 10
- We can create this simple file directly without using any specific agent
- We'll use the file creation feature to generate the CSV
- The file will be small, so we can include the data directly
</t628_reasoning>
<t628_current_subject starting_id="1"/>
Certainly! I'll create a CSV file containing the numbers from 1 to 10 for you. Here's the file:
<t628_file name="numbers_1_to_10.csv" mime_type="text/csv" size="20">
<data>number
1
2
3
4
5
6
7
8
9
10</data>
</t628_file>
I've created a CSV file named "numbers_1_to_10.csv" with a single column labeled "number" containing the values from 1 to 10. You can now download and use this file as needed. """
        result = parse_orchestrator_response(data)
        expected_dict = {
            "actions": [],
            "current_subject_starting_id": "1",
            "errors": [],
            "reasoning": "- User wants a CSV file with numbers from 1 to 10\n- We can create this simple file directly without using any specific agent\n- We'll use the file creation feature to generate the CSV\n- The file will be small, so we can include the data directly",
            "status_updates": [],
            "send_last_status_update": False,
            "content": [
                {
                    "type": "text",
                    "body": "Certainly! I'll create a CSV file containing the numbers from 1 to 10 for you. Here's the file:\n",
                },
                {
                    "type": "file",
                    "body": {
                        "data": "number\n1\n2\n3\n4\n5\n6\n7\n8\n9\n10",
                        "url": "",
                        "mime_type": "text/csv",
                        "name": "numbers_1_to_10.csv",
                    },
                },
                {
                    "type": "text",
                    "body": 'I\'ve created a CSV file named "numbers_1_to_10.csv" with a single column labeled "number" containing the values from 1 to 10. You can now download and use this file as needed. ',
                },
            ],
        }

        self.assertEqual(result, expected_dict)

    def test_strip_text_after_invoke_action_no_tag(self):
        text = "This is some text without any invoke action."
        result = strip_text_after_invoke_action(text)
        self.assertEqual(result, text)

    def test_strip_text_after_invoke_action_single_tag(self):
        text = "Some text before <t123_invoke_action agent='test' action='do'></t123_invoke_action> and some text after."
        expected = "Some text before <t123_invoke_action agent='test' action='do'></t123_invoke_action>"
        result = strip_text_after_invoke_action(text)
        self.assertEqual(result, expected)

    def test_strip_text_after_invoke_action_multiple_tags(self):
        text = "First action <t1_invoke_action></t1_invoke_action> then some text. Second action <t2_invoke_action></t2_invoke_action> and final text."
        expected = "First action <t1_invoke_action></t1_invoke_action> then some text. Second action <t2_invoke_action></t2_invoke_action>"
        result = strip_text_after_invoke_action(text)
        self.assertEqual(result, expected)

    def test_strip_text_after_invoke_action_tag_at_end(self):
        text = "Some text ending with an action <t99_invoke_action></t99_invoke_action>"
        expected = (
            "Some text ending with an action <t99_invoke_action></t99_invoke_action>"
        )
        result = strip_text_after_invoke_action(text)
        self.assertEqual(result, expected)

    def test_strip_text_after_invoke_action_multiline(self):
        text = """Some text.
<t1_invoke_action agent='a' action='b'></t1_invoke_action>
More text.
<t2_invoke_action agent='c' action='d'></t2_invoke_action>
Final line of text."""
        expected = """Some text.
<t1_invoke_action agent='a' action='b'></t1_invoke_action>
More text.
<t2_invoke_action agent='c' action='d'></t2_invoke_action>"""
        result = strip_text_after_invoke_action(text)
        self.assertEqual(result, expected)
