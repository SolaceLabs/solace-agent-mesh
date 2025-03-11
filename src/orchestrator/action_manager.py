"""The Action Manager tracks all pending actions and manages their execution. It
does the following things:

1. For each LLM response that has any actions, it create a unique ActionRequestList object.
2. The ActionRequestList object holds the list of actions to be executed.
3. As each action response is received, the Action Manager updates the ActionRequestList object.
4. Once all actions are received, the Action Manager sends the full response to the Orchestrator.
5. A periodic timer checks to see if any actions should be timed out. The timer is externally
   managed - this class just has a method to call to check for timeouts.

"""

from uuid import uuid4
from datetime import datetime

from solace_ai_connector.common.log import log
from ..common.utils import format_agent_response
from ..common.constants import ORCHESTRATOR_COMPONENT_NAME

ACTION_REQUEST_TIMEOUT = 180


class ActionManager:
    """This class manages all the ActionRequests that are pending"""

    def __new__(cls, kv_store, lock_manager):
        lock = lock_manager.get_lock("action_manager")
        with lock:
            instance = kv_store.get("action_manager_instance")
            if instance is None:
                instance = super(ActionManager, cls).__new__(cls)
                kv_store.set("action_manager_instance", instance)
        return instance

    def __init__(self, kv_store, lock_manager):
        self.action_requests = {}
        self.lock = lock_manager.get_lock("action_manager")

        with self.lock:
            action_requests = kv_store.get("action_requests")
            if not action_requests:
                action_requests = {}
                kv_store.set("action_requests", action_requests)
        self.action_requests = action_requests

    def add_action_request(self, action_requestlist, user_properties):
        """Add an action request to the list"""
        uuid = str(uuid4())

        # Add the uuid to each action
        for action in action_requestlist:
            action["action_list_id"] = uuid
        with self.lock:
            if uuid in self.action_requests:
                log.error("Action request with UUID %s already exists", uuid)

            arl = ActionRequestList(uuid, action_requestlist, user_properties)
            self.action_requests[uuid] = arl

    def delete_action_request(self, action_list_id):
        """Delete an action request from the list"""
        with self.lock:
            if action_list_id in self.action_requests:
                del self.action_requests[action_list_id]

    def get_action_info(self, action_list_id, action_name, action_idx):
        """Get an action request"""
        with self.lock:
            action_list = self.action_requests.get(action_list_id)
            if action_list is None:
                return None

            action = action_list.get_action(action_name, action_idx)
            if action is None:
                return None

        return action

    def add_action_response(self, action_response_obj, response_text_and_files):
        """Add an action response to the list"""
        action_list_id = action_response_obj.get("action_list_id")

        originator = action_response_obj.get("originator", "unknown")
        # Ignore responses for actions that are not originated by the orchestrator
        if originator != ORCHESTRATOR_COMPONENT_NAME:
            log.debug(
                "Ignoring response for action not originated by the orchestrator. "
                "originator: %s   action_list_id: %s", 
                originator, action_list_id
            )
            return None
            
        with self.lock:
            action_list = self.action_requests.get(action_list_id)
            if action_list is None:
                log.error(
                    "Action request %s not found. Maybe it had already timed out",
                    action_list_id,
                )
                return None

            action_list.add_response(action_response_obj, response_text_and_files)

        return action_list

    def do_timeout_check(self):
        """Check for any actions that have timed out"""
        events = []
        with self.lock:
            action_list_ids = list(self.action_requests.keys())
            for action_list_id in action_list_ids:
                action_requestlist = self.action_requests.get(action_list_id)
                if action_requestlist.has_timed_out():
                    log.info("Action request %s has timed out", action_list_id)
                    events.extend(self.do_timeout(action_requestlist, action_list_id))
        return events

    def do_timeout(self, action_requestlist, action_list_id):
        """Handle a timeout for a specific action request"""
        events = action_requestlist.get_action_response_timeout_events()
        if len(events) == 0:
            timeout_count = action_requestlist.get_timeout_count()
            if timeout_count > 10:
                log.error(
                    "Action request %s has timed out too many times", action_list_id
                )
                del self.action_requests[action_list_id]
            else:
                action_requestlist.increment_timeout_count()
        return events


class ActionRequestList:
    """This class holds the list of actions to be executed for a single LLM response"""

    def __init__(self, action_list_id, actions, user_properties):
        self.action_list_id = action_list_id
        self.actions = actions
        self.user_properties = user_properties
        self.num_pending_actions = len(actions)
        self.create_time = datetime.now()
        self.timeout_count = 0
        self.responses = {}

    def has_timed_out(self):
        """Check if the action request has timed out"""
        return (
            datetime.now() - self.create_time
        ).total_seconds() > ACTION_REQUEST_TIMEOUT

    def get_timeout_count(self):
        """Get the number of times this action request has timed out"""
        return self.timeout_count

    def increment_timeout_count(self):
        """Increment the number of times this action request has timed out"""
        self.timeout_count += 1

    def get_user_properties(self):
        """Get the user properties"""
        return self.user_properties

    def get_action_response_timeout_events(self):
        """Go through all the action requests and return a timeout event
        for each one that does not yet have a response"""
        timeout_events = []
        for action in self.actions:
            if "response" not in action:
                timeout_events.append(
                    {
                        "message": "Action response timed out",
                        "action_list_id": self.action_list_id,
                        "action_idx": action.get("action_idx"),
                        "action_name": action.get("action_name"),
                        "user_properties": self.user_properties,
                    }
                )
            action["response"] = {"text": "Action response timed out"}
            action["timed_out"] = True

        return timeout_events

    def get_action(self, action_name, action_idx):
        """Get the action with the specified name and index"""
        if action_idx is None:
            log.error("Action Response does not have an action_idx")
            return None

        if action_idx >= len(self.actions):
            log.error(
                "Action Response has an invalid action_idx. Max is %s, index is %s",
                len(self.actions),
                action_idx,
            )
            return None

        action = self.actions[action_idx]
        if action.get("action_name") != action_name:
            log.error(
                "Action Response has an invalid action name. Expected %s but got %s",
                action.get("action_name"),
                action_name,
            )
            return None

        return action

    def add_response(self, action_response_obj, response_text_and_files):
        """Add a response to the list - returns True if all actions are complete"""
        action_idx = action_response_obj.get("action_idx")
        action_name = action_response_obj.get("action_name")

        action = self.get_action(action_name, action_idx)

        if "response" in action and not action.get("timed_out"):
            log.error("Action Response already has a response")
        else:
            action["response"] = response_text_and_files
            self.num_pending_actions -= 1

        if self.is_complete():
            log.info("Action request %s is complete", self.action_list_id)
            return True

        return False

    def is_complete(self):
        """Check if all actions have been completed"""
        return self.num_pending_actions == 0

    def get_responses(self):
        """Get all the responses"""
        return self.actions

    def format_ai_response(self):
        """Format the action response for the AI"""
        return format_agent_response(self.actions)
