import pytest

pytestmark = [
    pytest.mark.all,
    pytest.mark.asyncio,
    pytest.mark.common,
    pytest.mark.middleware
]

async def test_resolve_user_config():
    """
    Tests the resolve_user_config function with various configurations.
    """
    from src.solace_agent_mesh.common.middleware.config_resolver import ConfigResolver

    # test user identity
    valid_user_identity = {
        "id": "test_user_id",
        "name": "test_user_name"
    }

    # test gateway context
    valid_gateway_context = {
        "gateway_id": "test_gateway_id",
    }

    # test base configuration
    valid_base_config = {
        "test_key": "test_value"
    }

    # Resolve user config
    resolved_config = await ConfigResolver.resolve_user_config(
        valid_user_identity, valid_gateway_context, valid_base_config
    )

    assert resolved_config["test_key"] == valid_base_config["test_key"]

def test_is_feature_enabled():
    """
    Tests the is_feature_enabled function with various feature descriptors.
    """
    from src.solace_agent_mesh.common.middleware.config_resolver import ConfigResolver

    # test user config
    valid_user_config = {
        "test_user_key": "test_user_value"
    }

    # test feature descriptor
    valid_feature_descriptor = {
       "required_scopes": ["tool:artifact:load"],
       "feature_type": "test_feature_type",
       "function_name": "test_function_name"
    }

    # test context
    valid_context = {
        "context_key": "context_value"
    }

    # Check if feature is enabled
    is_enabled = ConfigResolver.is_feature_enabled(
        valid_user_config, valid_feature_descriptor, valid_context
    )

    assert is_enabled  # Default implementation returns True for all features

def test_validate_operation_config():
    """
    Tests the validate_operation_config function with various operation specifications.
    """
    from src.solace_agent_mesh.common.middleware.config_resolver import ConfigResolver

    # test user config
    valid_user_config = {
        "test_user_key": "test_user_value"
    }

    # test operation specification
    valid_operation_spec = {
        "operation_type": "visualization_subscription",
        "target_type": "my_a2a_messages",
    }

    # test gateway context
    valid_gateway_context = {
        "gateway_id": "test_gateway_id",
    }

    # Validate operation config
    validated_operation_config = ConfigResolver.validate_operation_config(
        valid_user_config, valid_operation_spec, valid_gateway_context
    )

    assert validated_operation_config["valid"]
    assert validated_operation_config["reason"] == "default_validation"
    assert validated_operation_config["operation_type"] == valid_operation_spec["operation_type"]

def test_filter_available_options():
    """
    Tests the filter_available_options function with various options.
    """
    from src.solace_agent_mesh.common.middleware.config_resolver import ConfigResolver

    # test user config
    valid_user_config = {
        "test_user_key": "test_user_value"
    }

    # test available options
    valid_available_options = [
        {"option_key": "option_value_1"},
        {"option_key": "option_value_2"},
        {"option_key": "option_value_3"}
    ]

    # Filter available options
    filtered_options = ConfigResolver.filter_available_options(
        valid_user_config, valid_available_options, {}
    )

    assert len(filtered_options) == len(valid_available_options)

def test_bind_config_resolver_and_get_config_resolver():
    """
    Tests the bind_config_resolver function to ensure it binds a custom resolver.
    """
    from src.solace_agent_mesh.common.middleware.config_resolver import ConfigResolver
    from src.solace_agent_mesh.common.middleware.registry import MiddlewareRegistry

    class CustomConfigResolver(ConfigResolver):
        pass

    MiddlewareRegistry.bind_config_resolver(CustomConfigResolver)

    # Verify that the custom resolver is bound
    assert MiddlewareRegistry.get_config_resolver() == CustomConfigResolver

def test_register_initialization_callback():
    """
    Tests the register_initialization_callback function to ensure it registers a callback.
    """
    from src.solace_agent_mesh.common.middleware.registry import MiddlewareRegistry

    def sample_callback():
        pass

    MiddlewareRegistry.register_initialization_callback(sample_callback)

    # Verify that the callback is registered
    assert sample_callback in MiddlewareRegistry._initialization_callbacks

def test_initialize_middleware():
    """
    Tests the initialization of the MiddlewareRegistry to ensure it sets up correctly.
    """
    from src.solace_agent_mesh.common.middleware.registry import MiddlewareRegistry

    class callback_test_value:
        def __init__(self, value):
            self.callback_test_value = value

        def set_callback_value(self, value):
            self.callback_test_value = value

    callback_test_value_instance = callback_test_value("initial_value")

    # Initialize the registry
    def sample_callback():
        callback_test_value_instance.set_callback_value("callback_called!")

    MiddlewareRegistry.register_initialization_callback(sample_callback)
    assert sample_callback in MiddlewareRegistry._initialization_callbacks
    MiddlewareRegistry.initialize_middleware()

    # Verify that the registry is initialized correctly with the callback
    assert callback_test_value_instance.callback_test_value == "callback_called!"

    # MiddlewareRegistry initialized successfully with callback.

def test_reset_bindings():
    """
    Tests the reset_bindings function to ensure it clears the registry.
    """
    from src.solace_agent_mesh.common.middleware.config_resolver import ConfigResolver
    from src.solace_agent_mesh.common.middleware.registry import MiddlewareRegistry

    class CustomConfigResolver(ConfigResolver):
        pass

    # Bind a custom resolver
    MiddlewareRegistry.bind_config_resolver(CustomConfigResolver)
    assert MiddlewareRegistry.get_config_resolver() == CustomConfigResolver

    # add a callback
    def sample_callback():
        pass
    MiddlewareRegistry.register_initialization_callback(sample_callback)
    assert sample_callback in MiddlewareRegistry._initialization_callbacks

    # Reset the bindings
    MiddlewareRegistry.reset_bindings()

    # Verify that the bindings are cleared
    assert MiddlewareRegistry._config_resolver is None
    assert len(MiddlewareRegistry._initialization_callbacks) == 0

    import logging
    logging.info("MiddlewareRegistry bindings reset successfully.")

def test_get_registry_status():
    """
    Tests the get_registry_status function to ensure it returns the correct status.
    """
    from src.solace_agent_mesh.common.middleware.config_resolver import ConfigResolver
    from src.solace_agent_mesh.common.middleware.registry import MiddlewareRegistry

    class CustomConfigResolver(ConfigResolver):
        pass

    # change class name for testing purposes
    CustomConfigResolver.__name__ = "CustomConfigResolver_name"

    # Bind a custom resolver
    MiddlewareRegistry.bind_config_resolver(CustomConfigResolver)
    assert MiddlewareRegistry.get_config_resolver() == CustomConfigResolver

    # add a callback
    def sample_callback():
        pass
    MiddlewareRegistry.register_initialization_callback(sample_callback)
    assert sample_callback in MiddlewareRegistry._initialization_callbacks

    # Get the registry status
    status = MiddlewareRegistry.get_registry_status()
    assert status["config_resolver"] == "CustomConfigResolver_name", "Expected config_resolver to be 'CustomConfigResolver_name'."
    assert status["initialization_callbacks"] == 1, "Expected exactly 1 initialization callback."
    assert status["has_custom_bindings"], "Expected registry to have custom bindings."

    # Removed print statement as assertion messages provide sufficient context.
