import unittest
from time import sleep
import json
import time

from solace_agent_mesh.services.file_service import (
    FileService,
    FS_PROTOCOL,
    Types,
    FileServicePermissionError,
)
from solace_agent_mesh.services.file_service import file_utils

file_manager_config = {
    "type": "memory",
    "max_time_to_live": 86400,
    "expiration_check_interval": 600,
    "config": {"memory": {}},
}

file_manager_expiry_config = {
    "type": "memory",
    "max_time_to_live": 0.5,
    "expiration_check_interval": 0.5,
    "config": {"memory": {}},
}


class TestFileService(unittest.TestCase):

    def test_upload_and_download(self):
        file_service = FileService(file_manager_config)
        file_name = "test_upload_and_download.txt"
        file_content = b"Hello, world!"
        session_id = "test_session_id"
        meta = file_service.upload_from_buffer(file_content, file_name, session_id)
        content = file_service.download_to_buffer(meta["url"], session_id)
        self.assertEqual(content, file_content)

    def test_download_with_invalid_session(self):
        file_service = FileService(file_manager_config)
        file_name = "test_upload_and_download.txt"
        file_content = b"Hello, world!"
        session_id = "test_session_id"
        invalid_session_id = "invalid_session_id"
        meta = file_service.upload_from_buffer(file_content, file_name, session_id)
        with self.assertRaises(FileServicePermissionError):
            file_service.download_to_buffer(meta["url"], invalid_session_id)

    def test_delete(self):
        file_service = FileService(file_manager_config)
        file_name = "test_delete.txt"
        file_content = b"Hello, world!"
        session_id = "test_session_id"
        meta = file_service.upload_from_buffer(file_content, file_name, session_id)
        file_service.delete_by_url(meta["url"])
        with self.assertRaises(FileNotFoundError):
            file_service.download_to_buffer(meta["url"], session_id)

    def test_metadata(self):
        file_service = FileService(file_manager_config)
        file_name = "test_metadata.txt"
        file_content = b"Hello, world!"
        session_id = "test_session_id"
        meta = file_service.upload_from_buffer(file_content, file_name, session_id)
        fetched_meta = file_service.get_metadata(meta["url"])
        self.assertTrue("name" in fetched_meta and fetched_meta["name"] == file_name)
        self.assertTrue(
            "mime_type" in fetched_meta and fetched_meta["mime_type"] == "text/plain"
        )
        self.assertTrue(
            "session_id" in fetched_meta and fetched_meta["session_id"] == session_id
        )
        self.assertTrue(
            "file_size" in fetched_meta
            and fetched_meta["file_size"] == len(file_content)
        )
        self.assertTrue(
            "upload_timestamp" in fetched_meta
            and fetched_meta["upload_timestamp"] is not None
        )
        self.assertTrue(
            "expiration_timestamp" in fetched_meta
            and fetched_meta["expiration_timestamp"] is not None
        )
        self.assertTrue("url" in fetched_meta and fetched_meta["url"] is not None)

    def test_csv_file_metadata_extension(self):
        file_service = FileService(file_manager_config)
        file_name = "test_csv_file_metadata_extension.csv"
        file_content = b"one,two,three\n1,2,3\n4,5,6\n7,8,9\n10,11,12"
        session_id = "test_session_id"
        meta = file_service.upload_from_buffer(file_content, file_name, session_id)
        fetched_meta = file_service.get_metadata(meta["url"])
        self.assertTrue(
            "schema-yaml" in fetched_meta
            and Types.ARRAY in fetched_meta["schema-yaml"]
            and "one" in fetched_meta["schema-yaml"]
            and Types.INT in fetched_meta["schema-yaml"]
        )
        self.assertTrue(
            "shape" in fetched_meta
            and "4" in fetched_meta["shape"]
            and "3" in fetched_meta["shape"]
        )

    def test_metadata_update_file_expiry(self):
        file_service = FileService(file_manager_config)
        file_name = "test_csv_file_metadata_extension.csv"
        file_content = b"one,two,three\n1,2,3\n4,5,6\n7,8,9\n10,11,12"
        session_id = "test_session_id"
        new_expiry = time.time() + 10000
        meta = file_service.upload_from_buffer(file_content, file_name, session_id)
        file_service.update_file_expiration(meta["url"], new_expiry)
        fetched_meta = file_service.get_metadata(meta["url"])
        self.assertTrue(
            "expiration_timestamp" in fetched_meta
            and fetched_meta["expiration_timestamp"] == new_expiry
        )

    def test_upload_with_extra_metadata(self):
        file_service = FileService(file_manager_config)
        file_name = "test_upload_with_extra_metadata.txt"
        file_content = b"Hello, world!"
        session_id = "test_session_id"
        meta = file_service.upload_from_buffer(
            file_content, file_name, session_id, key="value", key2="value2"
        )
        fetched_meta = file_service.get_metadata(meta["url"])
        self.assertTrue("key" in fetched_meta and fetched_meta["key"] == "value")
        self.assertTrue("key2" in fetched_meta and fetched_meta["key2"] == "value2")

    def test_get_parsed_url(self):
        file_service = FileService(file_manager_config)
        test_table = [
            [
                f"{FS_PROTOCOL}://random-filename.ext?query=value",
                "random-filename.ext",
                {"query": "value"},
            ],
            [
                f"{FS_PROTOCOL}://random-filename.ext?query=value&query2=value2",
                "random-filename.ext",
                {"query": "value", "query2": "value2"},
            ],
            [f"{FS_PROTOCOL}://random-filename.ext", "random-filename.ext", {}],
        ]
        for url, expectedName, expectedQueries in test_table:
            filename, queries = file_service.get_parsed_url(url)
            self.assertEqual(filename, expectedName)
            self.assertEqual(queries, expectedQueries)

        # validate URL
        with self.assertRaises(ValueError):
            file_service.get_parsed_url("invalid-url")

    def test_file_with_spaces(self):
        file_service = FileService(file_manager_config)
        file_name = "test file with spaces.txt"
        file_content = b"Hello, world!"
        session_id = "test_session_id"
        meta = file_service.upload_from_buffer(file_content, file_name, session_id)
        cleaned_name = "test_file_with_spaces.txt"
        self.assertIn(cleaned_name, meta["url"])

    def test_file_with_spaces_and_special_chars(self):
        file_service = FileService(file_manager_config)
        file_name = "test file with spaces & special chars?*&.txt"
        file_content = b"Hello, world!"
        session_id = "test_session_id"
        meta = file_service.upload_from_buffer(file_content, file_name, session_id)
        cleaned_name = "test_file_with_spaces_special_chars_"
        self.assertIn(cleaned_name, meta["url"])

    def test_file_with_spaces_and_unicode_chars(self):
        file_service = FileService(file_manager_config)
        file_name = "test file\u202Fwith spaces & unicode chars 😊.txt"
        file_content = b"Hello, world!"
        session_id = "test_session_id"
        meta = file_service.upload_from_buffer(file_content, file_name, session_id)
        cleaned_name = "test_file_with_spaces_unicode_chars_.txt"
        self.assertIn(cleaned_name, meta["url"])

    def test_auto_expiry(self):
        file_service = FileService(file_manager_expiry_config, identifier="fs-expiry")
        file_name = "test_auto_expiry.txt"
        file_content = b"Hello, world!"
        session_id = "test_session_id"
        meta = file_service.upload_from_buffer(file_content, file_name, session_id)
        content = file_service.download_to_buffer(meta["url"], session_id)
        self.assertEqual(content, file_content)
        sleep(1)
        with self.assertRaises(FileNotFoundError):
            file_service.download_to_buffer(meta["url"], session_id)


