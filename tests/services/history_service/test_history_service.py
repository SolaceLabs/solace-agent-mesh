import unittest
import time

from src.services.history_service import HistoryService


class TestHistoryService(unittest.TestCase):
    def get_memory_history_service(self, config={}, ttl=10, exp=5):
        id = "test_history_" + str(time.time())
        if "enforce_alternate_message_roles" not in config:
            config["enforce_alternate_message_roles"] = False
        return HistoryService(
            config={
                "type": "memory",
                "time_to_live": ttl,
                "expiration_check_interval": exp,
                "history_policy": config,
            },
            identifier=id,
        )

    def test_store_and_get_history(self):
        service = self.get_memory_history_service()
        session_id = "session1"
        role = "user"
        content = "Hello, world!"

        service.store_history(session_id, role, content)
        history = service.get_history(session_id)

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["role"], role)
        self.assertEqual(history[0]["content"], content)

    def test_store_multiple_history(self):
        service = self.get_memory_history_service()
        session_id = "session1"
        role1 = "user"
        role2 = "assistant"
        content1 = "Hello, world!"
        content2 = "Hello again!"

        service.store_history(session_id, role1, content1)
        service.store_history(session_id, role2, content2)
        history = service.get_history(session_id)

        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["content"], content1)
        self.assertEqual(history[1]["content"], content2)

    def test_store_empty_content_history(self):
        service = self.get_memory_history_service()
        session_id = "session1"
        role = "user"
        content = ""

        service.store_history(session_id, role, content)
        history = service.get_history(session_id)

        self.assertEqual(len(history), 0)

    def test_max_characters_not_reached(self):
        service = self.get_memory_history_service({"max_characters": 100})
        session_id = "session1"
        role = "user"
        content = "Hello, world!"

        service.store_history(session_id, role, content)
        service.store_history(session_id, role, content)
        history = service.get_history(session_id)

        self.assertEqual(len(history), 2)

    def test_max_characters_reached(self):
        service = self.get_memory_history_service({"max_characters": 15})
        session_id = "session1"
        role = "user"
        content = "Hello, world!"

        service.store_history(session_id, role, content)
        service.store_history(session_id, role, content)
        history = service.get_history(session_id)

        self.assertEqual(len(history), 1)

    def test_max_turns_not_reached(self):
        service = self.get_memory_history_service({"max_turns": 2})
        session_id = "session1"
        role = "user"
        content = "Hello, world!"

        service.store_history(session_id, role, content)
        service.store_history(session_id, role, content)
        history = service.get_history(session_id)

        self.assertEqual(len(history), 2)

    def test_max_turns_reached(self):
        service = self.get_memory_history_service({"max_turns": 10})
        session_id = "session1"
        role = "user"
        content = "Hello, world!"

        for _ in range(20):
            service.store_history(session_id, role, content)

        history = service.get_history(session_id)

        self.assertEqual(len(history), 10)

    def test_enforce_alternate_message_roles_off(self):
        service = self.get_memory_history_service(
            {"enforce_alternate_message_roles": False}
        )
        session_id = "session1"
        role1 = "user"
        role2 = "assistant"
        content1 = "Hello, world!"
        content2 = "Hello again!"
        content3 = "Hello once more!"

        service.store_history(session_id, role1, content1)
        service.store_history(session_id, role1, content2)
        service.store_history(session_id, role2, content3)
        history = service.get_history(session_id)

        self.assertEqual(len(history), 3)
        self.assertEqual(history[0]["content"], content1)
        self.assertEqual(history[1]["content"], content2)
        self.assertEqual(history[2]["content"], content3)

    def test_enforce_alternate_message_roles(self):
        service = self.get_memory_history_service(
            {"enforce_alternate_message_roles": True}
        )
        session_id = "session1"
        role1 = "user"
        role2 = "assistant"
        content1 = "Hello, world!"
        content2 = "Hello again!"
        content3 = "Hello once more!"

        service.store_history(session_id, role1, content1)
        service.store_history(session_id, role1, content2)
        service.store_history(session_id, role2, content3)
        history = service.get_history(session_id)

        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["content"], content1 + "\n\n" + content2)
        self.assertEqual(history[1]["content"], content3)

    def test_store_and_get_files(self):
        service = self.get_memory_history_service()
        session_id = "session1"
        file_meta = {
            "url": "http://example.com/file.txt",
        }

        service.store_file(session_id, file_meta)
        files = service.get_files(session_id)

        self.assertEqual(len(files), 1)
        self.assertEqual(files[0], file_meta)

    def test_store_duplicate_files(self):
        service = self.get_memory_history_service()
        session_id = "session1"
        file_meta = {
            "url": "http://example.com/file.txt",
        }

        service.store_file(session_id, file_meta)
        service.store_file(session_id, file_meta)
        service.store_file(session_id, file_meta)
        files = service.get_files(session_id)

        self.assertEqual(len(files), 1)
        self.assertEqual(files[0], file_meta)

    def test_clear_history(self):
        service = self.get_memory_history_service()
        session_id = "session1"
        role = "user"
        content = "Hello, world!"

        service.store_history(session_id, role, content)
        service.clear_history(session_id)
        history = service.get_history(session_id)

        self.assertEqual(len(history), 0)

    def test_auto_expiry(self):
        service = self.get_memory_history_service(ttl=0.7, exp=0.3)
        session_id = "session1"
        role = "user"
        content = "Hello, world!"

        service.store_history(session_id, role, content)
        time.sleep(1)  # Wait for the item to expire
        service._delete_expired_items()
        history = service.get_history(session_id)

        self.assertEqual(len(history), 0)

    def test_unsupported_provider_type(self):
        with self.assertRaises(ValueError):
            HistoryService(config={"type": "unsupported"})

    def test_custom_provider_module_path(self):
        # Assuming a custom provider module is available at 'custom_module.CustomProvider'
        with self.assertRaises(ImportError):
            HistoryService(
                config={"type": "CustomProvider", "module_path": "custom_module"}
            )

    def test_clear_history_keep_levels(self):
        service = self.get_memory_history_service()
        session_id = "session1"
        role = "user"
        content1 = "Hello, world!"
        content2 = "Hello again!"

        service.store_history(session_id, role, content1)
        service.store_history(session_id, role, content2)
        service.clear_history(session_id, keep_levels=1)
        history = service.get_history(session_id)

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["content"], content2)
