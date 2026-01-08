"""Tests for deployment ID extension in AgentCard publishing."""

from unittest.mock import Mock
from solace_agent_mesh.agent.protocol.event_handlers import publish_agent_card

DEPLOYMENT_EXTENSION_URI = "https://solace.com/a2a/extensions/sam/deployment"


class TestDeploymentExtension:
    """Test deployment extension is added to AgentCard."""

    def test_publish_agent_card_with_deployment_id(self):
        """Test agent card includes deployment extension when deployment.id present."""
        component = Mock()
        component.get_config = Mock(side_effect=lambda key, default={}: {
            "agent_card": {
                "description": "Test agent",
                "skills": []
            },
            "agent_name": "TestAgent",
            "namespace": "test",
            "supports_streaming": True,
            "deployment": {"id": "test-deployment-123"}
        }.get(key, default))
        component.peer_agents = {}
        component.agent_card_tool_manifest = []
        component.log_identifier = "[TestAgent]"
        component.HOST_COMPONENT_VERSION = "1.0.0"

        published_card = None
        def capture_publish(card_dict, topic):
            nonlocal published_card
            published_card = card_dict

        component.publish_a2a_message = capture_publish

        publish_agent_card(component)

        assert published_card is not None
        assert "capabilities" in published_card
        assert "extensions" in published_card["capabilities"]

        extensions = published_card["capabilities"]["extensions"]
        deployment_ext = next(
            (ext for ext in extensions if ext["uri"] == DEPLOYMENT_EXTENSION_URI),
            None
        )

        assert deployment_ext is not None
        assert deployment_ext["params"]["id"] == "test-deployment-123"
        assert deployment_ext["required"] is False

    def test_publish_agent_card_without_deployment_id(self):
        """Test agent card works without deployment section (backward compat)."""
        component = Mock()
        component.get_config = Mock(side_effect=lambda key, default={}: {
            "agent_card": {
                "description": "Test agent",
                "skills": []
            },
            "agent_name": "TestAgent",
            "namespace": "test",
            "supports_streaming": False
        }.get(key, default))
        component.peer_agents = {}
        component.agent_card_tool_manifest = []
        component.log_identifier = "[TestAgent]"
        component.HOST_COMPONENT_VERSION = "1.0.0"

        published_card = None
        def capture_publish(card_dict, topic):
            nonlocal published_card
            published_card = card_dict

        component.publish_a2a_message = capture_publish

        publish_agent_card(component)

        assert published_card is not None

        extensions = published_card.get("capabilities", {}).get("extensions")
        if extensions:
            deployment_ext = next(
                (ext for ext in extensions if ext["uri"] == DEPLOYMENT_EXTENSION_URI),
                None
            )
            assert deployment_ext is None

    def test_deployment_extension_with_other_extensions(self):
        """Test deployment extension coexists with other extensions."""
        component = Mock()
        component.get_config = Mock(side_effect=lambda key, default={}: {
            "agent_card": {
                "description": "Test agent",
                "skills": []
            },
            "agent_name": "TestAgent",
            "display_name": "Test Display Name",
            "namespace": "test",
            "supports_streaming": True,
            "deployment": {"id": "deploy-456"}
        }.get(key, default))

        peer_agent_card = Mock()
        peer_agent_card.name = "PeerAgent"
        component.peer_agents = {"PeerAgent": peer_agent_card}
        component.agent_card_tool_manifest = []
        component.log_identifier = "[TestAgent]"
        component.HOST_COMPONENT_VERSION = "1.0.0"

        published_card = None
        def capture_publish(card_dict, topic):
            nonlocal published_card
            published_card = card_dict

        component.publish_a2a_message = capture_publish

        publish_agent_card(component)

        extensions = published_card["capabilities"]["extensions"]
        assert len(extensions) >= 3

        uris = [ext["uri"] for ext in extensions]
        assert DEPLOYMENT_EXTENSION_URI in uris
        assert "https://solace.com/a2a/extensions/display-name" in uris
        assert "https://solace.com/a2a/extensions/peer-agent-topology" in uris

    def test_deployment_extension_ordering(self):
        """Test deployment extension is added first in the list."""
        component = Mock()
        component.get_config = Mock(side_effect=lambda key, default={}: {
            "agent_card": {
                "description": "Test agent",
                "skills": []
            },
            "agent_name": "TestAgent",
            "display_name": "Test Display",
            "namespace": "test",
            "supports_streaming": False,
            "deployment": {"id": "deploy-789"}
        }.get(key, default))
        component.peer_agents = {}
        component.agent_card_tool_manifest = []
        component.log_identifier = "[TestAgent]"
        component.HOST_COMPONENT_VERSION = "1.0.0"

        published_card = None
        def capture_publish(card_dict, topic):
            nonlocal published_card
            published_card = card_dict

        component.publish_a2a_message = capture_publish

        publish_agent_card(component)

        extensions = published_card["capabilities"]["extensions"]
        assert extensions[0]["uri"] == DEPLOYMENT_EXTENSION_URI
