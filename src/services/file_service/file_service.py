import importlib
import time
import json
import re
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

from solace_ai_connector.common.log import log

from ...common.time import ONE_DAY, TEN_MINUTES
from ..common import AutoExpiry, AutoExpirySingletonMeta
from .file_manager.bucket_file_manager import BucketFileManager
from .file_manager.volume_file_manager import VolumeFileManager
from .file_manager.memory_file_manager import MemoryFileManager
from .file_manager.file_manager_base import FileManagerBase
from .file_service_constants import FS_PROTOCOL, INDENT_SIZE, DEFAULT_FILE_MANAGER, BLOCK_IGNORE_KEYS, BLOCK_TAG_KEYS, FS_URL_REGEX
from .file_transformations import apply_file_transformations
from .file_utils import starts_with_fs_url
from ...tools.config.runtime_config import get_service_config

FILE_MANAGERS = {
    "bucket": BucketFileManager,
    "volume": VolumeFileManager,
    "memory": MemoryFileManager,
}


class FileServicePermissionError(Exception):
    pass


# FileService class - Manages file storage and retrieval
class FileService(AutoExpiry, metaclass=AutoExpirySingletonMeta):
    file_manager: FileManagerBase

    def __init__(self, config=None, identifier=None) -> None:
        self.identifier = identifier
        self._expiry_thread = None
        config = config or get_service_config("file_service")
        self.service_type = config.get("type", DEFAULT_FILE_MANAGER)
        self.max_time_to_live = config.get("max_time_to_live", ONE_DAY)
        self.expiration_check_interval = config.get(
            "expiration_check_interval", TEN_MINUTES
        )

        if self.service_type not in config.get("config", {}):
            raise ValueError(
                f"Missing configuration for file service type: {self.service_type}"
            )
        self.service_config = config.get("config").get(self.service_type)

        if self.service_type not in FILE_MANAGERS and not self.service_config.get(
            "module_path"
        ):
            raise ValueError(
                f"Unsupported file service type: {self.service_type}. No module_path provided."
            )

        if self.service_type in FILE_MANAGERS:
            # Load built-in history provider
            self.file_manager = FILE_MANAGERS[self.service_type](
                self.service_config, self.max_time_to_live
            )
        else:
            try:
                # Load the provider from the module path
                module_name = self.service_type
                module_path = self.service_config.get("module_path")
                module = importlib.import_module(module_path, package=__package__)
                manager_class = getattr(module, module_name)
                if not issubclass(manager_class, FileManagerBase):
                    raise ValueError(
                        f"Provided class {manager_class} does not inherit from FileManagerBase"
                    )
                self.file_manager = manager_class(
                    self.service_config, self.max_time_to_live
                )
            except Exception as e:
                raise ImportError("Unable to load component: " + str(e)) from e

        # Start the background thread for auto-expiry
        self._start_auto_expiry_thread(self.expiration_check_interval)

    def _delete_expired_items(self):
        """Checks all files and deletes those that have exceeded max_time_to_live."""
        all_files_metadata = self.file_manager.list_all_metadata()
        current_time = time.time()
        for metadata in all_files_metadata:
            current_time = time.time()
            expiration_timestamp = metadata["expiration_timestamp"]

            if current_time > expiration_timestamp:
                try:
                    filename, _ = self.get_parsed_url(metadata["url"])
                    self.file_manager.delete_by_name(filename)
                    log.info(
                        f"Deleted expired file: {metadata['url']} {current_time} > {expiration_timestamp}"
                    )
                except FileNotFoundError:
                    log.warning(f"File not found: {metadata['url']}")
                except Exception as e:
                    log.error(
                        f"Failed to delete expired file: {metadata['url']} with error: {e}"
                    )

    def _validate_file_url(self, file_url: str):
        if not starts_with_fs_url(file_url):
            raise ValueError(
                f"Invalid URL format. URL must start with '{FS_PROTOCOL}://'"
            )

    def list_all_metadata(self, session_id: str):
        all_files_metadata = self.file_manager.list_all_metadata()
        return [
            metadata
            for metadata in all_files_metadata
            if metadata.get("session_id") == session_id
        ]
        

    def validate_access_permission(
        self, filename: str, session_id: str, return_metadata=False
    ):
        if not session_id:
            raise ValueError("Invalid session ID used for accessing file")
        metadata = self.file_manager.get_metadata(filename)
        if metadata.get("session_id") != session_id:
            raise FileServicePermissionError(f"Access denied to file: {filename}")
        current_time = time.time()
        if current_time > metadata.get("expiration_timestamp"):
            raise FileServicePermissionError(f"File has expired: {filename}")
        if return_metadata:
            return metadata

    def get_parsed_url(self, file_url: str):
        self._validate_file_url(file_url)

        if file_url.startswith("<url>") and file_url.endswith("</url>"):
            file_url = file_url[5:-6].strip()

        # Parse the URL into its components
        url_parts = urlparse(file_url)

        filename = url_parts[1]

        # Get the query parameters
        query = dict(parse_qsl(url_parts[4]))
        return filename, query

    def upload_from_buffer(
        self,
        buffer: bytes,
        file_name: str,
        session_id: str,
        **kwargs,
    ) -> dict:
        """
        Upload a file from a buffer.
        kwargs are added to metadata
        kwargs are over-written by default metadata if they have the same key.
        The official support kwargs are:
        - schema_yaml: str
        - shape: str
        - data_source: str
        """
        if type(buffer) == str:
            buffer = buffer.encode("utf-8")
        elif type(buffer) != bytes:
            raise ValueError("Invalid buffer type. Expected bytes or string.")

        return self.file_manager.upload_from_buffer(
            buffer,
            file_name,
            session_id=session_id,
            **kwargs,
        )

    def upload_from_file(self, file_path: str, session_id: str, **kwargs) -> dict:
        """
        Upload a file from a file path.
        kwargs are added to metadata
        kwargs are over-written by default metadata if they have the same key.
        The official support kwargs are:
        - schema_yaml: str
        - shape: str
        - data_source: str
        """
        return self.file_manager.upload_from_file(
            file_path, session_id=session_id, **kwargs
        )

    def get_metadata(self, file_url: str) -> dict:
        """
        Get metadata from a file URL.
        """
        filename, _ = self.get_parsed_url(file_url)
        return self.file_manager.get_metadata(filename)

    def download_to_buffer(self, file_url: str, session_id: str) -> bytes:
        """
        Download a file to a buffer.
        """
        filename, _ = self.get_parsed_url(file_url)
        self.validate_access_permission(filename, session_id)
        return self.file_manager.download_to_buffer(filename)

    def download_to_file(self, file_url: str, destination_path: str, session_id: str):
        """
        Download a file to a destination path.
        """
        filename, _ = self.get_parsed_url(file_url)
        self.validate_access_permission(filename, session_id)
        return self.file_manager.download_to_file(filename, destination_path)

    def delete_by_url(self, file_url: str):
        """
        Delete a file by URL.
        """
        filename, _ = self.get_parsed_url(file_url)
        return self.file_manager.delete_by_name(filename)
    
    def update_file_expiration(self, file_url: str, expiration_timestamp: float):
        """
        Update the expiration timestamp for a file.
        """
        filename, _ = self.get_parsed_url(file_url)
        return self.file_manager.update_file_expiration(filename, expiration_timestamp)

    def get_file_block_by_url(self, file_url: str) -> str:
        """
        Get file block LLM by URL in a format understandable by the LLM.
        """
        metadata = self.get_metadata(file_url)
        return self.get_file_block_by_metadata(metadata)

    @staticmethod
    def get_file_block_by_metadata(metadata: dict, tag_prefix: str = "") -> str:
        """
        Get file block LLM by metadata in a format understandable by the LLM.
        """
        block = ""
        head = f"<{tag_prefix}file "
        tail = f"\n</{tag_prefix}file>"
        body = ""
        tags = ""

        def indent(text: str, size=INDENT_SIZE) -> str:
            space = " " * size
            return space + f"\n{space}".join(text.split("\n")).strip()

        for key, value in metadata.items():
            if key in BLOCK_IGNORE_KEYS or key in BLOCK_TAG_KEYS or value is None:
                continue
            tags += f'{key}="{value}" '

        if "url" in metadata and metadata["url"]:
            if metadata["url"].startswith(FS_PROTOCOL):
                body += f'<url>\n{indent(metadata["url"])}\n</url>\n'
            else:
                tags += f'url="{metadata["url"]}" '

        for key in BLOCK_TAG_KEYS:
            if key in metadata and metadata[key] is not None:
                tag = key.replace("_", "-")
                body += f"<{tag}>\n{indent(metadata[key])}\n</{tag}>\n"

        if body:
            block = head + tags + ">\n" + indent(body) + tail
        else:
            block = head + tags + "/>"

        return block

    def resolve_url(self, file_url, session_id: str, return_extra=False) -> bytes | str:
        """
        Resolve a URL to its actual file URL and applies the necessary transformations (from query parameters)

        Parameters:
        - file_url (str): The URL to resolve.
        - return_extra (bool): Whether to return original file content and metadata along with the resolved URL.

        Returns:
        - bytes|str: The resolved file content. Applies query transformations if any.
        """
        filename, queries = self.get_parsed_url(file_url)
        file_metadata = self.validate_access_permission(
            filename, session_id, return_metadata=True
        )
        file_bytes = self.file_manager.download_to_buffer(filename)
        if return_extra:
            return (
                apply_file_transformations(file_bytes, file_metadata, queries),
                file_bytes,
                file_metadata,
            )
        return apply_file_transformations(file_bytes, file_metadata, queries)

    def resolve_all_resolvable_urls(
        self, text: str, session_id: str, forceResolve=False
    ) -> str:
        """
        Resolve all resolvable URLs in a text

        Parameters:
        - text (str): The text to resolve URLs in.
        - forceResolve (bool): Whether to force resolve all URLs (if false, only URLs with 'resolve' query parameter set to True will be resolved).
        """
        cache = {}

        if not session_id:
            raise ValueError("Invalid session ID used for resolving URLs")

        def replace_url(match):
            raw_url = match.group()
            url = FileService._clean_url(raw_url)
            try:
                filename, queries = self.get_parsed_url(url)

                resolvable = queries.get("resolve", False)
                resolvable = (
                    resolvable
                    if isinstance(resolvable, bool)
                    else resolvable.lower() == "true"
                )
                if not resolvable and not forceResolve:
                    return raw_url

                if filename in cache:
                    metadata = cache[filename][0]
                    file_bytes = cache[filename][1]
                else:
                    metadata = self.validate_access_permission(
                        filename, session_id, return_metadata=True
                    )
                    file_bytes = self.file_manager.download_to_buffer(filename)
                    cache[filename] = (metadata, file_bytes)

                response = apply_file_transformations(file_bytes, metadata, queries)
                # Convert type to string
                if type(response) == bytes:
                    response = response.decode("utf-8", "ignore")
                elif type(response) == str:
                    pass
                else:
                    response = json.dumps(response)
                # If initial URl was in quotes, return the response in quotes
                if raw_url.startswith('"') or raw_url.startswith("'"):
                    response = f"{raw_url[0]}{response}"

                if raw_url.endswith('"') or raw_url.endswith("'"):
                    response = f"{response}{raw_url[-1]}"
                elif raw_url.endswith("',") or raw_url.endswith('",'):
                    response = f"{response}{''.join(raw_url[-2:])}"
                # If initial URL ends with a comma, return the response with a comma
                elif raw_url.endswith(","):
                    response = f"{response},"
                return response
            except FileServicePermissionError as e:
                raise e
            except Exception as e:
                log.error(f"Failed to resolve URL: {raw_url} with error: {e}")
                raise e

        return re.sub(FS_URL_REGEX, replace_url, text)

    @staticmethod
    def get_urls_from_text(text: str) -> list:
        """
        Get all file URLs from a file block or text
        """
        urls = []

        def append_url(match):
            raw_url = match.group()
            url = FileService._clean_url(raw_url)
            urls.append(url)
            return raw_url

        re.sub(FS_URL_REGEX, append_url, text)
        return urls

    @staticmethod
    def _clean_url(url: str) -> str:
        """
        Clean up a URL by removing any extra characters
        """
        url = url.strip()
        if url.endswith(","):
            url = url[:-1]
        if url.startswith('"') or url.startswith("'"):
            url = url[1:]
        if url.startswith("<url>"):
            url = url[5:-6].strip()
        if url.endswith('"') or url.endswith("'") or url.endswith(","):
            url = url[:-1]
        if url.endswith(")"):
            open_parenthesis_count = url.count("(")
            close_parenthesis_count = url.count(")")
            if close_parenthesis_count > open_parenthesis_count:
                url = url[:-1]
        return url

    @staticmethod
    def get_query_params_from_url(url: str) -> dict:
        """
        Get query parameters from a URL
        """
        # Parse the URL into its components
        url_parts = urlparse(url)

        # Get the query parameters
        query = dict(parse_qsl(url_parts[4]))
        return query

    @staticmethod
    def add_query_params_to_url(url, params):
        """
        Add query parameters to a URL
        """
        # Parse the URL into its components
        url_parts = list(urlparse(url))

        # Get existing query parameters and update them with the new params
        query = dict(parse_qsl(url_parts[4]))
        query.update(params)

        queries = {}
        for key, value in query.items():
            if type(value) == str:
                queries[key] = value
            else:
                queries[key] = json.dumps(value)

        # Encode updated query parameters back into the URL
        url_parts[4] = urlencode(queries)

        # Rebuild the URL with the updated query string
        return urlunparse(url_parts)
