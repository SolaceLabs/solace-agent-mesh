from datetime import datetime, timedelta
from ..services.middleware_service.middleware_service import MiddlewareService
import threading
from solace_ai_connector.common.log import log
from ..common.action_response import ActionResponse
from ..common.time import TEN_MINUTES, THIRTY_MINUTES


ORCHESTRATOR_HISTORY_IDENTIFIER = "orchestrator"

ORCHESTRATOR_HISTORY_CONFIG = {
    "type": "memory",
    "time_to_live": THIRTY_MINUTES,
    "expiration_check_interval": TEN_MINUTES,
    "history_policy": {
        "max_turns": 30,
        "max_characters": 0,
        "enforce_alternate_message_roles": False,
    },
}


class OrchestratorState:
    """Singleton object to store orchestrator state"""

    _instance = None
    _lock = threading.Lock()
    _config = None
    _session_state = {}

    @classmethod
    def set_config(cls, config):
        cls._config = config

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(OrchestratorState, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "registered_agents"):
            self.registered_agents = {}

    def register_agent(self, agent):
        with self._lock:
            agent_name = agent.get("agent_name")
            agent["state"] = "closed"

            # Always update the agent information
            self.registered_agents[agent_name] = agent

            # Reset its TTL
            self.registered_agents[agent_name][
                "expire_time"
            ] = datetime.now() + timedelta(
                milliseconds=self._config.get("agent_ttl_ms")
            )

    def get_registered_agents(self):
        with self._lock:
            return self.registered_agents

    def get_agent_action(self, agent_name, action_name):
        with self._lock:
            agent = self.registered_agents.get(agent_name)
            if not agent:
                return None
            actions = agent.get("actions")
            if not actions:
                return None
            for action in actions:
                if action is None:
                    continue
                for action_obj_name, action_obj in action.items():
                    if action_obj_name == action_name:
                        return action_obj
            return None

    def age_out_agents(self):
        with self._lock:
            now = datetime.now()
            agents_to_remove = []
            for agent_name, agent in self.registered_agents.items():
                if agent.get("expire_time", datetime.max) < now:
                    log.warning("Agent %s has expired. Removing.", agent_name)
                    agents_to_remove.append(agent_name)
            for agent_name in agents_to_remove:
                del self.registered_agents[agent_name]

    def delete_agent(self, agent_name):
        with self._lock:
            if agent_name in self.registered_agents:
                del self.registered_agents[agent_name]

    def get_session_state(self, session_id):
        if not session_id in self._session_state:
            self._session_state[session_id] = {}
        return self._session_state[session_id]

    def get_agent_state(self, session_id):
        session_state = self.get_session_state(session_id)
        if "agent_state" not in session_state:
            session_state["agent_state"] = {
                "global": {"agent_name": "global", "state": "open"}
            }
        return session_state["agent_state"]

    def set_agent_state(self, session_id, agent_state):
        session_state = self.get_session_state(session_id)
        session_state["agent_state"] = agent_state

    def get_current_subject_starting_id(self, session_id):
        session_state = self.get_session_state(session_id)
        return session_state.get("current_subject_starting_id")

    def set_current_subject_starting_id(self, session_id, current_subject_starting_id):
        session_state = self.get_session_state(session_id)
        session_state["current_subject_starting_id"] = current_subject_starting_id

    def update_agent_state(
        self, agent_name: str, new_state: str, session_id
    ) -> ActionResponse:
        """
        Handle an app state change. Return whether or not
        """
        with self._lock:
            if agent_name == "global":
                return None
            old_state = "closed"
            conversation_agent_state = self.get_agent_state(session_id)
            if agent_name in conversation_agent_state:
                old_state = conversation_agent_state[agent_name].get("state", "closed")
            conversation_agent_state[agent_name] = {
                "agent_name": agent_name,
                "state": new_state,
            }
            self.set_agent_state(session_id, conversation_agent_state)
            if old_state == "closed" and new_state == "open":
                return ActionResponse(
                    invoke_model_again=True,
                )
            return None

    def get_agents_and_actions(self, user_properties: dict) -> dict:
        session_id = user_properties.get("session_id", "")
        result = {}
        middleware_service = MiddlewareService()

        for agent_name, agent in self.registered_agents.items():
            actions = agent.get("actions", [])
            filtered_actions = middleware_service.get("filter_action")(
                user_properties, actions
            )

            if filtered_actions:
                agent_state = self.get_agent_state(session_id).get(agent_name, {})
                state = agent_state.get("state", "closed")

                result[agent_name] = {
                    "description": agent.get("description"),
                    "state": state,
                }

                if state == "open":
                    if agent.get("detailed_description"):
                        result[agent_name]["description"] = agent.get(
                            "detailed_description"
                        )
                    result[agent_name]["actions"] = filtered_actions

        return result
