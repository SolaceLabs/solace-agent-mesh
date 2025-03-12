import time
from .base_history_provider import BaseHistoryProvider


class MemoryHistoryProvider(BaseHistoryProvider):
    def __init__(self, config=None):
        super().__init__(config)
        self.history = {}

    def store_history(self, session_id: str, role: str, content: str | dict):
        """
        Store a new entry in the history.

        :param session_id: The session identifier.
        :param history_entry: The entry to be stored in the history.
        """

        if session_id not in self.history:
            self.history[session_id] = {
                "history": [],
                "files": [],
                "last_active_time": time.time(),
                "num_characters": 0,
                "num_turns": 0,
            }

        # Check if adding another entry would exceed the max_turns
        if self.history[session_id]["num_turns"] == self.max_turns:
            # Remove the oldest entry
            oldest_entry = self.history[session_id]["history"].pop(0)
            # Subtract the length of the oldest entry from the total length
            self.history[session_id]["num_characters"] -= len(
                str(oldest_entry["content"])
            )
            self.history[session_id]["num_turns"] -= 1

        if (
            self.enforce_alternate_message_roles
            and self.history[session_id]["num_turns"] > 0
            # Check if the last entry was by the same role
            and self.history[session_id]["history"]
            and self.history[session_id]["history"][-1]["role"] == role
        ):
            # Append to last entry
            self.history[session_id]["history"][-1]["content"] += content
        else:
            # Add the new entry
            self.history[session_id]["history"].append(
                {"role": role, "content": content}
            )
            # Update the number of turns
            self.history[session_id]["num_turns"] += 1

        # Update the length
        self.history[session_id]["num_characters"] += len(str(content))
        # Update the last active time
        self.history[session_id]["last_active_time"] = time.time()

        # Check if we have exceeded max_characters
        if self.max_characters:
            while (
                self.history[session_id]["num_characters"] > self.max_characters
                and self.history[session_id]["num_turns"] > 0
            ):
                # Remove the oldest entry
                oldest_entry = self.history[session_id]["history"].pop(0)
                # Subtract the length of the oldest entry from the total length
                self.history[session_id]["num_characters"] -= len(
                    str(oldest_entry["content"])
                )
                self.history[session_id]["num_turns"] -= 1

    def get_history(self, session_id: str):
        """
        Retrieve the entire history for a session.

        :param session_id: The session identifier.
        :return: The complete history for the session.
        """
        if session_id not in self.history:
            return []
        return self.history.get(session_id)["history"]

    def store_file(self, session_id: str, file: dict):
        """
        Store a file in the history.

        :param session_id: The session identifier.
        :param file: The file metadata to be stored in the history.
        """
        if session_id not in self.history:
            self.history[session_id] = {
                "history": [],
                "files": [],
                "last_active_time": time.time(),
                "num_characters": 0,
                "num_turns": 0,
            }
        self.history[session_id]["last_active_time"] = time.time()

        # Check duplicate
        for f in self.history[session_id]["files"]:
            if f.get("url") and f.get("url") == file.get("url"):
                return

        self.history[session_id]["files"].append(file)

    def get_files(self, session_id: str):
        """
        Retrieve the files for a session.

        :param session_id: The session identifier.
        :return: The files for the session.
        """
        if session_id not in self.history:
            return []
        files = []
        current_time = time.time()
        all_files = self.history.get(session_id)["files"].copy()
        for file in all_files:
            expiration_timestamp = file.get("expiration_timestamp")
            if expiration_timestamp and current_time > expiration_timestamp:
                self.history[session_id]["files"].remove(file)
                continue
            files.append(file)
        return files

    def clear_history(self, session_id: str, keep_levels=0, clear_files=True):
        """
        Clear the history for a session, optionally keeping a specified number of recent entries.

        :param session_id: The session identifier.
        :param keep_levels: Number of most recent history entries to keep. Default is 0 (clear all).
        :param clear_files: Whether to clear associated files. Default is True.
        """
        if session_id in self.history:
            if keep_levels <= 0:
                del self.history[session_id]
            else:
                self.history[session_id]["history"] = self.history[session_id][
                    "history"
                ][-keep_levels:]
                # Recalculate the length and num_turns
                self.history[session_id]["num_characters"] = sum(
                    len(str(entry)) for entry in self.history[session_id]["history"]
                )
                self.history[session_id]["num_turns"] = len(
                    self.history[session_id]["history"]
                )
        if session_id in self.history and clear_files:
            self.history[session_id]["files"] = []

    def get_session_meta(self, session_id: str):
        """
        Retrieve the session metadata.

        :param session_id: The session identifier.
        :return: The session metadata.
        """
        if session_id in self.history:
            session = self.history[session_id]
            return {
                "num_characters": session["num_characters"],
                "num_turns": session["num_turns"],
                "last_active_time": session["last_active_time"],
            }
        return None

    def get_all_sessions(self) -> list[str]:
        return list(self.history.keys())
