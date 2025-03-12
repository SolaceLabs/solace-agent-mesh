import json
import time
from .base_history_provider import BaseHistoryProvider

class RedisHistoryProvider(BaseHistoryProvider):
    def __init__(self, config=None):
        super().__init__(config)
        try:
            import redis
        except ImportError:
            raise ImportError("Please install the redis package to use the RedisHistoryProvider.\n\t$ pip install redis")
        
        self.redis_client = redis.Redis(
            host=self.config.get("redis_host", "localhost"),
            port=self.config.get("redis_port", 6379),
            db=self.config.get("redis_db", 0),
        )

    def _get_history_key(self, session_id: str):
        return f"session:{session_id}:history"

    def _get_files_key(self, session_id: str):
        return f"session:{session_id}:files"

    def store_history(self, session_id: str, role: str, content: str | dict):
        key = self._get_history_key(session_id)
        entry = {"role": role, "content": content}
        entry_json = json.dumps(entry)

        # Check if session exists, if not initialize it
        if not self.redis_client.exists(key):
            self.redis_client.hset(session_id, mapping={
                "num_characters": 0,
                "num_turns": 0,
                "last_active_time": time.time()
            })

        # Get current stats
        session_meta = self.redis_client.hgetall(session_id)
        num_characters = int(session_meta.get(b"num_characters", 0))
        num_turns = int(session_meta.get(b"num_turns", 0))

        # Add the new entry
        if self.enforce_alternate_message_roles and num_turns > 0:
            last_entry = json.loads(self.redis_client.lindex(key, -1))
            if last_entry["role"] == role:
                last_entry["content"] += content
                self.redis_client.lset(key, -1, json.dumps(last_entry))
            else:
                self.redis_client.rpush(key, entry_json)
                num_turns += 1
        else:
            self.redis_client.rpush(key, entry_json)
            num_turns += 1
        num_characters += len(str(content))

        # Enforce max_turns by trimming the oldest entry if needed
        if self.max_turns and num_turns > self.max_turns:
            oldest_entry = json.loads(self.redis_client.lpop(key))
            num_characters -= len(str(oldest_entry["content"]))
            num_turns -= 1

        # Enforce max_characters
        if self.max_characters:
            while num_characters > self.max_characters and num_turns > 0:
                oldest_entry = json.loads(self.redis_client.lpop(key))
                num_characters -= len(str(oldest_entry["content"]))
                num_turns -= 1

        # Update metadata and set expiration
        self.redis_client.hset(session_id, mapping={
            "num_characters": num_characters,
            "num_turns": num_turns,
            "last_active_time": time.time()
        })

    def get_history(self, session_id: str):
        key = self._get_history_key(session_id)
        history = self.redis_client.lrange(key, 0, -1)

        # Decode JSON entries and return a list of dictionaries
        return [json.loads(entry) for entry in history]

    def store_file(self, session_id: str, file: dict):
        key = self._get_files_key(session_id)
        file_entry = json.dumps(file)

        # Avoid duplicate files by checking existing URLs
        existing_files = self.get_files(session_id)
        if any(f.get("url") == file.get("url") for f in existing_files):
            return

        # Add the file and update metadata
        self.redis_client.rpush(key, file_entry)
        self.redis_client.hset(session_id, "last_active_time", time.time())

    def get_files(self, session_id: str):
        key = self._get_files_key(session_id)
        current_time = time.time()
        files = self.redis_client.lrange(key, 0, -1)

        valid_files = []
        for file_json in files:
            file = json.loads(file_json)
            expiration_timestamp = file.get("expiration_timestamp")

            # Remove expired files
            if expiration_timestamp and current_time > expiration_timestamp:
                self.redis_client.lrem(key, 0, file_json)
            else:
                valid_files.append(file)

        return valid_files

    def clear_history(self, session_id: str, keep_levels=0, clear_files=True):
        history_key = self._get_history_key(session_id)

        if keep_levels > 0:
            # Keep the latest `keep_levels` entries
            self.redis_client.ltrim(history_key, -keep_levels, -1)

            # Recalculate session metadata
            remaining_entries = self.redis_client.lrange(history_key, 0, -1)
            num_characters = sum(len(str(json.loads(entry)["content"])) for entry in remaining_entries)
            num_turns = len(remaining_entries)

            # Update metadata
            self.redis_client.hset(session_id, mapping={
                "num_characters": num_characters,
                "num_turns": num_turns
            })
        else:
            # Clear all history and files
            self.redis_client.delete(history_key, session_id)

        if clear_files:
            files_key = self._get_files_key(session_id)
            self.redis_client.delete(files_key)


    def get_session_meta(self, session_id: str):
        """
        Retrieve the session metadata.

        :param session_id: The session identifier.
        :return: The session metadata.
        """
        # Check if session exists
        if not self.redis_client.exists(session_id):
            return None
        # Get current stats
        session_meta = self.redis_client.hgetall(session_id)
        num_characters = int(session_meta.get(b"num_characters", 0))
        num_turns = int(session_meta.get(b"num_turns", 0))
        last_active_time = float(session_meta.get(b"last_active_time", 0))
        return {
            "num_characters": num_characters,
            "num_turns": num_turns,
            "last_active_time": last_active_time,
        }


    def get_all_sessions(self)-> list[str]:
        # List all sessions based on Redis keys
        session_keys = self.redis_client.scan_iter("session:*:history")
        return [key.decode().split(":")[1] for key in session_keys]