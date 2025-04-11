import time
import importlib
import threading
from typing import Union, Tuple

from solace_ai_connector.common.log import log

from ...common.time import ONE_HOUR, FIVE_MINUTES, ONE_DAY
from ...common.constants import HISTORY_MEMORY_ROLE, HISTORY_ACTION_ROLE, HISTORY_USER_ROLE, HISTORY_ASSISTANT_ROLE
from ..common import AutoExpiry, AutoExpirySingletonMeta
from .history_providers.index import HistoryProviderFactory
from .history_providers.base_history_provider import BaseHistoryProvider
from .long_term_memory.long_term_memory import LongTermMemory

DEFAULT_PROVIDER = "memory"

DEFAULT_MAX_TURNS = 40
DEFAULT_MAX_CHARACTERS = 50_000
DEFAULT_SUMMARY_TIME_TO_LIVE = ONE_DAY * 5

DEFAULT_HISTORY_POLICY = {
    "max_turns": DEFAULT_MAX_TURNS,
    "max_characters": DEFAULT_MAX_CHARACTERS,
    "enforce_alternate_message_roles": True,
}


# HistoryService class - Manages history storage and retrieval
class HistoryService(AutoExpiry, metaclass=AutoExpirySingletonMeta):
    history_provider: BaseHistoryProvider
    long_term_memory_store: BaseHistoryProvider
    long_term_memory_service: LongTermMemory

    def __init__(self, config={}, identifier=None):
        """
        Initialize the history service.
        """
        self.identifier = identifier
        self.config = config
        self.time_to_live = self.config.get("time_to_live", ONE_HOUR)
        self.use_long_term_memory = self.config.get("enable_long_term_memory", False)
        self.expiration_check_interval = self.config.get(
            "expiration_check_interval", FIVE_MINUTES
        )

        self.history_policy = {
            **DEFAULT_HISTORY_POLICY,
            **self.config.get("history_policy", {}),
        }

        self.history_provider = self._get_history_provider(
            self.config.get("type", DEFAULT_PROVIDER),
            self.config.get("module_path"),
            self.history_policy
        )

        if self.use_long_term_memory:
            # Setting up the long-term memory service
            self.long_term_memory_config = self.config.get("long_term_memory_config", {})
            if not self.long_term_memory_config.get("llm_config"):
                raise ValueError("Missing required configuration for Long-Term Memory provider, Missing 'model' or 'api_key' in 'history_policy.long_term_memory_config.llm_config'.")
            self.long_term_memory_service = LongTermMemory(self.long_term_memory_config.get("llm_config"))

            # Setting up the long-term memory store
            store_config = self.long_term_memory_config.get("store_config", {})
            self.long_term_memory_store =  self._get_history_provider(
                store_config.get("type", DEFAULT_PROVIDER),
                store_config.get("module_path"),
                store_config
            )

        # Start the background thread for auto-expiry
        self._start_auto_expiry_thread(self.expiration_check_interval)

    def _get_history_provider(self, provider_type:str, module_path:str="", config:dict={}):
        """
        Get the history provider based on the provider type.
        """
        if HistoryProviderFactory.has_provider(provider_type):
            return HistoryProviderFactory.get_provider_class(provider_type)(config)
        else:
            if not module_path:
                raise ValueError(
                    f"Unsupported history provider type: {provider_type}. No module_path provided."
                )
            try:
                module_name = self.provider_type
                module = importlib.import_module(module_path, package=__package__)
                history_class = getattr(module, module_name)
                if not issubclass(history_class, BaseHistoryProvider):
                    raise ValueError(
                        f"History provider class {history_class} does not inherit from BaseHistoryProvider"
                    )
                return history_class(config)
            except Exception as e:
                raise ImportError("Unable to load component: " + str(e)) from e

    def _delete_expired_items(self):
        """Checks all history entries and deletes those that have exceeded max_time_to_live."""
        current_time = time.time()
        sessions = self.history_provider.get_all_sessions()
        for session_id in sessions:
            session = self.history_provider.get_session(session_id)
            if not session:
                continue
            elapsed_time = current_time - session["last_active_time"]
            if elapsed_time > self.time_to_live:
                self.clear_history(session_id)
                log.debug("History for session %s has expired", session_id)

    def _get_empty_history_entry(self):
        """
        Get an empty history entry.
        """
        return {
            "history": [],
            "files": [],
            "summary": "",
            "last_active_time": time.time(),
            "num_characters": 0,
            "num_turns": 0,
        }


    def _merge_assistant_with_actions(self, assistant_message:str, history:list) -> Tuple[str, list]:
        """
        Merge assistant message with the actions called to generate the response.
        """
        actions_called = []
        # Looping reversely to get the most recent action
        index = len(history)
        for entry in reversed(history):
            if entry["role"] == HISTORY_ACTION_ROLE:
                actions_called.append(entry["content"])
                index -= 1
            else:
                break
        if actions_called:
            actions_called_str = ""
            for action_called in reversed(actions_called):
                actions_called_str += (
                    f"\n - Agent: {action_called.get('agent_name')}"
                    f"\n   Action: {action_called.get('action_name')}"
                    f"\n   Action Parameters: {action_called.get('action_params')}"
                )
                
            actions_called_prompt = (
                "<message_metadata>\n"
                "[Following actions were called to generate this response:]"
                f"{actions_called_str}"
                "\n</message_metadata>\n\n"
            )
            assistant_message = f"{actions_called_prompt}{assistant_message}"

        return assistant_message, history[:index]
    
    def _filter_actions(self, history:list) -> list:
        """
        Filter out action entries from the history.
        """
        return [entry for entry in history if entry["role"] != HISTORY_ACTION_ROLE]
    
    def store_history(self, session_id: str, role: str, content: Union[str, dict], other_history_props: dict = {}):
        """
        Store a new entry in the history.

        :param session_id: The session identifier.
        :param role: The role of the entry to be stored in the history.
        :param content: The content of the entry to be stored in the history.
        :param other_history_props: Other history properties such as user identifier.
        """
        if not content:
            return
        
        user_identity = other_history_props.get("identity", session_id)
        
        history = self.history_provider.get_session(session_id).copy()
        if not history:
            history = self._get_empty_history_entry()

        if role == HISTORY_ASSISTANT_ROLE:
            content, history["history"] = self._merge_assistant_with_actions(content, history["history"])
        elif role == HISTORY_USER_ROLE:
            history["history"] = self._filter_actions(history["history"])

        if (
            self.history_policy.get("enforce_alternate_message_roles")
            and history["num_turns"] > 0
            # Check if the last entry was by the same role
            and history["history"]
            and history["history"][-1]["role"] == role
        ):
            # Append to last entry
            history["history"][-1]["content"] += "\n\n" + content
        else:
            # Add the new entry
            history["history"].append(
                {"role": role, "content": content}
            )
            # Update the number of turns
            history["num_turns"] += 1

        # Update the length
        history["num_characters"] += len(str(content))
        # Update the last active time
        history["last_active_time"] = time.time()

        # Extract memory from the last 2 messages if use long term memory is enabled
        if self.use_long_term_memory and role == HISTORY_USER_ROLE and len(history["history"]) > 2:
            recent_messages = history["history"][-3:-1].copy()
            def background_task():
                memory = self.long_term_memory_service.extract_memory_from_chat(recent_messages)

                if memory and (memory.get("facts") or memory.get("instructions") or memory.get("update_notes")):
                    old_memory = self.long_term_memory_store.get_session(user_identity).get("memory", {})
                    updated_memory = self.long_term_memory_service.update_user_memory(old_memory, memory)
                    self.long_term_memory_store.update_session(user_identity, {
                        "memory": updated_memory
                    })

            threading.Thread(target=background_task).start()

        # Check if active session history requires truncation
        if ((self.history_policy.get("max_characters") and (history["num_characters"] > self.history_policy.get("max_characters"))) 
            or history["num_turns"] > self.history_policy.get("max_turns")):
            
            cut_off_index = 0
            if history["num_turns"] > self.history_policy.get("max_turns"):
                cut_off_index = max(0, int(self.history_policy.get("max_turns") * 0.5)) # 40% of max_turns

            if self.history_policy.get("max_characters") and (history["num_characters"] > self.history_policy.get("max_characters")):
                index = 0
                characters = 0
                while characters < self.history_policy.get("max_characters") and index < len(history["history"]) - 1:
                    characters += len(str(history["history"][index]["content"]))
                    index += 1
                cut_off_index = max(cut_off_index, index)

            cut_off_index = min(cut_off_index, len(history["history"])) # Ensure cut_off_index is within bounds 

            if self.use_long_term_memory:
                cut_of_history = history["history"][:cut_off_index].copy()
                def background_summary_task():
                    summary = self.long_term_memory_service.summarize_chat(cut_of_history)
                    updated_summary = self.long_term_memory_service.update_summary(history["summary"], summary)

                    fetched_history = self.history_provider.get_session(session_id).copy()
                    if fetched_history:
                        fetched_history["summary"] = updated_summary
                        self.history_provider.store_session(session_id, fetched_history)

                threading.Thread(target=background_summary_task).start()

            history["history"] = history["history"][cut_off_index:]
            history["num_characters"] = sum(len(str(entry["content"])) for entry in history["history"])
            history["num_turns"] = len(history["history"])
            history["last_active_time"] = time.time()

        # Update the session history
        return self.history_provider.store_session(session_id, history)


    def get_history(self, session_id:str, other_history_props: dict = {}) -> list:
        """
        Retrieve the entire history.

        :param session_id: The session identifier.
        :param other_history_props: Other history properties such as user identifier.
        :return: The complete history.
        """
        history = self.history_provider.get_session(session_id)
        messages = history.get("history", [])

        if self.use_long_term_memory:
            user_identity = other_history_props.get("identity", session_id)
            stored_memory = self.long_term_memory_store.get_session(user_identity)
            if stored_memory:
                long_term_memory = self.long_term_memory_service.retrieve_user_memory(stored_memory.get("memory", {}), history.get("summary", ""))
                if long_term_memory:
                    return [
                        {
                            "role": HISTORY_MEMORY_ROLE,
                            "content": long_term_memory
                        },
                        *messages
                    ]
                
        return messages
    
    def store_actions(self, session_id:str, actions:list):
        """
        Store an action in the history.

        :param session_id: The session identifier.
        :param actions: The actions to be stored in the history.
        """
        if not actions:
            return
        
        history = self.history_provider.get_session(session_id).copy()
        if not history:
            history = self._get_empty_history_entry()

        for action in actions:
            history["history"].append(
                {"role": HISTORY_ACTION_ROLE, "content": action}
            )

        history["last_active_time"] = time.time()

        return self.history_provider.store_session(session_id, history)
    

    def store_file(self, session_id:str, file:dict):
        """
        Store a file in the history.

        :param session_id: The session identifier.
        :param file: The file to be stored in the history.
        """
        if not file:
            return
        
        history = self.history_provider.get_session(session_id).copy()
        if not history:
            history = self._get_empty_history_entry()

        # Check duplicate
        for f in history["files"]:
            if f.get("url") and f.get("url") == file.get("url"):
                return

        history["files"].append(file)
        history["last_active_time"] = time.time()

        return self.history_provider.store_session(session_id, history)

    def get_files(self, session_id:str) -> list:
        """
        Retrieve the files for a session.

        :param session_id: The session identifier.
        :return: The files for the session.
        """
        history = self.history_provider.get_session(session_id)
        if not history:
            return []
        
        files = []
        current_time = time.time()
        all_files = history["files"].copy()

        for file in all_files:
            expiration_timestamp = file.get("expiration_timestamp")
            if expiration_timestamp and current_time > expiration_timestamp:
                history["files"].remove(file)
                continue
            files.append(file)

        self.history_provider.store_session(session_id, history)
        return files


    def clear_history(self, session_id:str, keep_levels=0, clear_files=True):
        """
        Clear the history and files, optionally keeping a specified number of recent entries.

        :param session_id: The session identifier.
        :param keep_levels: Number of most recent history entries to keep. Default is 0 (clear all).
        :param other_history_props: Other history properties such as user identifier.
        :param clear_files: Whether to clear associated files. Default is True.
        """

        history = self.history_provider.get_session(session_id).copy()
        if not history:
            return
        
        if history.get("history") or (clear_files and history.get("files")):
            cut_off_index = max(0, len(history["history"]) - keep_levels)
            cut_off_history = history["history"][:cut_off_index]

            if self.use_long_term_memory and cut_off_history:
                def background_task(): 
                    summary = self.long_term_memory_service.summarize_chat(cut_off_history)
                    updated_summary = self.long_term_memory_service.update_summary(history["summary"], summary)

                    fetched_history = self.history_provider.get_session(session_id).copy()
                    if fetched_history:
                        fetched_history["summary"] = updated_summary
                        self.history_provider.store_session(session_id, fetched_history)
                threading.Thread(target=background_task).start()

            history["history"] = [] if keep_levels <= 0 else history["history"][-keep_levels:]
            history["num_turns"] = keep_levels
            history["num_characters"] = sum(len(str(entry["content"])) for entry in history["history"])
            history["last_active_time"] = time.time()

            if clear_files:
                history["files"] = []

            return self.history_provider.store_session(session_id, history)
        
        # Summaries get cleared at a longer expiry time
        elif  self.use_long_term_memory and history.get("summary"):
            elapsed_time = time.time() - history["last_active_time"]
            summary_ttl = self.long_term_memory_config.get("summary_time_to_live", DEFAULT_SUMMARY_TIME_TO_LIVE)
            if elapsed_time > summary_ttl:
                return self.history_provider.delete_session(session_id)
            
        # Delete the session if it has no chat history, files or summary
        else:
            return self.history_provider.delete_session(session_id)
        
