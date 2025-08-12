"""
In-memory implementation of the ADK BaseArtifactService for testing purposes.
"""

from collections import defaultdict
from typing import Dict, List, Optional, Tuple, cast

from google.adk.artifacts import BaseArtifactService
from google.genai import types as adk_types
from typing_extensions import override

_USER_NAMESPACE_KEY = "__USER_NAMESPACE_ARTIFACTS__"


class TestInMemoryArtifactService(BaseArtifactService):
    """
    An in-memory artifact service for testing.

    Stores artifacts in a nested dictionary structure:
    _artifacts_data[app_name][user_id][session_id_or_user_namespace_key][filename_key][version] = (content_bytes, mime_type)
    """

    def __init__(self):
        self._artifacts_data: Dict[
            str, Dict[str, Dict[str, Dict[str, Dict[int, Tuple[bytes, str]]]]]
        ] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
        )

    def _get_path_keys(
        self, app_name: str, user_id: str, session_id: str, filename: str
    ) -> Tuple[str, str, str, str]:
        """
        Determines the effective keys for accessing the artifact storage.
        Returns (app_name, user_id, effective_session_key, filename_key)
        """
        filename_key = filename
        effective_session_key = session_id
        if filename.startswith("user:"):
            filename_key = filename.split(":", 1)[1]
            effective_session_key = _USER_NAMESPACE_KEY
        return app_name, user_id, effective_session_key, filename_key

    @override
    async def save_artifact(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
        filename: str,
        artifact: adk_types.Part,
    ) -> int:
        if not artifact.inline_data or artifact.inline_data.data is None:
            raise ValueError(
                f"Artifact part for '{filename}' has no inline_data to save."
            )

        app_key, user_key, effective_session_key, fn_key = self._get_path_keys(
            app_name, user_id, session_id, filename
        )

        versions_dict = self._artifacts_data[app_key][user_key][effective_session_key][
            fn_key
        ]
        current_versions = list(versions_dict.keys())
        new_version = 0
        if current_versions:
            new_version = max(current_versions) + 1

        content_bytes = artifact.inline_data.data
        mime_type = artifact.inline_data.mime_type or "application/octet-stream"

        versions_dict[new_version] = (content_bytes, mime_type)
        return new_version

    @override
    async def load_artifact(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
        filename: str,
        version: Optional[int] = None,
    ) -> Optional[adk_types.Part]:
        app_key, user_key, effective_session_key, fn_key = self._get_path_keys(
            app_name, user_id, session_id, filename
        )

        versions_dict = self._artifacts_data[app_key][user_key][
            effective_session_key
        ].get(fn_key)
        if not versions_dict:
            return None

        target_version = version
        if target_version is None:
            if not versions_dict:
                return None
            target_version = max(versions_dict.keys()) if versions_dict else -1

        if target_version not in versions_dict:
            return None

        content_bytes, mime_type = versions_dict[target_version]
        return adk_types.Part(
            inline_data=adk_types.Blob(mime_type=mime_type, data=content_bytes)
        )

    @override
    async def list_artifact_keys(
        self, *, app_name: str, user_id: str, session_id: str
    ) -> List[str]:
        keys: set[str] = set()

        session_artifacts = (
            self._artifacts_data.get(app_name, {}).get(user_id, {}).get(session_id, {})
        )
        for filename_key in session_artifacts.keys():
            keys.add(filename_key)
        user_namespace_artifacts = (
            self._artifacts_data.get(app_name, {})
            .get(user_id, {})
            .get(_USER_NAMESPACE_KEY, {})
        )
        for filename_key in user_namespace_artifacts.keys():
            keys.add(f"user:{filename_key}")
        return sorted(list(keys))

    @override
    async def delete_artifact(
        self, *, app_name: str, user_id: str, session_id: str, filename: str
    ) -> None:
        app_key, user_key, effective_session_key, fn_key = self._get_path_keys(
            app_name, user_id, session_id, filename
        )
        if self._artifacts_data[app_key][user_key][effective_session_key].pop(
            fn_key, None
        ):
            pass

    @override
    async def list_versions(
        self, *, app_name: str, user_id: str, session_id: str, filename: str
    ) -> List[int]:
        app_key, user_key, effective_session_key, fn_key = self._get_path_keys(
            app_name, user_id, session_id, filename
        )
        versions_dict = self._artifacts_data[app_key][user_key][
            effective_session_key
        ].get(fn_key)
        if not versions_dict:
            return []
        return sorted(list(versions_dict.keys()))

    async def get_artifact_details(
        self, app_name: str, user_id: str, session_id: str, filename: str, version: int
    ) -> Optional[Tuple[bytes, str]]:
        """
        Retrieves the content bytes and mime type for a specific artifact version.
        Returns (content_bytes, mime_type) or None if not found.
        """
        app_key, user_key, effective_session_key, fn_key = self._get_path_keys(
            app_name, user_id, session_id, filename
        )
        artifact_data = (
            self._artifacts_data[app_key][user_key][effective_session_key]
            .get(fn_key, {})
            .get(version)
        )
        return cast(Optional[Tuple[bytes, str]], artifact_data)

    async def get_all_artifacts_for_session(
        self, app_name: str, user_id: str, session_id: str
    ) -> Dict[str, Dict[int, Tuple[bytes, str]]]:
        """
        Returns all artifacts (filename -> version -> (bytes, mime_type))
        for a specific app_name, user_id, and session_id (non-user-namespaced).
        """
        app_data = self._artifacts_data.get(app_name, {})
        user_data = app_data.get(user_id, {})
        session_data = user_data.get(session_id, {})
        return cast(Dict[str, Dict[int, Tuple[bytes, str]]], session_data)

    async def get_all_user_artifacts(
        self, app_name: str, user_id: str
    ) -> Dict[str, Dict[int, Tuple[bytes, str]]]:
        """
        Returns all user-namespaced artifacts (filename_key -> version -> (bytes, mime_type))
        for a specific app_name and user_id. Filename keys here do NOT have the "user:" prefix.
        """
        app_data = self._artifacts_data.get(app_name, {})
        user_data = app_data.get(user_id, {})
        user_namespace_data = user_data.get(_USER_NAMESPACE_KEY, {})
        return cast(Dict[str, Dict[int, Tuple[bytes, str]]], user_namespace_data)

    async def clear_all_artifacts(self) -> None:
        """Clears all artifacts from the in-memory store."""
        self._artifacts_data.clear()
        self._artifacts_data = defaultdict(
            lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
        )

    async def get_raw_store(self) -> Dict:
        """Returns the raw internal storage dictionary. For debugging/advanced inspection."""
        return self._artifacts_data