class TestFileServiceRegex(unittest.TestCase):

    def test_simple_url(self):
        text = f"https://file_name.csv"
        result = FileService.get_urls_from_text(text)
        expected = []
        self.assertEqual(result, expected)

    def test_non_url_text(self):
        text = "a non url normal english piece of text"
        result = FileService.get_urls_from_text(text)
        expected = []  # Assuming no match for a regular text without a URL
        self.assertEqual(result, expected)

    def test_simple_amfs_url(self):
        text = f"{FS_PROTOCOL}://random-filename.ext"
        result = FileService.get_urls_from_text(text)[0]
        expected = text
        self.assertEqual(result, expected)

    def test_amfs_url_with_query_params(self):
        text = f"{FS_PROTOCOL}://random-filename.ext?col=yes&row=3"
        result = FileService.get_urls_from_text(text)[0]
        expected = text
        self.assertEqual(result, expected)

    def test_url_in_string_with_assignment(self):
        text = "url=amfs://random-filename.ext"
        result = FileService.get_urls_from_text(text)[0]
        expected = f"{FS_PROTOCOL}://random-filename.ext"
        self.assertEqual(result, expected)

    def test_url_in_double_quotes(self):
        text = f'<file url="{FS_PROTOCOL}://random-filename.ext" size="120" /file>'
        result = FileService.get_urls_from_text(text)[0]
        expected = f"{FS_PROTOCOL}://random-filename.ext"
        self.assertEqual(result, expected)

    def test_url_in_single_quotes(self):
        text = f"<file url='{FS_PROTOCOL}://random-filename.ext' size='120' /file>"
        result = FileService.get_urls_from_text(text)[0]
        expected = f"{FS_PROTOCOL}://random-filename.ext"
        self.assertEqual(result, expected)

    def test_url_in_file_tag_with_query_params(self):
        text = f'<file url="{FS_PROTOCOL}://random-filename.ext?col=yes&row=3" size="120" /file>'
        result = FileService.get_urls_from_text(text)[0]
        expected = f"{FS_PROTOCOL}://random-filename.ext?col=yes&row=3"
        self.assertEqual(result, expected)

    def test_url_in_file_tag_with_query_params_with_quote(self):
        text = f'<file url="{FS_PROTOCOL}://random-filename.ext?jq=.keyA | length" size="120" </file>'
        result = FileService.get_urls_from_text(text)[0]
        expected = f"{FS_PROTOCOL}://random-filename.ext?jq=.keyA | length"
        self.assertEqual(result, expected)

    def test_url_with_url_tag(self):
        text = f"this is a test <url>{FS_PROTOCOL}://random-filename.ext?jq=.keyA | length</url> which just ended"
        result = FileService.get_urls_from_text(text)[0]
        expected = f"{FS_PROTOCOL}://random-filename.ext?jq=.keyA | length"
        self.assertEqual(result, expected)

    def test_url_in_file_tag_with_query_params_with_space(self):
        text = f"<file url=\"{FS_PROTOCOL}://random-filename.ext?columns=['one', 'two']\" size=\"120\" /file>"
        result = FileService.get_urls_from_text(text)[0]
        expected = f"{FS_PROTOCOL}://random-filename.ext?columns=['one', 'two']"
        self.assertEqual(result, expected)

    def test_url_with_metadata(self):
        text = f'<file file_name="kitty.jpg" mime_type="image/jpeg" url="{FS_PROTOCOL}://f56e454c-4bc7-4307-8fed-d90009fae2f6_kitty.jpg?columns=[\'one\', \'two\', \'three\']&sorted=True&first=10" downloadable="true" >'
        result = FileService.get_urls_from_text(text)[0]
        expected = f"{FS_PROTOCOL}://f56e454c-4bc7-4307-8fed-d90009fae2f6_kitty.jpg?columns=['one', 'two', 'three']&sorted=True&first=10"
        self.assertEqual(result, expected)

    def test_url_inside_url_tags(self):
        text = f"<url> {FS_PROTOCOL}://f56e454c-4bc7-4307-8fed-d90009fae2f6_kitty.jpg?columns=['one', 'two', 'three']&sorted=True&first=10 </url>"
        result = FileService.get_urls_from_text(text)[0]
        expected = f"{FS_PROTOCOL}://f56e454c-4bc7-4307-8fed-d90009fae2f6_kitty.jpg?columns=['one', 'two', 'three']&sorted=True&first=10"
        self.assertEqual(result, expected)

    def test_multiline_url_inside_url_tags(self):
        text = f"<url>\n{FS_PROTOCOL}://f56e454c-4bc7-4307-8fed-d90009fae2f6_kitty.jpg?columns=['one', 'two', 'three']&sorted=True&first=10\n</url>"
        result = FileService.get_urls_from_text(text)[0]
        expected = f"{FS_PROTOCOL}://f56e454c-4bc7-4307-8fed-d90009fae2f6_kitty.jpg?columns=['one', 'two', 'three']&sorted=True&first=10"
        self.assertEqual(result, expected)

    def test_multiple_urls(self):
        text = f"""<file schema="None" file_name="kitty.jpg" mime_type="image/jpeg" >
  <url>
    {FS_PROTOCOL}://3b416917-28fa-4574-b459-7fd111704717_kitty.jpg?columns=['one', 'two', 'three']&sorted=True&first=10
  </url>
  <schema-yaml>
    columns:
      - one
      - two
      - three
  </schema-yaml>
  <data>
    {FS_PROTOCOL}://5eb57ccb-65d3-42de-91d2-d522ef057fd5_chart_data.csv
  </data>
</file>"""
        results = FileService.get_urls_from_text(text)
        self.assertEqual(len(results), 2)
        expected_url = [
            f"{FS_PROTOCOL}://3b416917-28fa-4574-b459-7fd111704717_kitty.jpg?columns=['one', 'two', 'three']&sorted=True&first=10",
            f"{FS_PROTOCOL}://5eb57ccb-65d3-42de-91d2-d522ef057fd5_chart_data.csv",
        ]
        self.assertEqual(results, expected_url)

