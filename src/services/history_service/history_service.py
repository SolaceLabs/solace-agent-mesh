import time
import importlib
from typing import Union

from solace_ai_connector.common.log import log

from ...common.time import ONE_HOUR, FIVE_MINUTES
from ..common import AutoExpiry, AutoExpirySingletonMeta
from .history_providers.memory_history_provider import MemoryHistoryProvider
from .history_providers.redis_history_provider import RedisHistoryProvider
from .history_providers.base_history_provider import BaseHistoryProvider

HISTORY_PROVIDERS = {
    "redis": RedisHistoryProvider,
    "memory": MemoryHistoryProvider,
}


DEFAULT_PROVIDER = "memory"

DEFAULT_MAX_TURNS = 40
DEFAULT_MAX_CHARACTERS = 50_000

DEFAULT_HISTORY_POLICY = {
    "max_turns": DEFAULT_MAX_TURNS,
    "max_characters": DEFAULT_MAX_CHARACTERS,
    "enforce_alternate_message_roles": False,
}


# HistoryService class - Manages history storage and retrieval
class HistoryService(AutoExpiry, metaclass=AutoExpirySingletonMeta):
    history_provider: BaseHistoryProvider

    def __init__(self, config={}, identifier=None):
        self.identifier = identifier
        self.config = config
        self.provider_type = self.config.get("type", DEFAULT_PROVIDER)
        self.time_to_live = self.config.get("time_to_live", ONE_HOUR)
        self.expiration_check_interval = self.config.get(
            "expiration_check_interval", FIVE_MINUTES
        )

        if self.provider_type not in HISTORY_PROVIDERS and not self.config.get(
            "module_path"
        ):
            raise ValueError(
                f"Unsupported history provider type: {self.provider_type}. No module_path provided."
            )

        history_policy = {
            **DEFAULT_HISTORY_POLICY,
            **self.config.get("history_policy", {}),
        }
        if self.provider_type in HISTORY_PROVIDERS:
            # Load built-in history provider
            self.history_provider = HISTORY_PROVIDERS[self.provider_type](
                history_policy
            )
        else:
            try:
                # Load the provider from the module path
                module_name = self.provider_type
                module_path = self.config.get("module_path")
                module = importlib.import_module(module_path, package=__package__)
                history_class = getattr(module, module_name)
                if not issubclass(history_class, BaseHistoryProvider):
                    raise ValueError(
                        f"History provider class {history_class} does not inherit from BaseHistoryProvider"
                    )
                self.history_provider = history_class(history_policy)
            except Exception as e:
                raise ImportError("Unable to load component: " + str(e)) from e

        # Start the background thread for auto-expiry
        self._start_auto_expiry_thread(self.expiration_check_interval)

    def _delete_expired_items(self):
        """Checks all history entries and deletes those that have exceeded max_time_to_live."""
        current_time = time.time()
        sessions = self.history_provider.get_all_sessions()
        for session_id in sessions:
            session = self.history_provider.get_session_meta(session_id)
            if not session:
                continue
            elapsed_time = current_time - session["last_active_time"]
            if elapsed_time > self.time_to_live:
                self.history_provider.clear_history(session_id)
                log.debug(f"History for session {session_id} has expired")

    def store_history(self, session_id: str, role: str, content: Union[str, dict]):
        """
        Store a new entry in the history.

        :param session_id: The session identifier.
        :param role: The role of the entry to be stored in the history.
        :param content: The content of the entry to be stored in the history.
        """
        if not content:
            return
        return self.history_provider.store_history(session_id, role, content)

    def get_history(self, session_id:str) -> list:
        """
        Retrieve the entire history.

        :param session_id: The session identifier.
        :return: The complete history.
        """
        return self.history_provider.get_history(session_id)

    def store_file(self, session_id:str, file:dict):
        """
        Store a file in the history.

        :param session_id: The session identifier.
        :param file: The file to be stored in the history.
        """
        if not file:
            return
        return self.history_provider.store_file(session_id, file)

    def get_files(self, session_id:str) -> list:
        """
        Retrieve the files for a session.

        :param session_id: The session identifier.
        :return: The files for the session.
        """
        return self.history_provider.get_files(session_id)

    def clear_history(self, session_id:str, keep_levels=0):
        """
        Clear the history and files, optionally keeping a specified number of recent entries.

        :param session_id: The session identifier.
        :param keep_levels: Number of most recent history entries to keep. Default is 0 (clear all).
        """
        return self.history_provider.clear_history(session_id, keep_levels, clear_files=True)
