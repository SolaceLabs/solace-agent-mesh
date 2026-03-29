"""Unit tests for dynamic_model_provider_topics topic generation functions."""

import pytest

from solace_agent_mesh.agent.adk.models.dynamic_model_provider_topics import (
    BOOTSTRAP_SUBSCRIBE_TOPIC,
    BOOTSTRAP_REQUEST_TOPIC,
    BOOTSTRAP_RESPONSE_TOPIC,
    MODEL_CONFIG_UPDATE_TOPIC,
    get_bootstrap_subscribe_topic,
    get_bootstrap_request_topic,
    get_bootstrap_response_topic,
    get_model_config_update_topic,
)


class TestGetBootstrapSubscribeTopic:
    """Test get_bootstrap_subscribe_topic."""

    def test_formats_namespace(self):
        result = get_bootstrap_subscribe_topic("myorg/ai/")
        assert result == "myorg/ai/configuration/model/bootstrap/>"

    def test_empty_namespace(self):
        result = get_bootstrap_subscribe_topic("")
        assert result == "configuration/model/bootstrap/>"

    def test_namespace_without_trailing_slash(self):
        result = get_bootstrap_subscribe_topic("ns")
        assert result == "nsconfiguration/model/bootstrap/>"


class TestGetBootstrapRequestTopic:
    """Test get_bootstrap_request_topic."""

    def test_formats_namespace_and_model_id(self):
        result = get_bootstrap_request_topic("myorg/ai/", "general")
        assert result == "myorg/ai/configuration/model/bootstrap/general"

    def test_empty_namespace(self):
        result = get_bootstrap_request_topic("", "general")
        assert result == "configuration/model/bootstrap/general"

    def test_different_model_ids(self):
        result = get_bootstrap_request_topic("ns/", "premium")
        assert result == "ns/configuration/model/bootstrap/premium"


class TestGetBootstrapResponseTopic:
    """Test get_bootstrap_response_topic."""

    def test_formats_all_params(self):
        result = get_bootstrap_response_topic("myorg/ai/", "general", "agent_1")
        assert result == "myorg/ai/configuration/model/response/general/agent_1"

    def test_empty_namespace(self):
        result = get_bootstrap_response_topic("", "general", "agent_1")
        assert result == "configuration/model/response/general/agent_1"

    def test_different_component_ids(self):
        result = get_bootstrap_response_topic("ns/", "general", "platform_service")
        assert result == "ns/configuration/model/response/general/platform_service"


class TestGetModelConfigUpdateTopic:
    """Test get_model_config_update_topic."""

    def test_formats_namespace_and_model_id(self):
        result = get_model_config_update_topic("myorg/ai/", "general")
        assert result == "myorg/ai/configuration/model/general"

    def test_empty_namespace(self):
        result = get_model_config_update_topic("", "general")
        assert result == "configuration/model/general"

    def test_different_model_ids(self):
        result = get_model_config_update_topic("ns/", "premium")
        assert result == "ns/configuration/model/premium"


class TestTopicTemplateConstants:
    """Verify the raw template strings are correct."""

    def test_bootstrap_subscribe_template(self):
        assert BOOTSTRAP_SUBSCRIBE_TOPIC == "{namespace}configuration/model/bootstrap/>"

    def test_bootstrap_request_template(self):
        assert BOOTSTRAP_REQUEST_TOPIC == "{namespace}configuration/model/bootstrap/{model_id}"

    def test_bootstrap_response_template(self):
        assert BOOTSTRAP_RESPONSE_TOPIC == "{namespace}configuration/model/response/{model_id}/{component_id}"

    def test_model_config_update_template(self):
        assert MODEL_CONFIG_UPDATE_TOPIC == "{namespace}configuration/model/{model_id}"
