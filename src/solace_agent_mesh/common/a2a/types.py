"""
Custom type aliases for the A2A helper layer.
"""
from typing import Union
from a2a.types import TextPart, DataPart, FilePart

# A type alias for the raw content parts of a message or artifact.
# This is the type that application logic should work with, insulating it
# from the SDK's generic `Part` wrapper.
ContentPart = Union[TextPart, DataPart, FilePart]
