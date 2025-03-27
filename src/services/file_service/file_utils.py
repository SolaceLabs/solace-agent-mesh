# Add utility functions for upload CSV that automatically creates the number of row and data types
import csv
from typing import Tuple, Union
import json

from .file_service_constants import FS_PROTOCOL, INDENT_SIZE


class Types:
    """
    Type constants definition to be used when representing the schema.
    """

    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    STR = "str"
    ARRAY = "array"
    OBJECT = "object"
    NULL = "null"

    @property
    def PRIMITIVES():
        return [Types.INT, Types.FLOAT, Types.BOOL, Types.STR]


def get_str_type(value: str) -> str:
    """
    Get the type of a string value.

    Parameters:
    - value (str): The string value.

    Returns:
    - str: The type of the value.
    """
    if not value:
        return Types.NULL
    if value.isdigit():
        return Types.INT
    elif value.replace(".", "", 1).isdigit():
        return Types.FLOAT
    else:
        return Types.STR


def convert_dict_to_yaml(schema: dict, indent_size=INDENT_SIZE, _level=0) -> str:
    """
    Convert a dictionary schema to a YAML string.

    Parameters:
    - schema (dict): The dictionary schema.

    Returns:
    - str: The YAML string.
    """
    yaml_str = ""
    indent = indent_size * _level

    for key, value in schema.items():
        if isinstance(value, dict):
            value_str = convert_dict_to_yaml(value, indent_size, _level + 1)
            yaml_str += f"{space(indent)}{key}:\n{value_str}\n"
        else:
            yaml_str += f"{space(indent)}{key}: {value}\n"
    return yaml_str.rstrip()


def space(size=INDENT_SIZE):
    """
    Get a string of spaces.
    """
    if size == 0:
        return ""
    return " " * size


def extract_csv_schema_and_shape(csv_file: Union[str, bytes]) -> Tuple[dict, Tuple[int, int]]:
    """
    Get the schema and shape of a CSV file.

    Parameters:
    - csv_file (str): The CSV file content.
    - header_row (str): The header row of the CSV file.

    Returns:
    - str: The schema of the CSV file.
    - st: The shape of the CSV file.
    """
    if type(csv_file) == bytes:
        csv_file = csv_file.decode("utf-8")

    # Parse the CSV string
    csv_lines = csv_file.splitlines()
    csv_reader = csv.DictReader(csv_lines)
    columns = csv_reader.fieldnames
    listed_csv = list(csv_reader)
    shape = (len(listed_csv), len(columns))
    schema = {}
    for col in columns:
        # deriving type from the top 10 rows
        col_type = None
        for i, row in enumerate(listed_csv):
            if i >= 10:
                break
            curr_type = get_str_type(row[col])
            if col_type is None:
                col_type = curr_type
            elif col_type != curr_type:
                # multiple types, set as str
                col_type = Types.STR
                break
        schema[col] = {"type": col_type}

    return schema, shape


def dict_to_schema(input_dict: dict) -> dict:
    """
    Convert a dictionary to a JSON schema.

    Parameters:
    - input_dict (dict): The input dictionary.

    Returns:
    - dict: The JSON schema.
    """

    def infer_type(value):
        if isinstance(value, str):
            return Types.STR
        elif isinstance(value, int):
            return Types.INT
        elif isinstance(value, float):
            return Types.FLOAT
        elif isinstance(value, bool):
            return Types.BOOL
        elif isinstance(value, list):
            if len(value) > 0:
                return {"type": Types.ARRAY, "items": infer_type(value[0])}
            else:
                return {"type": Types.ARRAY, "items": {}}
        elif isinstance(value, dict):
            return {"type": Types.OBJECT, "properties": infer_properties(value)}
        else:
            return Types.NULL

    def infer_properties(input_dict):
        return {
            key: (
                {"type": infer_type(value)}
                if isinstance(infer_type(value), str)
                else infer_type(value)
            )
            for key, value in input_dict.items()
        }

    if type(input_dict) is list:
        input_dict = input_dict[0]
        json_schema = {
            "type": Types.ARRAY,
            "items": {"type": Types.OBJECT, "properties": infer_properties(input_dict)},
        }
    else:
        json_schema = {"type": Types.OBJECT, "properties": infer_properties(input_dict)}

    return json_schema


