"""The agent component for the replicator"""

import os
import copy
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))

from solace_agent_mesh.agents.base_agent_component import (
    agent_info,
    BaseAgentComponent,
)

# Action import
from src.agents.replicator.actions.action_replicator import ActionReplicator

info = copy.deepcopy(agent_info)
info["agent_name"] = "replicator"
info["class_name"] = "ReplicatorAgentComponent"
info["description"] = (
    "This agent is able to create new instances of agents by making copies "
    "of agent prototypes with custom configurations."
)

class ReplicatorAgentComponent(BaseAgentComponent):
    info = info
    # actions
    actions = [ActionReplicator]
