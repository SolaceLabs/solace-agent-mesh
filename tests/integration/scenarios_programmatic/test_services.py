import json
import pytest
import os
from unittest.mock import Mock

pytestmark = [
    pytest.mark.all,
    pytest.mark.asyncio,
    pytest.mark.common,
    pytest.mark.services
]

__current_dir__ = os.path.dirname(os.path.abspath(__file__))
__test_support_dir__ = os.path.join(__current_dir__, "../test_support")


invalid_json_config = {
        "file_path": os.path.join(__test_support_dir__, "identity_service_users_invalid_json.json"),
        "lookup_key": "id",
        "type": "local_file"
    }

invalid_path_config = {
        "file_path": os.path.join(__test_support_dir__, "ghostfile.json"),
        "lookup_key": "id",
        "type": "local_file"
    }

valid_config = {
        "file_path": os.path.join(__test_support_dir__, "identity_service_users.json"),
        "lookup_key": "id",
        "type": "local_file"
    }

def test_local_file_identity_service_initialization():
    """
    Tests that the LocalFileIdentityService initializes correctly with a valid file path.
    """
    from src.solace_agent_mesh.common.services.providers.local_file_identity_service import (
        LocalFileIdentityService,
    )

    try:
        service = LocalFileIdentityService(valid_config)
        assert service.file_path == valid_config["file_path"]
        assert service.lookup_key == valid_config["lookup_key"]
        assert service.component is None, "Component should be None when not provided"
        print("LocalFileIdentityService initialized successfully.")
    except Exception as e:
        pytest.fail(f"Initialization failed with exception: {e}")

def test_local_file_identity_service_initialization_with_component():
    """
    Tests that the LocalFileIdentityService initializes correctly with a component parameter.
    """
    from src.solace_agent_mesh.common.services.providers.local_file_identity_service import (
        LocalFileIdentityService,
    )
    from unittest.mock import Mock

    try:
        # Create a mock component
        mock_component = Mock()
        service = LocalFileIdentityService(valid_config, component=mock_component)
        assert service.file_path == valid_config["file_path"]
        assert service.lookup_key == valid_config["lookup_key"]
        assert service.component is mock_component, "Component should be set to the provided mock"
        print("LocalFileIdentityService initialized successfully with component.")
    except Exception as e:
        pytest.fail(f"Initialization with component failed with exception: {e}")

def test_local_file_identity_service_invalid_path():
    """
    Tests that the LocalFileIdentityService raises an error when the file path is invalid.
    """
    from src.solace_agent_mesh.common.services.providers.local_file_identity_service import (
        LocalFileIdentityService,
    )

    with pytest.raises(FileNotFoundError):
        LocalFileIdentityService(invalid_path_config)

def test_local_file_identity_service_invalid_json():
    """
    Tests that the LocalFileIdentityService raises an error when the JSON file is invalid.
    """
    from src.solace_agent_mesh.common.services.providers.local_file_identity_service import (
        LocalFileIdentityService,
    )

    with pytest.raises(json.JSONDecodeError):
        LocalFileIdentityService(invalid_json_config)

def test_local_file_identity_service_load_data():
    """
    Tests that the LocalFileIdentityService loads data correctly from a valid JSON file.
    """
    from src.solace_agent_mesh.common.services.providers.local_file_identity_service import (
        LocalFileIdentityService,
    )

    service = LocalFileIdentityService(valid_config)
    assert len(service.all_users) > 0, "No users loaded from the JSON file."
    assert isinstance(service.all_users, list), "All users should be a list."
    assert len(service.user_index) > 0, "User index is empty after loading data."
    assert isinstance(service.user_index, dict), "User index should be a dictionary."

    for user in service.all_users:
        assert service.lookup_key in user, f"User profile missing lookup key: {service.lookup_key}"

    print("LocalFileIdentityService loaded data successfully.")

async def test_local_file_identity_service_get_user_profile():
    """
    Tests that the LocalFileIdentityService can retrieve user profiles correctly.
    """
    from src.solace_agent_mesh.common.services.providers.local_file_identity_service import (
        LocalFileIdentityService,
    )

    service = LocalFileIdentityService(valid_config)

    # Test with a valid user ID
    user_id = "jdoe"
    profile = await service.get_user_profile({"id": user_id})
    assert profile is not None, f"Profile for user ID '{user_id}' should not be None."
    assert profile["id"] == user_id, f"Retrieved profile ID '{profile['id']}' does not match requested ID '{user_id}'."

    # Test with an invalid user ID
    invalid_user_id = "nonexistent_user"
    profile = await service.get_user_profile({"id": invalid_user_id})
    assert profile is None, f"Profile for non-existent user ID '{invalid_user_id}' should be None."

    print("LocalFileIdentityService retrieved user profiles successfully.")

async def test_local_file_identity_service_search_users():
    """
    Tests that the LocalFileIdentityService can search for users based on a query string.
    """
    from src.solace_agent_mesh.common.services.providers.local_file_identity_service import (
        LocalFileIdentityService,
    )

    service = LocalFileIdentityService(valid_config)

    # Test with a valid query that should match multiple users
    query = "Jane"
    results = await service.search_users(query)
    assert len(results) > 0, f"Search for '{query}' should return results."
    for user in results:
        assert "name" in user and query.lower() in user["name"].lower(), \
            f"User '{user}' does not match search query '{query}'."

    # Test with a query that matches no users
    query = "NonExistentUser"
    results = await service.search_users(query)
    assert len(results) == 0, f"Search for '{query}' should return no results."

    print("LocalFileIdentityService search users functionality works correctly.")

def test_identity_service_factory():
    """
    Tests the identity service factory function to ensure it creates the correct service instance.
    """
    from src.solace_agent_mesh.common.services.identity_service import (
        create_identity_service,
    )

    # Test with valid configuration
    service = create_identity_service(valid_config)
    assert service is not None, "Service should be created successfully with valid config."
    assert hasattr(service, 'get_user_profile'), "Service should have 'get_user_profile' method."
    assert service.component is None, "Component should be None when not provided to factory"

    # Test with invalid configuration
    with pytest.raises(ValueError):
        create_identity_service({"type": "invalid_type"})

    # Test with no configuration
    service = create_identity_service(None)
    assert service is None, "Service should be None when no config is provided."

    print("Identity service factory works correctly.")

def test_identity_service_factory_with_component():
    """
    Tests the identity service factory function with a component parameter.
    """
    from src.solace_agent_mesh.common.services.identity_service import (
        create_identity_service,
    )
    from unittest.mock import Mock

    # Create a mock component
    mock_component = Mock()

    # Test with valid configuration and component
    service = create_identity_service(valid_config, component=mock_component)
    assert service is not None, "Service should be created successfully with valid config and component."
    assert hasattr(service, 'get_user_profile'), "Service should have 'get_user_profile' method."
    assert service.component is mock_component, "Component should be set to the provided mock"

    # Test with no configuration but with component
    service = create_identity_service(None, component=mock_component)
    assert service is None, "Service should be None when no config is provided, regardless of component."

    print("Identity service factory with component works correctly.")

def test_employee_service_factory():
    """
    Tests the employee service factory function to ensure it creates the correct service instance.
    """
    from src.solace_agent_mesh.common.services.employee_service import (
        create_employee_service,
    )

    # Test with some dummy configuration, but plugin not installed, so expect ValueError when metadata.entry_points(group="solace_agent_mesh.plugins")
    with pytest.raises(ValueError):
        create_employee_service({"type": "dummy_type"})
