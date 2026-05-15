"""Unit tests for providers_router RBAC scope declarations.

Runtime enforcement of ValidatedUserConfig is covered by
tests/unit/gateway/http_sse/test_dependencies.py — here we only verify
that each provider endpoint declares the expected sam:models:* scope.
"""

import inspect

import pytest
from fastapi.params import Depends

from solace_agent_mesh.shared.auth.dependencies import ValidatedUserConfig


def _endpoint_scopes(endpoint_func) -> list[list[str]]:
    """Return all ValidatedUserConfig.required_scopes declared on an endpoint."""
    scopes: list[list[str]] = []
    for param in inspect.signature(endpoint_func).parameters.values():
        default = param.default
        if isinstance(default, Depends):
            dep = default.dependency
            if isinstance(dep, ValidatedUserConfig):
                scopes.append(dep.required_scopes)
    return scopes


class TestProvidersEndpointScopes:
    """Provider query endpoints are only reachable from the create/edit model
    form, so they share the same sam:model_config:write gate as the underlying
    write endpoints.
    """

    @pytest.mark.parametrize(
        "endpoint_name",
        ["list_provider_models", "get_supported_params"],
    )
    def test_endpoint_requires_model_config_write(self, endpoint_name):
        from solace_agent_mesh.services.platform.api.routers import providers_router

        endpoint = getattr(providers_router, endpoint_name)
        assert [["sam:model_config:write"]] == _endpoint_scopes(endpoint), (
            f"{endpoint_name} should depend on ValidatedUserConfig(['sam:model_config:write'])"
        )
