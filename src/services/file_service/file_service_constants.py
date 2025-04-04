FS_PROTOCOL = "amfs"
"""
mesh file service protocol.
"""

META_FILE_EXTENSION = ".metadata"
"""
Extension for metadata files.
"""

INDENT_SIZE = 2
"""
Indent size for XML representation.
"""

DEFAULT_FILE_MANAGER = "volume"
"""
Default file manager to use.
"""


BLOCK_IGNORE_KEYS = [
    "session_id",
    "upload_timestamp",
    "url",
]
"""
Keys to ignore from metadata file attribute while generating file block.
"""

BLOCK_TAG_KEYS = [
    "data",
    "schema-yaml",
    "schema_yaml",
    "shape",
    "data-source",
    "data_source",
]
"""
Keys to be treated as tags in the file block, and not file attributes.
"""

FS_URL_REGEX = r"""<url>\s*({protocol}:\/\/.+?)\s*<\/url>|{protocol}:\/\/[^\s\?]+(\s|$)|{protocol}:\/\/[^\n\?]+\?.*?(?=\n|$|>)|\"({protocol}:\/\/[^\"]+?)(\"|\n)|'({protocol}:\/\/[^']+?)('|\n)""".format(
    protocol=FS_PROTOCOL
)
"""
Regex pattern to match FS URLs in a text. \n
Matches if: \n
- Starts with <url> ends with </url>
- Starts with FS_PROTOCOL:// has no ? and ends with space or newline or end of string \n
- Starts with FS_PROTOCOL:// has ? and ends with space or newline or end of string \n
- Starts with "FS_PROTOCOL:// ends with " or newline \n
- Starts with 'FS_PROTOCOL:// ends with ' or newline \n
"""