class TestFileUtils(unittest.TestCase):

    def test_csv_schema_and_shape(self):
        csv = b"integers,floats,strings\n1,1.1,one\n2,2.2,two\n3,3.3,three\n4,4.4,four"
        schema, shape = file_utils.extract_csv_schema_and_shape(csv)
        expected_schema = {
            "integers": {
                "type": Types.INT,
            },
            "floats": {
                "type": Types.FLOAT,
            },
            "strings": {
                "type": Types.STR,
            },
        }
        expected_shape = (4, 3)
        self.assertEqual(schema, expected_schema)
        self.assertEqual(shape, expected_shape)

    def test_csv_str_schema_and_shape(self):
        csv = b"integers,floats,strings\n1,1.1,one\n2,2.2,two\n3,3.3,three\n4,4.4,four"
        schema, shape = file_utils.extract_csv_schema_and_shape(csv)
        str_schema, str_shape = file_utils.get_csv_schema_and_shape(schema, shape)
        expected_schema = (
            f"type: {Types.ARRAY}\n"
            "items:\n"
            f"  type: {Types.OBJECT}\n"
            "  properties:\n"
            "    integers:\n"
            f"      type: {Types.INT}\n"
            "    floats:\n"
            f"      type: {Types.FLOAT}\n"
            "    strings:\n"
            f"      type: {Types.STR}"
        )
        expected_shape = f"4 rows x 3 columns"
        self.assertEqual(str_schema, expected_schema)
        self.assertEqual(str_shape, expected_shape)

    def test_dict_to_schema(self):
        json_dict = [
            {
                "name": "John",
                "age": 30,
                "is_student": False,
                "addresses": [
                    {
                        "city": "New York",
                        "zipcode": "10001",
                        "grades": [85.5, 90],
                    },
                    {
                        "city": "Los Angeles",
                        "zipcode": "90001",
                        "grades": [85.5, 90],
                    },
                ],
            }
        ]
        expected_json = {
            "type": Types.ARRAY,
            "items": {
                "type": Types.OBJECT,
                "properties": {
                    "name": {"type": Types.STR},
                    "age": {"type": Types.INT},
                    "is_student": {"type": Types.INT},
                    "addresses": {
                        "type": Types.ARRAY,
                        "items": {
                            "type": Types.OBJECT,
                            "properties": {
                                "city": {"type": Types.STR},
                                "zipcode": {"type": Types.STR},
                                "grades": {"type": Types.ARRAY, "items": Types.FLOAT},
                            },
                        },
                    },
                },
            },
        }
        schema = file_utils.dict_to_schema(json_dict)
        self.assertEqual(schema, expected_json)

    def test_get_dict_array_shape_list(self):
        json_dict = [
            {
                "name": "John",
                "age": 30,
                "numbers": [1, 2, 3],
                "addresses": [
                    {
                        "city": "New York",
                        "zipcode": "10001",
                        "grades": [85.5, 90],
                    },
                    {
                        "city": "Los Angeles",
                        "zipcode": "90001",
                        "grades": [85.5, 90],
                    },
                ],
            }
        ]
        shape_limited = file_utils.get_dict_array_shape(json_dict)
        shape_unlimited = file_utils.get_dict_array_shape(json_dict, 10)
        expected_shape_limited = [
            ["top level", 1],
            ["[*].numbers", 3],
            ["[*].addresses", 2],
        ]
        expected_shape_unlimited = [
            ["top level", 1],
            ["[*].numbers", 3],
            ["[*].addresses", 2],
            ["[*].addresses[*].grades", 2],
        ]
        self.assertEqual(shape_limited, expected_shape_limited)
        self.assertEqual(shape_unlimited, expected_shape_unlimited)

    def test_get_dict_array_shape_obj(self):
        json_dict = {
            "name": "John",
            "age": 30,
            "numbers": [1, 2, 3],
            "addresses": [
                {
                    "city": "New York",
                    "zipcode": "10001",
                    "grades": [85.5, 90],
                },
                {
                    "city": "Los Angeles",
                    "zipcode": "90001",
                    "grades": [85.5, 90],
                },
            ],
        }

        shape = file_utils.get_dict_array_shape(json_dict)
        expected_shape = [["numbers", 3], ["addresses", 2]]
        self.assertEqual(shape, expected_shape)

    def test_json_str_schema_and_shape(self):
        json_dict = {
            "name": "John",
            "numbers": [1, 2, 3],
            "myObj": {
                "myArray1": [1, 2, 3],
                "myArray2": [4, 5, 6, 7],
            },
            "addresses": [
                {
                    "city": "New York",
                    "zipcode": "10001",
                    "grades": [85.5, 90],
                },
                {
                    "city": "Los Angeles",
                    "zipcode": "90001",
                    "grades": [85.5, 90],
                },
            ],
        }

        expected_schema = f"""type: {Types.OBJECT}
properties:
  name:
    type: {Types.STR}
  numbers:
    type: {Types.ARRAY}
    items: {Types.INT}
  myObj:
    type: {Types.OBJECT}
    properties:
      myArray1:
        type: {Types.ARRAY}
        items: {Types.INT}
      myArray2:
        type: {Types.ARRAY}
        items: {Types.INT}
  addresses:
    type: {Types.ARRAY}
    items:
      type: {Types.OBJECT}
      properties:
        city:
          type: {Types.STR}
        zipcode:
          type: {Types.STR}
        grades:
          type: {Types.ARRAY}
          items: {Types.FLOAT}"""

        expected_shape = "numbers: 3 elements\nmyObj.myArray1: 3 elements\nmyObj.myArray2: 4 elements\naddresses: 2 elements"

        json_bytes = json.dumps(json_dict).encode("utf-8")
        schema, shape = file_utils.get_json_schema_and_shape(json_bytes)
        self.assertEqual(schema, expected_schema)
        self.assertEqual(shape, expected_shape)


if __name__ == "__main__":
    unittest.main()