def get_dict_array_shape(
    data: Union[dict, list], max_level=2, _path="", _result=None, _level=0
):
    """
    Get the count of each array in a dictionary schema.
    """
    if _result is None:
        _result = []

    # If it's a list, record its length and traverse each element
    if isinstance(data, list):
        if _path:
            _result.append([_path, len(data)])
        else:
            _result.append(["top level", len(data)])
        if _level < max_level:
            get_dict_array_shape(data[0], max_level, f"{_path}[*]", _result, _level + 1)

    # If it's a dictionary, traverse each key-value pair
    elif isinstance(data, dict):
        for key, value in data.items():
            new_path = f"{_path}.{key}" if _path else key
            if _level < max_level:
                get_dict_array_shape(value, max_level, new_path, _result, _level + 1)

    return _result


def get_csv_schema_and_shape(schema: dict, shape: Tuple[int, int]) -> Tuple[str, str]:
    """
    Get the formatted schema and shape of a CSV file.

    Parameters:
    - schema (dict): The schema of the CSV file.
    - shape (Tuple[int, int]): The shape of the CSV file.

    Returns:
    - str: The formatted schema of the CSV file.
    - Tuple[int, int]: The shape of the CSV file.
    """
    shape_str = f"{shape[0]} rows x {shape[1]} columns"
    schema_dict = {
        "type": Types.ARRAY,
        "items": {"type": Types.OBJECT, "properties": schema},
    }
    schema_str = convert_dict_to_yaml(schema_dict)
    return schema_str, shape_str


def get_json_schema_and_shape(file: Union[bytes, str]) -> Tuple[str, str]:
    try:
        if type(file) == bytes:
            file = file.decode("utf-8")
        json_data = json.loads(file)
        schema = dict_to_schema(json_data)
        schema_str = convert_dict_to_yaml(schema)
        shape_str = None

        def get_row_text(count):
            return f"{count} elements" if count > 1 else f"{count} element"

        array_lengths = get_dict_array_shape(json_data)
        if array_lengths:
            shape_str = "\n".join(
                [f"{key}: {get_row_text(val)}" for key, val in array_lengths]
            )
        return schema_str, shape_str
    except Exception as e:
        return None, None


def get_file_schema_and_shape(file: bytes, metadata: dict) -> Tuple[str, str]:
    """
    Get the schema and shape of a file.

    Parameters:
    - file (bytes): The file content as bytes.
    - metadata (dict): The file metadata.

    Returns:
    - str: The schema of the file. None if cannot be determined.
    - str: The shape of the file. None if cannot be determined.
    """
    if metadata.get("mime_type") == "text/csv":
        schema, shape = extract_csv_schema_and_shape(file)
        schema_str, shape_str = get_csv_schema_and_shape(schema, shape)
        return schema_str, shape_str
    elif metadata.get("mime_type") == "application/json":
        schema, shape = get_json_schema_and_shape(file)
        return schema, shape
    else:
        return None, None


def recursive_file_resolver(
    obj: Union[dict, str, list],
    resolver: callable,
    session_id: str,
    force_resolve: bool = False,
):
    """
    Recursively resolve all the file URLs in the input data.

    Parameters:
    - obj (dict|str|list): The input data.
    - resolver (callable): The resolver function.
    - session_id (str): The session ID.
    - force_resolve (bool): Resolve all the URLs regardless of the 'resolve' query parameter.

    Returns:
    - dict|str|list: The object with resolved URLs.
    """
    if type(obj) == str:
        return resolver(obj, session_id, force_resolve)

    keys = []
    if type(obj) == list:
        keys = range(len(obj))
    elif type(obj) == dict:
        keys = obj.keys()

    for key in keys:
        if isinstance(obj[key], dict):
            obj[key] = recursive_file_resolver(
                obj[key], resolver, session_id, force_resolve
            )
        elif isinstance(obj[key], list):
            obj[key] = [
                (
                    recursive_file_resolver(item, resolver, session_id, force_resolve)
                    if isinstance(item, dict)
                    else item
                )
                for item in obj[key]
            ]
        elif isinstance(obj[key], str):
            obj[key] = resolver(obj[key], session_id, force_resolve)
    return obj


def starts_with_fs_url(url: str) -> bool:
    """
    Check if the URL starts with the file service protocol.

    Parameters:
    - url (str): The URL.

    Returns:
    - bool: True if the URL starts with the file service protocol.
    """
    return (
        url.startswith(f"{FS_PROTOCOL}://")
        or url.startswith(f"<url>{FS_PROTOCOL}://")
        or url.startswith(f"<url> {FS_PROTOCOL}://")
    )
