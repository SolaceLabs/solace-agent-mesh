"""
Tests for project artifact description length limits.

Validates that file descriptions exceeding DEFAULT_MAX_PROJECT_FILE_DESCRIPTION_LENGTH (1000 chars)
are rejected with a 400 status on creation and update endpoints.
"""

import io
import json

from fastapi.testclient import TestClient

from tests.integration.apis.infrastructure.gateway_adapter import GatewayAdapter

LIMIT = 1000


def make_file(name: str):
    return ("files", (name, io.BytesIO(b"x"), "text/plain"))


def seed(gw: GatewayAdapter, project_id: str):
    gw.seed_project(
        project_id=project_id,
        name=project_id,
        user_id="sam_dev_user",
        description="",
    )


class TestArtifactDescriptionLimit:

    def test_description_over_limit_rejected_on_create(
        self, both_enabled_client: TestClient
    ):
        response = both_enabled_client.post(
            "/api/v1/projects",
            data={
                "name": "Test",
                "description": "",
                "fileMetadata": json.dumps({"doc.txt": "a" * (LIMIT + 1)}),
            },
            files=[make_file("doc.txt")],
        )
        assert response.status_code == 400
        assert "exceeds maximum length" in response.json()["detail"]

    def test_description_at_limit_succeeds_on_create(
        self, both_enabled_client: TestClient
    ):
        response = both_enabled_client.post(
            "/api/v1/projects",
            data={
                "name": "Test",
                "description": "",
                "fileMetadata": json.dumps({"doc.txt": "a" * LIMIT}),
            },
            files=[make_file("doc.txt")],
        )
        assert response.status_code == 201
