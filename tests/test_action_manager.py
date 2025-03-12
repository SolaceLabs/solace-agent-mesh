# tests to verify that the action_manager.py file is working as expected:
import unittest

from src.orchestrator.action_manager import ActionManager
from src.common.constants import ORCHESTRATOR_COMPONENT_NAME
from tests.mocks import FlowKVStore, FlowLockManager


class TestActionManger(unittest.TestCase):

    def test_action_manager_creation(self):
        kv_store = FlowKVStore()
        lock_manager = FlowLockManager()
        action_manager = ActionManager(kv_store, lock_manager)
        self.assertIsNotNone(action_manager)

    def test_add_action_request(self):
        kv_store = FlowKVStore()
        lock_manager = FlowLockManager()
        action_manager = ActionManager(kv_store, lock_manager)
        action_manager.add_action_request(
            [
                {
                    "agent_name": "global",
                    "action_name": "error_action",
                    "action_params": {
                        "error_message": "There was no useful response. Please try again"
                    },
                }
            ],
            None,
        )

        self.assertEqual(len(action_manager.action_requests), 1)

    def test_add_mixed_action_requests_and_complete_them(self):
        kv_store = FlowKVStore()
        lock_manager = FlowLockManager()
        action_manager = ActionManager(kv_store, lock_manager)
        action_requestlist = [
            {
                "agent_name": "global",
                "action_name": "send_message",
                "action_params": {"message": "Hello"},
            },
            {
                "agent_name": "global",
                "action_name": "send_message",
                "action_params": {"message": "Hello2"},
            },
            {
                "agent_name": "global",
                "action_name": "send_message",
                "action_params": {"message": "Hello3"},
            },
        ]

        action_manager.add_action_request(action_requestlist, None)

        action_list_id = action_requestlist[0].get("action_list_id")

        action_list = action_manager.add_action_response(
            {
                "action_list_id": action_list_id,
                "action_idx": 0,
                "action_name": "send_message",
                "action_params": {"message": "Hello"},
                "originator": ORCHESTRATOR_COMPONENT_NAME,
            },
            {"text": "Hello", "files": []},
        )

        self.assertIsNotNone(action_list)
        self.assertFalse(action_list.is_complete())

        action_list = action_manager.add_action_response(
            {
                "action_list_id": action_list_id,
                "action_idx": 1,
                "action_name": "send_message",
                "action_params": {"message": "Hello2"},
                "originator": ORCHESTRATOR_COMPONENT_NAME,

            },
            {"text": "Hello2", "files": []},
        )

        self.assertIsNotNone(action_list)
        self.assertFalse(action_list.is_complete())

        action_list = action_manager.add_action_response(
            {
                "action_list_id": action_list_id,
                "action_idx": 2,
                "action_name": "send_message",
                "action_params": {"message": "Hello3"},
                "originator": ORCHESTRATOR_COMPONENT_NAME,
            },
            {"text": "Hello3", "files": []},
        )

        self.assertIsNotNone(action_list)
        self.assertTrue(action_list.is_complete())

        self.assertEqual(len(action_manager.action_requests), 1)
